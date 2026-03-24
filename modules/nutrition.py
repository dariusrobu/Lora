# modules/nutrition.py

import aiohttp
from typing import Dict, Any, Tuple, List, Optional
from bot.formatter import escape_md
from datetime import date
from core.config import NUTRITIONIX_APP_ID, NUTRITIONIX_API_KEY
import db.queries.nutrition as nutrition_queries

NUTRITIONIX_URL = "https://trackapi.nutritionix.com/v2/natural/nutrients"

async def get_nutritionix_data(query: str) -> Optional[List[Dict]]:
    """Calls Nutritionix Natural Language API to parse food string."""
    if not NUTRITIONIX_APP_ID or not NUTRITIONIX_API_KEY:
        print("Nutritionix API keys missing.", flush=True)
        return None
        
    headers = {
        "x-app-id": NUTRITIONIX_APP_ID,
        "x-app-key": NUTRITIONIX_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(NUTRITIONIX_URL, headers=headers, json={"query": query}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(f"Nutritionix API error ({resp.status}): {text}", flush=True)
                    return None
                data = await resp.json()
                return data.get("foods", [])
    except Exception as e:
        print(f"Nutritionix call error: {e}", flush=True)
        return None

async def handle_nutrition_intent(pool, intent: str, data: Dict[str, Any], bot=None) -> Tuple[str, None]:
    """Main router for nutrition-related intents."""
    
    if intent == "meal_log":
        # We can accept either pre-parsed items or a raw description
        items = data.get("items", [])
        meal_type = data.get("meal_type", "masa")
        description = data.get("description") # The raw text like "2 oua si o felie de paine"
        
        # If Gemini didn't extract items but gave a description, or if we want to re-parse
        # for better accuracy using Nutritionix's NLP:
        query = description if description else ", ".join([f"{i.get('quantity_g', '')}g {i['name']}" for i in items])
        
        if not query:
            return "Spune-mi ce ai mâncat și cantitățile aproximative\\. 🍎", None
            
        foods = await get_nutritionix_data(query)
        
        if not foods:
            return "Nu am putut analiza nutrienții pentru această masă\\. 😕 Verifică dacă API key-ul este valid\\.", None
            
        found_items = []
        total_cal = total_prot = total_carbs = total_fat = 0.0
        
        for f in foods:
            cal = float(f.get("nf_calories", 0))
            prot = float(f.get("nf_protein", 0))
            carbs = float(f.get("nf_total_carbohydrate", 0))
            fat = float(f.get("nf_total_fat", 0))
            
            total_cal += cal
            total_prot += prot
            total_carbs += carbs
            total_fat += fat
            
            found_items.append({
                "name": f.get("food_name", "Unknown"),
                "quantity_g": float(f.get("serving_weight_grams", 0)),
                "calories": cal,
                "protein": prot,
                "carbs": carbs,
                "fat": fat
            })
            
        # Log to DB
        await nutrition_queries.log_meal(
            pool, date.today(), meal_type,
            {"calories": total_cal, "protein": total_prot, "carbs": total_carbs, "fat": total_fat},
            description or query,
            found_items
        )
        
        # Get daily totals and targets for the reply
        day_totals = await nutrition_queries.get_daily_totals(pool, date.today())
        targets = await nutrition_queries.get_nutrition_targets(pool)
        
        # Build reply
        lines = [f"🍽 *{escape_md(meal_type.replace('_', ' ').title())}* înregistrat\\!"]
        lines.append(f"🔥 *{int(total_cal)}* kcal | 💪 *{total_prot:.1f}g* P | 🍞 *{total_carbs:.1f}g* C | 🫒 *{total_fat:.1f}g* F")
        
        if len(found_items) > 1:
            item_names = [escape_md(f['name']) for f in found_items]
            lines.append(f"_{', '.join(item_names)}_")
            
        lines.append("")
        lines.append(f"📊 *Total azi:* {int(day_totals['calories'])} kcal")
        
        if targets:
            prot_pct = int((day_totals['protein'] / targets['protein_g']) * 100)
            prot_bar = "█" * min(prot_pct // 10, 10) + "░" * max(10 - prot_pct // 10, 0)
            lines.append(f"💪 Proteină: `{prot_bar}` {int(day_totals['protein'])}/{targets['protein_g']}g")
            
            cal_rem = targets['calories'] - int(day_totals['calories'])
            if cal_rem > 0:
                lines.append(f"🍴 Mai poți consuma *{cal_rem}* kcal azi\\.")
            else:
                lines.append("⚠️ Ai depășit targetul de calorii pe azi\\.")

        return "\n".join(lines), None

    elif intent == "nutrition_summary":
        day_totals = await nutrition_queries.get_daily_totals(pool, date.today())
        targets = await nutrition_queries.get_nutrition_targets(pool)
        
        if day_totals['calories'] == 0:
            return "Nu ai logat nicio masă azi\\. 🍎", None
            
        lines = ["🍽 *Nutriție Azi*\n"]
        lines.append(f"🔥 Calorii: *{int(day_totals['calories'])}* / {targets['calories']} kcal")
        lines.append(f"💪 Proteină: *{day_totals['protein']:.1f}* / {targets['protein_g']}g")
        lines.append(f"🍞 Carbs: *{day_totals['carbs']:.1f}* / {targets['carbs_g']}g")
        lines.append(f"🫒 Grăsimi: *{day_totals['fat']:.1f}* / {targets['fat_g']}g")
        
        # Add visual progress bars
        cal_pct = min(int((day_totals['calories'] / targets['calories']) * 100), 100)
        prot_pct = min(int((day_totals['protein'] / targets['protein_g']) * 100), 100)
        
        cal_bar = "█" * (cal_pct // 10) + "░" * (10 - (cal_pct // 10))
        prot_bar = "█" * (prot_pct // 10) + "░" * (10 - (prot_pct // 10))
        
        lines.insert(2, f"🔥 `{cal_bar}` {cal_pct}%")
        lines.insert(5, f"💪 `{prot_bar}` {prot_pct}%")
        
        return "\n".join(lines), None

    elif intent == "nutrition_target":
        targets = await nutrition_queries.get_nutrition_targets(pool)
        return (
            f"🎯 *Targeturi Zilnice*\n\n"
            f"🔥 Calorii: *{targets['calories']}* kcal\n"
            f"💪 Proteină: *{targets['protein_g']}g*\n"
            f"🍞 Carbs: *{targets['carbs_g']}g*\n"
            f"🫒 Grăsimi: *{targets['fat_g']}g*"
        ), None

    return "Nu am înțeles cererea legată de nutriție\\. 🤔", None


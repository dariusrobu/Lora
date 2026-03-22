# modules/nutrition.py

import aiohttp
import asyncio
from typing import Dict, Any, Tuple, List, Optional
from bot.formatter import escape_md
from datetime import date

OPENFOODFACTS_URL = "https://world.openfoodfacts.org/cgi/search.pl"

async def search_food(food_name: str) -> Optional[Dict]:
    """Caută un aliment în OpenFoodFacts și returnează valorile nutriționale per 100g."""
    params = {
        "search_terms": food_name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 5,
        "fields": "product_name,nutriments,serving_size"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(OPENFOODFACTS_URL, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
                products = data.get("products", [])
                
                if not products:
                    return None
                
                # Găsește primul produs cu date nutriționale complete
                for product in products:
                    nutriments = product.get("nutriments", {})
                    if nutriments.get("energy-kcal_100g") or nutriments.get("energy_100g"):
                        calories = nutriments.get("energy-kcal_100g") or (nutriments.get("energy_100g", 0) / 4.184)
                        return {
                            "name": product.get("product_name", food_name),
                            "calories_100g": round(float(calories or 0), 1),
                            "protein_100g": round(float(nutriments.get("proteins_100g", 0)), 1),
                            "carbs_100g": round(float(nutriments.get("carbohydrates_100g", 0)), 1),
                            "fat_100g": round(float(nutriments.get("fat_100g", 0)), 1),
                        }
                return None
    except Exception as e:
        print(f"OpenFoodFacts error for {food_name}: {e}", flush=True)
        return None

# Fallback pentru alimente comune românești
COMMON_FOODS = {
    "ou": {"calories_100g": 143, "protein_100g": 13.0, "carbs_100g": 1.1, "fat_100g": 9.5},
    "oua": {"calories_100g": 143, "protein_100g": 13.0, "carbs_100g": 1.1, "fat_100g": 9.5},
    "piept pui": {"calories_100g": 165, "protein_100g": 31.0, "carbs_100g": 0.0, "fat_100g": 3.6},
    "pui": {"calories_100g": 165, "protein_100g": 31.0, "carbs_100g": 0.0, "fat_100g": 3.6},
    "porc": {"calories_100g": 242, "protein_100g": 27.0, "carbs_100g": 0.0, "fat_100g": 14.0},
    "carne porc": {"calories_100g": 242, "protein_100g": 27.0, "carbs_100g": 0.0, "fat_100g": 14.0},
    "cartofi": {"calories_100g": 77, "protein_100g": 2.0, "carbs_100g": 17.0, "fat_100g": 0.1},
    "cartof": {"calories_100g": 77, "protein_100g": 2.0, "carbs_100g": 17.0, "fat_100g": 0.1},
    "orez": {"calories_100g": 130, "protein_100g": 2.7, "carbs_100g": 28.0, "fat_100g": 0.3},
    "paine": {"calories_100g": 265, "protein_100g": 9.0, "carbs_100g": 49.0, "fat_100g": 3.2},
    "branza vaci": {"calories_100g": 98, "protein_100g": 11.0, "carbs_100g": 3.4, "fat_100g": 4.3},
    "lapte": {"calories_100g": 61, "protein_100g": 3.2, "carbs_100g": 4.8, "fat_100g": 3.3},
    "banana": {"calories_100g": 89, "protein_100g": 1.1, "carbs_100g": 23.0, "fat_100g": 0.3},
    "mar": {"calories_100g": 52, "protein_100g": 0.3, "carbs_100g": 14.0, "fat_100g": 0.2},
    "mere": {"calories_100g": 52, "protein_100g": 0.3, "carbs_100g": 14.0, "fat_100g": 0.2},
}

async def get_food_nutrients(food_name: str) -> Optional[Dict]:
    """Încearcă fallback local, apoi OpenFoodFacts."""
    # Check fallback local mai întâi
    food_lower = food_name.lower().strip()
    for key, values in COMMON_FOODS.items():
        if key in food_lower or food_lower in key:
            return {**values, "name": food_name}
    
    # Caută în OpenFoodFacts
    result = await search_food(food_name)
    return result

async def log_meal(pool, meal_type: str, items: List[Dict], description: str = None) -> Tuple[str, None]:
    """Loghează o masă cu ingredientele ei."""
    total_cal = total_prot = total_carbs = total_fat = 0.0
    found_items = []
    not_found = []
    
    # Caută nutrienți pentru fiecare ingredient
    tasks = [get_food_nutrients(item["name"]) for item in items]
    results = await asyncio.gather(*tasks)
    
    for i, nutrients in enumerate(results):
        item = items[i]
        qty = float(item.get("quantity_g", 100))
        
        if nutrients:
            factor = qty / 100
            cal = round(nutrients["calories_100g"] * factor, 1)
            prot = round(nutrients["protein_100g"] * factor, 1)
            carbs = round(nutrients["carbs_100g"] * factor, 1)
            fat = round(nutrients["fat_100g"] * factor, 1)
            
            total_cal += cal
            total_prot += prot
            total_carbs += carbs
            total_fat += fat
            
            found_items.append({
                "name": item["name"],
                "quantity_g": qty,
                "calories": cal,
                "protein": prot,
                "carbs": carbs,
                "fat": fat
            })
        else:
            not_found.append(item["name"])
    
    # Salvează în DB
    async with pool.acquire() as conn:
        meal_id = await conn.fetchval("""
            INSERT INTO meals (meal_type, total_calories, total_protein, total_carbs, total_fat, description)
            VALUES ($1, $2, $3, $4, $5, $6) RETURNING id
        """, meal_type, total_cal, total_prot, total_carbs, total_fat, description)
        
        for item in found_items:
            await conn.execute("""
                INSERT INTO meal_items (meal_id, food_name, quantity_g, calories, protein, carbs, fat)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, meal_id, item["name"], item["quantity_g"], 
                item["calories"], item["protein"], item["carbs"], item["fat"])
    
    # Calculează totalul zilei
    day_totals = await get_daily_totals(pool)
    async with pool.acquire() as conn:
        targets = await conn.fetchrow("SELECT * FROM nutrition_targets LIMIT 1")
    
    # Build reply
    lines = [f"🍽 *{escape_md(meal_type.replace('_', ' ').title())}* — {int(total_cal)} kcal"]
    lines.append(f"💪 Proteină: *{total_prot:.1f}g* · Carbs: {total_carbs:.1f}g · Grăsimi: {total_fat:.1f}g")
    
    if not_found:
        lines.append(f"⚠️ Nu am găsit: {escape_md(', '.join(not_found))}")
    
    lines.append("")
    lines.append(f"📊 *Azi total:* {int(day_totals['calories'])} kcal · {day_totals['protein']:.0f}g proteină")
    
    if targets:
        prot_remaining = float(targets['protein_g']) - float(day_totals['protein'])
        cal_remaining = float(targets['calories']) - float(day_totals['calories'])
        
        if prot_remaining > 5:
            lines.append(f"→ Mai ai nevoie de *{prot_remaining:.0f}g proteină* și {int(cal_remaining)} kcal")
        else:
            lines.append(f"→ Target proteină atins\\! ✅")
    
    return "\n".join(lines), None

async def get_daily_totals(pool, target_date=None) -> Dict:
    if target_date is None:
        target_date = date.today()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(total_calories), 0) as calories,
                COALESCE(SUM(total_protein), 0) as protein,
                COALESCE(SUM(total_carbs), 0) as carbs,
                COALESCE(SUM(total_fat), 0) as fat,
                COUNT(*) as meal_count
            FROM meals
            WHERE meal_date = $1
        """, target_date)
        return dict(row) if row else {"calories": 0, "protein": 0, "carbs": 0, "fat": 0, "meal_count": 0}

async def get_nutrition_summary(pool) -> Tuple[str, None]:
    totals = await get_daily_totals(pool)
    async with pool.acquire() as conn:
        targets = await conn.fetchrow("SELECT * FROM nutrition_targets LIMIT 1")
    
    if totals['meal_count'] == 0:
        return "Nicio masă logată azi\\.", None
    
    lines = ["🍽 *Nutriție azi*\n"]
    
    if targets:
        cal_pct = int(totals['calories'] / targets['calories'] * 100)
        prot_pct = int(totals['protein'] / targets['protein_g'] * 100)
        
        cal_bar = "█" * min(cal_pct // 10, 10) + "░" * max(10 - cal_pct // 10, 0)
        prot_bar = "█" * min(prot_pct // 10, 10) + "░" * max(10 - prot_pct // 10, 0)
        
        lines += [
            f"🔥 Calorii: `{cal_bar}` *{int(totals['calories'])}/{targets['calories']}* kcal",
            f"💪 Proteină: `{prot_bar}` *{totals['protein']:.0f}/{targets['protein_g']}g*",
            f"🍞 Carbs: *{totals['carbs']:.0f}g* · 🫒 Grăsimi: *{totals['fat']:.0f}g*",
        ]
        
        prot_remaining = float(targets['protein_g']) - float(totals['protein'])
        if prot_remaining > 5:
            lines.append(f"\n→ Mai ai nevoie de *{prot_remaining:.0f}g proteină*")
    else:
        lines += [
            f"🔥 Calorii: *{int(totals['calories'])}* kcal",
            f"💪 Proteină: *{totals['protein']:.0f}g*",
            f"🍞 Carbs: *{totals['carbs']:.0f}g* · 🫒 Grăsimi: *{totals['fat']:.0f}g*",
        ]
    
    return "\n".join(lines), None

async def handle_nutrition_intent(pool, intent: str, data: Dict[str, Any], bot=None) -> Tuple[str, None]:
    
    if intent == "meal_log":
        items = data.get("items", [])
        meal_type = data.get("meal_type", "masa")
        description = data.get("description")
        
        if not items:
            return "Spune-mi ce ai mâncat și cantitățile aproximative\\.", None
        
        return await log_meal(pool, meal_type, items, description)
    
    elif intent == "nutrition_summary":
        return await get_nutrition_summary(pool)
    
    elif intent == "nutrition_target":
        async with pool.acquire() as conn:
            targets = await conn.fetchrow("SELECT * FROM nutrition_targets LIMIT 1")
        if not targets:
            return "Nu ai setat targeturi nutriționale\\.", None
        
        return (
            f"🎯 *Targeturi zilnice*\n\n"
            f"🔥 Calorii: *{targets['calories']}* kcal\n"
            f"💪 Proteină: *{targets['protein_g']}g*\n"
            f"🍞 Carbs: *{targets['carbs_g']}g*\n"
            f"🫒 Grăsimi: *{targets['fat_g']}g*"
        ), None
    
    return "Nu am înțeles cererea legată de nutriție\\.", None

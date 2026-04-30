# modules/nutrition.py

from typing import Dict, Any, Tuple
from bot.formatter import safe_markdown
from datetime import date
import re
import db.queries.nutrition as nutrition_queries


def parse_meal_text(text: str) -> Dict[str, Any] | None:
    """
    Fast regex parser for meal_log intents.
    Returns dict with 'meal_type', 'description', 'items', 'calories', etc.
    """
    original = text.strip().lower()

    # Determine meal type based on time keywords
    meal_type = "masa"
    if any(w in original for w in ["mic dejun", "breakfast", "dimineața", "dejun"]):
        meal_type = "mic_dejun"
    elif any(w in original for w in ["prânz", "pranz", "lunch", "amiază"]):
        meal_type = "pranz"
    elif any(w in original for w in ["cină", "cina", " dinner", "seară"]):
        meal_type = "cina"
    elif any(w in original for w in ["gustare", "snack", "nun", "pauză"]):
        meal_type = "gustare"

    # Extract items with quantities
    items = []

    # Pattern: "3 oua", "80 gr de kaiser", "2 felii paine"
    quantity_pattern = r"(\d+(?:[.,]\d+)?)\s*(kg|g|gr|ml|l|felii|buche)?\s*(?:de\s+)?(.+?)(?=\d+\s*(?:kg|g|gr|ml|l|felii|buche)|$)"

    for m in re.finditer(quantity_pattern, text, re.IGNORECASE):
        qty = m.group(1).replace(",", ".")
        unit = (m.group(2) or "buc").lower()
        food = m.group(3).strip()

        if food and len(food) > 1:
            # Convert to grams
            qty_num = float(qty)
            if unit in ["kg", "k"]:
                qty_num *= 1000
            elif unit in ["l", "litri"]:
                qty_num *= 1000
            elif unit in ["ml"]:
                pass
            elif unit in ["g", "gr"]:
                pass
            elif unit in ["felii", "buc", "buche"]:
                # Estimate 30g per felie/buc
                qty_num *= 30

            items.append({"name": food, "quantity_g": qty_num})

    if not items:
        # Fallback: just use the whole description
        return {
            "meal_type": meal_type,
            "description": text,
            "items": [],
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
        }

    # Rough calorie estimation per item
    calories_per_100g = {
        "oua": 155,
        "ou": 155,
        "kaiser": 290,
        "carnati": 250,
        "paine": 265,
        "paine alba": 280,
        "lapte": 42,
        "cereale": 350,
        "iaurt": 59,
        "unt": 717,
        "branza": 300,
        "sunca": 120,
        "rosii": 18,
        "castraveti": 15,
        "salata": 20,
        "cartofi": 77,
        "orez": 130,
        "paste": 131,
        "carne": 200,
        "pui": 165,
        "porc": 242,
        "vita": 250,
    }

    total_cal = 0
    total_prot = 0
    total_carbs = 0
    total_fat = 0

    for item in items:
        food_lower = item["name"].lower()
        cal_per_100g = 100  # default
        for key, val in calories_per_100g.items():
            if key in food_lower:
                cal_per_100g = val
                break

        qty_factor = item["quantity_g"] / 100
        item_cal = cal_per_100g * qty_factor
        total_cal += item_cal
        total_prot += item_cal * 0.15 / 4  # ~15% protein, 4 cal/g
        total_carbs += item_cal * 0.45 / 4  # ~45% carbs
        total_fat += item_cal * 0.40 / 9  # ~40% fat, 9 cal/g

    return {
        "meal_type": meal_type,
        "description": text,
        "items": items,
        "calories": round(total_cal),
        "protein": round(total_prot, 1),
        "carbs": round(total_carbs, 1),
        "fat": round(total_fat, 1),
    }


async def handle_nutrition_intent(
    pool, intent: str, data: Dict[str, Any], bot=None
) -> Tuple[str, Any, Optional[int]]:
    """Main router for nutrition-related intents."""

    if intent == "meal_log":
        meal_type = data.get("meal_type", "masa")
        description = data.get("description", "Masă fără descriere")

        total_cal = float(data.get("calories", 0))
        total_prot = float(data.get("protein", 0))
        total_carbs = float(data.get("carbs", 0))
        total_fat = float(data.get("fat", 0))

        items_data = data.get("items", [])
        found_items = []
        for item in items_data:
            found_items.append(
                {
                    "name": item.get("name", "Unknown"),
                    "quantity_g": float(item.get("quantity_g", 0)),
                    "calories": float(item.get("calories", 0)),
                    "protein": float(item.get("protein", 0)),
                    "carbs": float(item.get("carbs", 0)),
                    "fat": float(item.get("fat", 0)),
                }
            )

        await nutrition_queries.log_meal(
            pool,
            date.today(),
            meal_type,
            {
                "calories": total_cal,
                "protein": total_prot,
                "carbs": total_carbs,
                "fat": total_fat,
            },
            description,
            found_items,
        )

        day_totals = await nutrition_queries.get_daily_totals(pool, date.today())
        targets = await nutrition_queries.get_nutrition_targets(pool)

        lines = [f"🍽 *{meal_type.replace('_', ' ').title()}* inregistrat!"]
        lines.append(
            f"🔥 *{int(total_cal)}* kcal | 💪 *{total_prot:.1f}g* P | 🍞 *{total_carbs:.1f}g* C | 🫒 *{total_fat:.1f}g* F"
        )

        lines.append("")
        cal_pct = int((day_totals["calories"] / targets["calories"]) * 100)
        cal_bar = "█" * min(cal_pct // 10, 10) + "░" * max(10 - cal_pct // 10, 0)
        lines.append(
            f"📊 *Total azi:* {int(day_totals['calories'])}/{targets['calories']} kcal"
        )
        lines.append(f"🔥 `{cal_bar}` {cal_pct}%")

        prot_pct = int((day_totals["protein"] / targets["protein_g"]) * 100)
        prot_bar = "█" * min(prot_pct // 10, 10) + "░" * max(10 - prot_pct // 10, 0)
        lines.append(
            f"💪 Proteina: `{prot_bar}` {int(day_totals['protein'])}/{targets['protein_g']}g"
        )

        cal_rem = targets["calories"] - int(day_totals["calories"])
        if cal_rem > 0:
            lines.append(f"\n🍴 Mai poti consuma *{cal_rem}* kcal azi.")
        else:
            lines.append("\n⚠️ Ai depasit targetul de calorii pe azi.")

        return safe_markdown("\n".join(lines)), None, None

    elif intent == "nutrition_summary":
        day_totals = await nutrition_queries.get_daily_totals(pool, date.today())
        targets = await nutrition_queries.get_nutrition_targets(pool)
        meals = await nutrition_queries.get_daily_meals(pool, date.today())

        if day_totals["calories"] == 0:
            return safe_markdown("Nu ai logat nicio masă azi. 🍎"), None

        lines = ["🍽 *Nutriție Azi*\n"]
        
        # Add list of meals
        for m in meals:
            desc = m.get("description", "Masă")
            # Truncate long descriptions
            if len(desc) > 40:
                desc = desc[:37] + "..."
            lines.append(f"• `{int(m['total_calories'])} kcal` — {desc}")
        
        lines.append("")
        lines.append(
            f"🔥 Calorii: *{int(day_totals['calories'])}* / {targets['calories']} kcal"
        )
        lines.append(
            f"💪 Proteina: *{day_totals['protein']:.1f}* / {targets['protein_g']}g"
        )
        lines.append(f"🍞 Carbs: *{day_totals['carbs']:.1f}* / {targets['carbs_g']}g")
        lines.append(f"🫒 Grasimi: *{day_totals['fat']:.1f}* / {targets['fat_g']}g")

        cal_pct = min(int((day_totals["calories"] / targets["calories"]) * 100), 100)
        prot_pct = min(int((day_totals["protein"] / targets["protein_g"]) * 100), 100)

        cal_bar = "█" * (cal_pct // 10) + "░" * (10 - (cal_pct // 10))
        prot_bar = "█" * (prot_pct // 10) + "░" * (10 - (prot_pct // 10))

        # Insert bars after total lines
        # Total calories is at lines index (len(meals) + 2)
        idx_cal = len(meals) + 2
        lines.insert(idx_cal + 1, f"🔥 `{cal_bar}` {cal_pct}%")
        
        # Protein is 2 lines after calorie bar
        idx_prot = idx_cal + 3
        lines.insert(idx_prot + 1, f"💪 `{prot_bar}` {prot_pct}%")

        return safe_markdown("\n".join(lines)), None, None

    elif intent == "nutrition_target":
        targets = await nutrition_queries.get_nutrition_targets(pool)
        return safe_markdown(
            f"🎯 *Targeturi Zilnice*\n\n"
            f"🔥 Calorii: *{targets['calories']}* kcal\n"
            f"💪 Proteina: *{targets['protein_g']}g*\n"
            f"🍞 Carbs: *{targets['carbs_g']}g*\n"
            f"🫒 Grasimi: *{targets['fat_g']}g*"
        ), None, None

    return safe_markdown("Nu am inteles cererea legata de nutritie. 🤔"), None, None

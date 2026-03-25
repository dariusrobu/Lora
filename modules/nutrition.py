# modules/nutrition.py

from typing import Dict, Any, Tuple
from bot.formatter import safe_markdown
from datetime import date
import db.queries.nutrition as nutrition_queries


async def handle_nutrition_intent(
    pool, intent: str, data: Dict[str, Any], bot=None
) -> Tuple[str, None]:
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
                    "calories": 0,
                    "protein": 0,
                    "carbs": 0,
                    "fat": 0,
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

        return safe_markdown("\n".join(lines)), None

    elif intent == "nutrition_summary":
        day_totals = await nutrition_queries.get_daily_totals(pool, date.today())
        targets = await nutrition_queries.get_nutrition_targets(pool)

        if day_totals["calories"] == 0:
            return safe_markdown("Nu ai logat nicio masa azi. 🍎"), None

        lines = ["🍽 *Nutritie Azi*\n"]
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

        cal_bar = "█" * (cal_pct // 10) + "░" * (10 - cal_pct // 10)
        prot_bar = "█" * (prot_pct // 10) + "░" * (10 - prot_pct // 10)

        lines.insert(2, f"🔥 `{cal_bar}` {cal_pct}%")
        lines.insert(5, f"💪 `{prot_bar}` {prot_pct}%")

        return safe_markdown("\n".join(lines)), None

    elif intent == "nutrition_target":
        targets = await nutrition_queries.get_nutrition_targets(pool)
        return safe_markdown(
            f"🎯 *Targeturi Zilnice*\n\n"
            f"🔥 Calorii: *{targets['calories']}* kcal\n"
            f"💪 Proteina: *{targets['protein_g']}g*\n"
            f"🍞 Carbs: *{targets['carbs_g']}g*\n"
            f"🫒 Grasimi: *{targets['fat_g']}g*"
        ), None

    return safe_markdown("Nu am inteles cererea legata de nutritie. 🤔"), None

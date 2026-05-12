from typing import Dict, Any, Tuple, Optional
from datetime import date
import io
import traceback
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from bot.formatter import escape_md, safe_markdown
import db.queries.health as health_queries


async def handle_health_intent(
    pool, intent: str, data: Dict[str, Any], bot=None
) -> Tuple[str, Any, Optional[int]]:
    today = date.today()

    if intent in [
        "health_log",
        "log_health",
        "log_sleep",
        "log_weight",
        "log_nutrition",
        "nutrition_log",
    ]:
        return await _handle_upsert(pool, intent, data, today)

    elif intent == "log_cigarettes":
        count = data.get("cigarettes") or 1
        new_total = await health_queries.add_cigarettes(pool, today, count)
        
        msg = f"✅ \\+{count} țigări adăugate\\.\n🚬 *Total azi:* {new_total}"
        log = await health_queries.get_health_log(pool, today)
        return msg, None, log["id"] if log else None

    elif intent == "log_water":
        water_ml = data.get("water_ml") or data.get("amount_ml")
        if not water_ml:
            return "Câți ml ai băut? 💧", None, None

        new_total = await health_queries.add_water(pool, today, water_ml)
        target = await _get_water_target(pool)
        pct = min(int((new_total / target) * 100), 100)
        bar = "█" * (pct // 10) + "░" * (10 - (pct // 10))

        msg = f"✅ \\+{water_ml}ml adăugați\\.\n💧 *Total azi:* {new_total}/{target}ml\n`{bar}` {pct}\\%"
        # We use today's log ID for undo. add_water doesn't return the ID, but we can fetch it or just not support undo for water yet.
        # Actually, let's get the ID if we want to support undo.
        log = await health_queries.get_health_log(pool, today)
        return msg, None, log["id"] if log else None

    elif intent == "health_status_today":
        log = await health_queries.get_health_log(pool, today)
        cigs = log.get("cigarettes", 0) if log else 0
        return f"🚬 Azi ai fumat *{cigs}* țigări până acum\\.", None, None

    elif intent == "health_summary":
        res_text, res_markup = await _generate_health_summary_text(pool)
        return res_text, res_markup, None

    elif intent == "health_chart":
        res_text, res_markup = await _generate_health_chart(pool)
        return res_text, res_markup, None

    elif intent == "view_today_logs":
        res_text, res_markup = await _generate_today_logs_text(pool)
        return res_text, res_markup, None

    return (
        escape_md("Nu sunt sigură cum să procesez această cerere pentru sănătate. 🤔"),
        None,
        None,
    )


async def handle_health_callback(query, pool, data: str) -> None:
    from core.state import set_state, clear_state

    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    try:
        if action == "summary":
            text, markup = await _generate_health_summary_text(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif action == "chart":
            result, _ = await _generate_health_chart(pool)
            if isinstance(result, io.BytesIO):
                await query.message.reply_photo(
                    photo=result,
                    caption="Health Trends 📊 \\(ultimele 30 zile\\)",
                    parse_mode="MarkdownV2",
                )
            else:
                await query.message.reply_text(result)

        elif action == "today_logs":
            text, markup = await _generate_today_logs_text(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif action == "log_water":
            await set_state(pool, "awaiting_health_input", "health", "log_water", None)
            prompt = "💧 *Câți ml ai băut?*\n_\\(ex: am băut 500ml, 1\\.5L, \\+250\\)_"
            await query.edit_message_text(prompt, parse_mode="MarkdownV2")
            await _save_prompt_to_conversation(pool, prompt)

        elif action == "log_sleep":
            await set_state(pool, "awaiting_health_input", "health", "log_sleep", None)
            prompt = "😴 *Câte ore ai dormit?*\n_\\(ex: 8 ore, somn bun, 7h30\\)_"
            await query.edit_message_text(prompt, parse_mode="MarkdownV2")
            await _save_prompt_to_conversation(pool, prompt)

        elif action == "log_weight":
            await set_state(pool, "awaiting_health_input", "health", "log_weight", None)
            prompt = "⚖️ *Care e greutatea ta azi?*\n_\\(ex: 74\\.5kg, am 75\\)_"
            await query.edit_message_text(prompt, parse_mode="MarkdownV2")
            await _save_prompt_to_conversation(pool, prompt)

        elif action == "log_nutrition":
            await set_state(
                pool, "awaiting_health_input", "health", "log_nutrition", None
            )
            prompt = "🍎 *Ce ai mâncat azi?*\n_\\(ex: 2 ouă și o felie de pâine, am mâncat un măr, prânz: pui cu orez 200g\\)_"
            await query.edit_message_text(prompt, parse_mode="MarkdownV2")
            await _save_prompt_to_conversation(pool, prompt)

        elif action == "log_cigarettes":
            await set_state(
                pool, "awaiting_health_input", "health", "log_cigarettes", None
            )
            prompt = "🚬 *Câte țigări ai fumat?*\n_\\(ex: 1, 5, am fumat 3\\)_"
            await query.edit_message_text(prompt, parse_mode="MarkdownV2")
            await _save_prompt_to_conversation(pool, prompt)

        elif action == "cancel":
            await clear_state(pool)
            text, markup = await _generate_health_summary_text(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )
            await query.answer("Anulat.")

    except Exception as e:
        print(f"ERROR in handle_health_callback: {e}")
        traceback.print_exc()
        await query.answer("A apărut o eroare.")
        await query.message.reply_text("A apărut o eroare. Te rog să încerci din nou.")


async def handle_health_message(update, pool, state: dict, text: str) -> None:
    from core.state import clear_state
    import re

    action = state.get("action")

    try:
        data = {}

        if action == "log_water":
            match = re.search(r"(\d+)\s*ml", text.lower())
            if match:
                data["water_ml"] = int(match.group(1))
            elif "l" in text.lower():
                match = re.search(r"([\d.]+)\s*l", text.lower())
                if match:
                    data["water_ml"] = int(float(match.group(1)) * 1000)

        elif action == "log_sleep":
            match = re.search(r"(\d+)\s*[.,]?(\d*)\s*h", text.lower())
            if match:
                hours = int(match.group(1))
                minutes = int(match.group(2) or "0")
                data["sleep_hours"] = hours + minutes / 60
            else:
                match = re.search(r"(\d+)", text)
                if match:
                    data["sleep_hours"] = int(match.group(1))

            for quality in ["great", "good", "neutral", "bad", "terrible"]:
                if quality in text.lower():
                    data["sleep_quality"] = quality
                    break

        elif action == "log_weight":
            match = re.search(r"([\d.]+)\s*kg", text.lower())
            if match:
                data["weight_kg"] = float(match.group(1))

        elif action == "log_cigarettes":
            match = re.search(r"(\d+)", text)
            if match:
                data["cigarettes"] = int(match.group(1))

        elif action == "log_nutrition":
            items = _parse_meal_text(text)
            if items:
                from modules.nutrition import handle_nutrition_intent

                meal_data = {
                    "meal_type": "masa",
                    "description": text,
                    "calories": sum(i.get("calories", 0) for i in items),
                    "protein": sum(i.get("protein", 0) for i in items),
                    "carbs": sum(i.get("carbs", 0) for i in items),
                    "fat": sum(i.get("fat", 0) for i in items),
                    "items": items,
                }
                reply, _, _ = await handle_nutrition_intent(pool, "meal_log", meal_data)
                await update.message.reply_text(reply, parse_mode="MarkdownV2")
                await clear_state(pool)
                return
            else:
                reply, _, _ = await handle_health_intent(pool, "health_log", {})
                await update.message.reply_text(reply, parse_mode="MarkdownV2")
                await clear_state(pool)
                return

        reply, _, _ = await handle_health_intent(pool, "health_log", data)
        await update.message.reply_text(reply, parse_mode="MarkdownV2")
        await clear_state(pool)

    except Exception as e:
        print(f"ERROR in handle_health_message: {e}")
        traceback.print_exc()
        await update.message.reply_text("A apărut o eroare. Te rog să încerci din nou.")


async def _handle_upsert(
    pool, intent: str, data: Dict[str, Any], log_date: date
) -> Tuple[str, Any, Optional[int]]:
    nutrition = data.get("nutrition")
    weight_kg = data.get("weight_kg")
    cigarettes = data.get("cigarettes")
    notes = data.get("notes")

    log_id = await health_queries.upsert_health_log(
        pool,
        log_date,
        sleep_hours=sleep_hours,
        sleep_quality=sleep_quality,
        water_ml=water_ml,
        nutrition=nutrition,
        weight_kg=weight_kg,
        cigarettes=cigarettes,
        notes=notes,
    )

    parts = []
    if sleep_hours is not None:
        parts.append(f"somn {sleep_hours}h ✓")
    if water_ml is not None:
        parts.append(f"apă {water_ml}ml ✓")
    if weight_kg is not None:
        parts.append(f"{weight_kg}kg ✓")
    if nutrition is not None:
        parts.append(f"nutriție: {nutrition} ✓")
    if cigarettes is not None:
        parts.append(f"țigări: {cigarettes} ✓")

    msg = "✅ Health logat: " + " + ".join(parts)
    return escape_md(msg), None, log_id


FOOD_MACROS = {
    "oua": {"calories": 155, "protein": 13, "carbs": 1.1, "fat": 11, "unit": "100g"},
    "ou": {"calories": 155, "protein": 13, "carbs": 1.1, "fat": 11, "unit": "100g"},
    "sunca": {"calories": 120, "protein": 17, "carbs": 0, "fat": 5, "unit": "100g"},
    "paine": {"calories": 265, "protein": 9, "carbs": 49, "fat": 3, "unit": "100g"},
    "pâine": {"calories": 265, "protein": 9, "carbs": 49, "fat": 3, "unit": "100g"},
    "lapte": {"calories": 42, "protein": 3.4, "carbs": 5, "fat": 1, "unit": "100ml"},
    "branza": {"calories": 98, "protein": 11, "carbs": 3.4, "fat": 4, "unit": "100g"},
    "Unt": {"calories": 717, "protein": 1, "carbs": 0, "fat": 81, "unit": "100g"},
    "carne": {"calories": 200, "protein": 26, "carbs": 0, "fat": 10, "unit": "100g"},
    "pui": {"calories": 165, "protein": 31, "carbs": 0, "fat": 3.6, "unit": "100g"},
    "oreez": {"calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3, "unit": "100g"},
    "cartofi": {"calories": 77, "protein": 2, "carbs": 17, "fat": 0.1, "unit": "100g"},
    "mar": {"calories": 52, "protein": 0.3, "carbs": 14, "fat": 0.2, "unit": "100g"},
    "banana": {"calories": 89, "protein": 1.1, "carbs": 23, "fat": 0.3, "unit": "100g"},
    "iaurt": {"calories": 59, "protein": 10, "carbs": 3.6, "fat": 0.4, "unit": "100g"},
    "cascaval": {
        "calories": 350,
        "protein": 25,
        "carbs": 1.3,
        "fat": 27,
        "unit": "100g",
    },
}


def _parse_meal_text(text: str) -> list[dict]:
    """Parse Romanian meal text into items with macros."""
    import re

    items = []
    text = text.lower()

    food_pattern = r"(\d+(?:\.\d+)?)\s*(?:gr|g|kg|ml|l)?\s*(?:de\s+)?(\w+)"
    matches = re.findall(food_pattern, text)

    if not matches:
        word_pattern = r"(\d+)\s+(\w+)"
        matches = re.findall(word_pattern, text)

    for qty_str, food_name in matches:
        qty = float(qty_str)
        food_key = food_name.lower().rstrip(".,!?")

        if food_key in FOOD_MACROS:
            macros = FOOD_MACROS[food_key]
            unit = macros["unit"]

            if "100g" in unit or "100ml" in unit:
                factor = qty / 100
            elif "100" in unit:
                factor = qty / 100
            else:
                factor = 1

            items.append(
                {
                    "name": food_name.capitalize(),
                    "quantity_g": int(qty) if "g" in unit else int(qty * 1000),
                    "calories": macros["calories"] * factor,
                    "protein": macros["protein"] * factor,
                    "carbs": macros["carbs"] * factor,
                    "fat": macros["fat"] * factor,
                }
            )

    if not items:
        items.append(
            {
                "name": text[:30],
                "quantity_g": 100,
                "calories": 200,
                "protein": 10,
                "carbs": 25,
                "fat": 5,
            }
        )

    return items


async def _generate_health_summary_text(pool) -> Tuple[str, Any]:
    import db.queries.nutrition as nutrition_queries
    from bot.keyboards import health_summary_keyboard

    summary = await health_queries.get_health_summary(pool, 7)
    nutrition_today = await nutrition_queries.get_daily_totals(pool, date.today())
    targets = await nutrition_queries.get_nutrition_targets(pool)

    if not summary or summary.get("total_days", 0) == 0:
        return (
            safe_markdown(
                "Nu am destule date pentru un rezumat încă. Mai loghează câteva zile! 📊"
            ),
            health_summary_keyboard(),
        )

    avg_sleep = summary.get("avg_sleep", 0) or 0
    common_quality = summary.get("common_sleep_quality", "—")
    avg_water = summary.get("avg_water", 0) or 0
    max_water = summary.get("max_water", 0) or 0
    recent_weight = summary.get("recent_weight", "—")
    trend_emoji = (
        "↓"
        if summary.get("weight_trend") == "down"
        else "↑"
        if summary.get("weight_trend") == "up"
        else "→"
    )

    nutri_text = "Nicio masă azi."
    if nutrition_today["calories"] > 0:
        cal_pct = min(
            int((nutrition_today["calories"] / targets["calories"]) * 100), 100
        )
        nutri_text = f"{int(nutrition_today['calories'])}/{targets['calories']} kcal ({cal_pct}%) · {int(nutrition_today['protein'])}g P"

    text = (
        "📊 *Health — ultimele 7 zile*\n\n"
        f"😴 *Somn:* medie {avg_sleep:.1f}h · {common_quality}\n"
        f"💧 *Apă:* medie {int(avg_water)}ml · max {max_water}ml\n"
        f"⚖️ *Greutate:* {recent_weight}kg (trend: {trend_emoji})\n"
        f"🚬 *Țigări:* medie {summary.get('avg_cigarettes', 0):.1f}/zi · total {int(summary.get('total_cigarettes', 0))}\n"
        f"🍎 *Nutriție Azi:* {nutri_text}"
    )

    text = safe_markdown(text)
    return text, health_summary_keyboard()


async def _generate_health_chart(pool) -> Tuple[str, Any]:
    history = await health_queries.get_health_history(pool, 30)
    if len(history) < 3:
        return (
            safe_markdown(
                "Am nevoie de măcar 3 zile logate pentru a genera un grafic relevant. 📉"
            ),
            None,
        )

    dates = [row["log_date"] for row in history]
    sleep_vals = [
        float(row["sleep_hours"]) if row["sleep_hours"] else None for row in history
    ]
    water_vals = [row["water_ml"] if row["water_ml"] else 0 for row in history]
    weight_vals = [
        float(row["weight_kg"]) if row["weight_kg"] else None for row in history
    ]

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 15), sharex=True)
    plt.subplots_adjust(hspace=0.3)

    ax1.plot(
        dates, sleep_vals, color="#3498db", marker="o", linewidth=2, label="Somn (h)"
    )
    ax1.set_title("Somn (ore)", fontsize=14, pad=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylabel("Ore")

    ax2.bar(dates, water_vals, color="#2ecc71", alpha=0.7, label="Apă (ml)")
    ax2.set_title("Apă (ml)", fontsize=14, pad=10)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylabel("ml")

    weight_dates = [d for d, w in zip(dates, weight_vals) if w is not None]
    weight_clean = [w for w in weight_vals if w is not None]
    if weight_clean:
        ax3.plot(
            weight_dates,
            weight_clean,
            color="#e67e22",
            marker="s",
            linewidth=2,
            label="Greutate (kg)",
        )
        ax3.set_title("Greutate (kg)", fontsize=14, pad=10)
        ax3.grid(True, alpha=0.3)
        ax3.set_ylabel("kg")

    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    plt.xticks(rotation=45)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    buf.seek(0)
    plt.close(fig)

    return buf, "photo"


async def _generate_today_logs_text(pool) -> Tuple[str, Any]:
    import db.queries.nutrition as nutrition_queries
    from bot.keyboards import health_back_keyboard

    today = date.today()
    health = await health_queries.get_health_log(pool, today)
    meals = await nutrition_queries.get_daily_meals(pool, today)
    totals = await nutrition_queries.get_daily_totals(pool, today)

    if not health and not meals:
        return safe_markdown("Nu ai logat nimic pentru azi încă. 🍎💧"), None

    text = f"📜 *Jurnal Sănătate — {today.strftime('%d %b %Y')}*\n\n"

    if health:
        metrics = []
        if health.get("sleep_hours"):
            metrics.append(
                f"😴 *Somn:* {health['sleep_hours']}h ({health.get('sleep_quality', '—')})"
            )
        if health.get("water_ml"):
            metrics.append(f"💧 *Apă:* {health['water_ml']}ml")
        if health.get("weight_kg"):
            metrics.append(f"⚖️ *Greutate:* {health['weight_kg']}kg")
        if health.get("cigarettes"):
            metrics.append(f"🚬 *Țigări:* {health['cigarettes']}")
        if health.get("notes"):
            metrics.append(f"📝 *Note:* {health['notes']}")

        if metrics:
            text += "\n".join(metrics) + "\n\n"

    if meals:
        text += "🍎 *Mese:* \n"
        for i, m in enumerate(meals, 1):
            time_str = m["created_at"].strftime("%H:%M")
            text += f"{i}. `[{time_str}]` *{int(m['total_calories'])} kcal* — {m['description']}\n"

        text += f"\n🔥 *Total Calorii:* {int(totals['calories'])} kcal\n"
        text += f"📊 *Macros:* {int(totals['protein'])}g P · {int(totals['carbs'])}g C · {int(totals['fat'])}g F\n"
    else:
        text += "🍎 *Mese:* Nicio masă logată încă.\n"

    text = safe_markdown(text)
    return text, health_back_keyboard()


async def _get_water_target(pool) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT water_target_ml FROM user_profile LIMIT 1")
        if row and row["water_target_ml"]:
            return row["water_target_ml"]
    return 2500


async def _save_prompt_to_conversation(pool, prompt: str) -> None:
    """Saves the assistant's prompt to the history table for Gemini context."""
    from db.queries.history import save_message
    from core.config import TELEGRAM_USER_ID

    await save_message(pool, TELEGRAM_USER_ID, "assistant", prompt)


async def undo_last_action(pool, intent: str, item_id: int) -> Tuple[bool, str]:
    """Rolls back the last health log entry."""
    if not item_id:
        return False, "ID invalid."

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT log_date FROM health_logs WHERE id = $1", item_id
        )
        if not row:
            return False, "Log-ul de sănătate nu mai există."

    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM health_logs WHERE id = $1", item_id)
        return True, f"log-ul de sănătate din data de {row['log_date']}"
    except Exception as e:
        return False, str(e)

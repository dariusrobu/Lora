from bot.callback_utils import make_callback_data
from typing import Dict, Any, Tuple, Optional
from telegram import InlineKeyboardMarkup
from bot.formatter import escape_md
import db.queries.skills as skill_queries
from bot.keyboards import (
    skills_main_keyboard,
    skills_list_keyboard,
    skill_detail_keyboard,
    confirm_delete_skill_keyboard,
)


async def get_skills_dashboard(pool) -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the main skills overview."""
    skills = await skill_queries.get_all_skills(pool)

    if not skills:
        return (
            "✅ Nu ai skill\\-uri adăugate încă\\.",
            skills_list_keyboard([]),
        )

    lines = ["🧠 *Dashboard Skills*", "━━━━━━━━━━━━━━━━━━━━"]
    for s in skills:
        val = s.get("last_value")
        # Priority: last_metric (from log) > unit (from skill definition)
        unit = s.get("last_metric") or s.get("unit", "")
        streak = await skill_queries.get_skill_streak(pool, s["id"])
        streak_str = f" 🔥{streak}" if streak > 0 else ""

        name_esc = escape_md(s["name"])
        if val is not None:
            val_str = (
                f"{float(val):.0f}" if float(val) == int(val) else f"{float(val):.2f}"
            )
            # If the unit already starts with a number (like "589 ELO"), it's likely a data entry error
            # We'll try to show it cleanly.
            display_val = f"**{escape_md(val_str)}**"
            display_unit = escape_md(unit)

            lines.append(f"• *{name_esc}*: {display_val} {display_unit}{streak_str}")
        else:
            lines.append(f"• *{name_esc}*: _fără date_{streak_str}")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines), skills_main_keyboard()


async def get_skill_detail_view(
    pool, skill_id: int
) -> Tuple[str, InlineKeyboardMarkup]:
    skill = await skill_queries.get_skill_by_id(pool, skill_id)
    if not skill:
        return "❌ Eroare: Skill-ul nu mai există\\.", skills_main_keyboard()

    stats = await skill_queries.get_skill_stats(pool, skill_id)
    history = await skill_queries.get_skill_history(pool, skill_id, limit=5)

    title = escape_md(skill["name"])
    unit = escape_md(skill["unit"])

    streak = await skill_queries.get_skill_streak(pool, skill_id)

    avg_str = f"{stats['avg']:.2f}"
    max_str = f"{stats['max']:.2f}"
    trend_val = f"{abs(stats['trend']):.2f}"
    trend_icon = "📈" if stats["trend"] > 0 else "📉" if stats["trend"] < 0 else "➡️"

    lines = [
        f"📊 *{title}* \\({escape_md(skill['category'])}\\)",
        "━━━━━━━━━━━━━━━━━━━━",
        f"• *Streak*: {streak} 🔥" if streak > 0 else "• *Streak*: 0 ❄️",
        f"• *Medie*: {escape_md(avg_str)} {unit}",
        f"• *Best/Max*: {escape_md(max_str)} {unit}",
        f"• *Trend*: {trend_icon} {escape_md(trend_val)} {unit}\n",
        "*Istoric Recent:*",
    ]

    for h in history:
        date_str = h["log_date"].strftime("%d %b")
        h_unit = h.get("metric") or skill["unit"]
        val_str = (
            f"{float(h['value']):.0f}"
            if float(h["value"]) == int(h["value"])
            else f"{float(h['value']):.2f}"
        )
        lines.append(
            f"• {escape_md(date_str)}: {escape_md(val_str)} {escape_md(h_unit)}"
        )

    if not history:
        lines.append("_Nicio înregistrare încă_")

    return "\n".join(lines), skill_detail_keyboard(skill_id)


async def handle_skill_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Optional[InlineKeyboardMarkup], Optional[int]]:
    """NLP Entry point from Gemini."""
    if intent == "log_skill":
        name = data.get("skill_name")
        value = data.get("value")
        # Try to find skill
        skill = await skill_queries.get_skill_by_name(pool, name)
        if not skill:
            # Auto-create? No, better ask to create first or handle in state
            return (
                f"❌ Eroare: Nu am găsit skill-ul *{escape_md(name)}*\\.",
                None,
                None,
            )

        unit = data.get("unit") or skill["unit"]
        log_row = await skill_queries.log_skill_value(
            pool, skill["id"], float(value), metric=unit
        )
        return (
            f"✏️ Log înregistrat: *{escape_md(str(value))} {escape_md(unit)}* (Skill: *{escape_md(skill['name'])}*)\\.",
            None,
            log_row["id"],
        )

    elif intent == "view_skills":
        text, markup = await get_skills_dashboard(pool)
        return text, markup, None

    elif intent == "add_habit":
        name = data.get("name") or data.get("skill_name")
        frequency = data.get("frequency", "daily")
        if not name:
            return "⚠️ Atenție: Specifică un nume pentru habit.", None, None
        existing = await skill_queries.get_skill_by_name(pool, name)
        if existing:
            return (
                f"⚠️ Atenție: Habit-ul *{escape_md(name)}* există deja\\.",
                None,
                existing["id"],
            )
        unit = data.get("unit", "zile" if frequency == "daily" else "ori")
        new_skill = await skill_queries.add_skill(pool, name, unit)
        return (
            f"✅ Habit-ul *{escape_md(name)}* a fost adăugat cu succes\\.",
            None,
            new_skill["id"],
        )

    elif intent == "log_habit":
        name = data.get("name") or data.get("skill_name")
        value = data.get("value", 1)
        if not name:
            return (
                "⚠️ Atenție: Specifică habit-ul pentru care vrei să loghezi.",
                None,
                None,
            )
        skill = await skill_queries.get_skill_by_name(pool, name)
        if not skill:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Creează și bifează",
                            callback_data=make_callback_data(
                                "skills_create_confirm", name[:30], value
                            ),
                        ),
                        InlineKeyboardButton(
                            "❌ Anulează",
                            callback_data=make_callback_data("skills_cancel"),
                        ),
                    ]
                ]
            )
            return (
                rf"❌ Eroare: Nu am găsit habit\-ul *{escape_md(name)}*\.",
                keyboard,
                None,
            )
        log_row = await skill_queries.log_skill_value(
            pool, skill["id"], float(value), metric=skill.get("unit")
        )
        streak = await skill_queries.get_skill_streak(pool, skill["id"])
        streak_str = f" 🔥{streak}" if streak > 0 else ""
        return (
            rf"✅ Habit completat: *{escape_md(name)}*\. Streak: *{streak}* {streak_str}",
            None,
            log_row["id"],
        )

    elif intent == "list_habits":
        text, markup = await get_skills_dashboard(pool)
        return text, markup, None

    elif intent == "delete_habit":
        name = data.get("name") or data.get("skill_name")
        if not name:
            return "⚠️ Atenție: Specifică un habit pentru a-l șterge.", None, None
        skill = await skill_queries.get_skill_by_name(pool, name)
        if not skill:
            return (
                f"❌ Eroare: Nu am putut găsi habit-ul *{escape_md(name)}*\\.",
                None,
                None,
            )
        await skill_queries.delete_skill(pool, skill["id"])
        return f"🗑️ Habit-ul *{escape_md(name)}* a fost șters\\.", None, skill["id"]

    return "Intent necunoscut pentru Skills\\.", None, None

    return "Intent necunoscut pentru Skills\\.", None, None


async def handle_skills_callback(update, context, pool) -> None:
    """Router for skills_ callbacks."""
    query = update.callback_query
    data = query.data
    from core.state import set_state, clear_state

    try:
        if data == "skills_list":
            text, markup = await get_skills_dashboard(pool)
            await query.edit_message_text(
                text, reply_markup=markup, parse_mode="MarkdownV2"
            )

        elif data == "skills_log_list":
            skills = await skill_queries.get_all_skills(pool)
            text = "📝 *Selectează Skill pentru Log:*\n\nAlege skill\\-ul pentru care vrei să înregistrezi o valoare:"
            await query.edit_message_text(
                text,
                reply_markup=skills_list_keyboard(
                    skills, action_prefix="skills_log_entry_"
                ),
                parse_mode="MarkdownV2",
            )

        elif data == "skills_manage" or data == "skills_progress":
            # For now, these can both show the list, maybe with a different prefix if needed
            skills = await skill_queries.get_all_skills(pool)
            text = "⚙️ *Manage Skills:*\n\nAlege un skill pentru a\\-l edita sau sterge:"
            await query.edit_message_text(
                text, reply_markup=skills_list_keyboard(skills), parse_mode="MarkdownV2"
            )

        elif data.startswith("skills_detail_"):
            skill_id = int(data.split("_")[-1])
            text, markup = await get_skill_detail_view(pool, skill_id)
            await query.edit_message_text(
                text, reply_markup=markup, parse_mode="MarkdownV2"
            )

        elif data == "skills_add_new":
            await set_state(pool, "skills_add_name", "skills", "add", None)
            prompt = "➕ *Skill Nou*\n\nIntrodu numele skill\\-ului \\(ex: Sah, Duolingo, Rubik\\):"
            await query.edit_message_text(
                prompt,
                parse_mode="MarkdownV2",
            )
            await _save_prompt_to_conversation(pool, prompt)

        elif data.startswith("skills_log_entry_"):
            skill_id = int(data.split("_")[-1])
            skill = await skill_queries.get_skill_by_id(pool, skill_id)
            await set_state(pool, "skills_log_value", "skills", "log", skill_id)
            prompt = f"📝 *Log {escape_md(skill['name'])}*\n\nIntrodu valoarea \\({escape_md(skill['unit'])}\\):"
            await query.edit_message_text(
                prompt,
                parse_mode="MarkdownV2",
            )
            await _save_prompt_to_conversation(pool, prompt)

        elif data.startswith("skills_history_"):
            skill_id = int(data.split("_")[-1])
            history = await skill_queries.get_skill_history(pool, skill_id, limit=20)
            skill = await skill_queries.get_skill_by_id(pool, skill_id)
            lines = [f"📊 *Istoric Detaliat: {escape_md(skill['name'])}*\n"]
            for h in history:
                date_str = h["log_date"].strftime("%d %b %Y")
                val_str = (
                    f"{float(h['value']):.0f}"
                    if float(h["value"]) == int(h["value"])
                    else f"{float(h['value']):.2f}"
                )
                lines.append(
                    f"• {escape_md(date_str)}: {escape_md(val_str)} {escape_md(h['metric'] or skill['unit'])}"
                )
            if not history:
                lines.append("_Nicio înregistrare încă_")

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            back_markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ Înapoi",
                            callback_data=make_callback_data(
                                "skills", "detail", skill_id
                            ),
                        )
                    ]
                ]
            )
            await query.edit_message_text(
                "\n".join(lines), reply_markup=back_markup, parse_mode="MarkdownV2"
            )

        elif data.startswith("skills_delete_"):
            skill_id = int(data.split("_")[-1])
            await query.edit_message_text(
                "⚠️ Sigur vrei să ștergi acest skill și tot istoricul său?",
                reply_markup=confirm_delete_skill_keyboard(skill_id),
            )

        elif data.startswith("skills_confirm_delete_"):
            skill_id = int(data.split("_")[-1])
            await skill_queries.delete_skill(pool, skill_id)
            await query.answer("Skill șters!")
            text, markup = await get_skills_dashboard(pool)
            await query.edit_message_text(
                text, reply_markup=markup, parse_mode="MarkdownV2"
            )

        elif data == "skills_cancel":
            await clear_state(pool)
            text, markup = await get_skills_dashboard(pool)
            await query.edit_message_text(
                text, reply_markup=markup, parse_mode="MarkdownV2"
            )

        elif data.startswith("skill_create_confirm:"):
            parts = data.split(":")
            name = parts[1]
            value = float(parts[2]) if len(parts) > 2 and parts[2] else 1
            unit = "zile"
            await skill_queries.add_skill(pool, name, unit)
            skill = await skill_queries.get_skill_by_name(pool, name)
            await skill_queries.log_skill_value(pool, skill["id"], value, metric=unit)
            streak = await skill_queries.get_skill_streak(pool, skill["id"])
            streak_str = f" 🔥{streak}" if streak > 0 else ""
            await query.answer("✅ Creat și bifat!")
            await query.edit_message_text(
                rf"✅ Habit *{escape_md(name)}* creat și bifat\. Streak: *{streak}* {streak_str}",
                parse_mode="MarkdownV2",
            )

    except Exception as e:
        import logging

        logging.error(f"Error in skills callback: {e}")
        await query.answer("Eroare la procesarea cererii\\.")


async def handle_skills_message(update, context, pool, state: dict) -> bool:
    """Handles text input for skills state machine."""
    from core.state import set_state, clear_state

    msg_text = update.message.text.strip()
    state_type = state.get("state_type")

    try:
        if state_type == "skills_add_name":
            await set_state(
                pool, "skills_add_unit", "skills", "add", None, extra={"name": msg_text}
            )
            await update.message.reply_text(
                f"✅ Nume: *{escape_md(msg_text)}*\n\nAcum introdu unitatea de măsură \\(ex: elo, min, kg, puncte\\):",
                parse_mode="MarkdownV2",
            )
            return True

        elif state_type == "skills_add_unit":
            extra = state.get("extra") or {}
            name = extra.get("name")
            unit = msg_text
            await skill_queries.add_skill(pool, name, unit=unit)
            await clear_state(pool)
            text, markup = await get_skills_dashboard(pool)
            await update.message.reply_text(
                f"🎉 Skill\\-ul *{escape_md(name)}* a fost adăugat\\!",
                parse_mode="MarkdownV2",
            )
            await update.message.reply_text(
                text, reply_markup=markup, parse_mode="MarkdownV2"
            )
            return True

        elif state_type == "skills_log_value":
            skill_id = state.get("item_id")
            try:
                # Better parsing: extract first number, use rest as potential unit/metric override
                import re

                match = re.search(r"(\d+([.,]\d+)?)", msg_text)
                if not match:
                    raise ValueError("No number found")

                val = float(match.group(1).replace(",", "."))
                # Rest of text after the number could be the unit (e.g. "589 ELO" -> "ELO")
                remaining = msg_text.replace(match.group(1), "", 1).strip()
                metric = remaining if remaining else None

                await skill_queries.log_skill_value(pool, skill_id, val, metric=metric)
                await clear_state(pool)
                text, markup = await get_skill_detail_view(pool, skill_id)
                await update.message.reply_text(
                    "✅ Valoare înregistrată\\!", parse_mode="MarkdownV2"
                )
                await update.message.reply_text(
                    text, reply_markup=markup, parse_mode="MarkdownV2"
                )
                return True
            except (ValueError, IndexError):
                await update.message.reply_text(
                    "❌ Te rog introdu un număr valid (ex: 589, 74.5).",
                    parse_mode="MarkdownV2",
                )
                return True

    except Exception as e:
        import logging

        logging.error(f"Error in skills message: {e}")
        await update.message.reply_text(
            "❌ A apărut o eroare la salvarea datelor\\.", parse_mode="MarkdownV2"
        )
        await clear_state(pool)
        return True

    return False


async def skills_command(update, context) -> None:
    """/skills command handler."""
    pool = context.bot_data["pool"]
    try:
        text, markup = await get_skills_dashboard(pool)
        await update.message.reply_text(
            text, reply_markup=markup, parse_mode="MarkdownV2"
        )
    except Exception as e:
        import logging

        logging.error(f"Error in skills command: {e}")
        await update.message.reply_text(
            "Eroare la deschiderea dashboard-ului de skills\\.", parse_mode="MarkdownV2"
        )


async def _save_prompt_to_conversation(pool, prompt: str) -> None:
    """Saves the assistant's prompt to the history table for Gemini context."""
    from db.queries.history import save_message
    from core.config import TELEGRAM_USER_ID

    await save_message(pool, TELEGRAM_USER_ID, "assistant", prompt)


async def undo_last_action(pool, intent: str, item_id: int) -> Tuple[bool, str]:
    if not item_id:
        return False, "Nu s-a găsit ID-ul entității de anulat."

    try:
        if intent in ("log_skill", "log_habit"):
            await skill_queries.delete_skill_log(pool, item_id)
            return True, "Logarea progresului a fost anulată."
        elif intent == "add_habit":
            await skill_queries.delete_skill(pool, item_id)
            return True, "Adăugarea habit-ului a fost anulată."

        return False, f"Anularea nu este implementată pentru intentul '{intent}'."
    except Exception as e:
        return False, f"Eroare la anulare: {str(e)}"

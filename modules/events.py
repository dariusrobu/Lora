from typing import Dict, Any, Tuple
from datetime import datetime, timedelta
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import db.queries.events as event_queries
from bot.formatter import escape_md


async def handle_event_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any]:
    if intent == "add_event":
        title = data.get("title") or data.get("description") or data.get("name")
        date_str = data.get("event_date") or data.get("date")
        time_str = data.get("event_time") or data.get("time")
        remind_minutes = data.get("remind_before_minutes", 30)
        remind_1day = data.get("remind_1day", False)

        if not title or not date_str:
            return "Care este evenimentul și când este?", None

        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            event_time = None
            if time_str:
                event_time = datetime.strptime(time_str, "%H:%M").time()
        except Exception:
            return (
                "Nu am putut parse data sau ora. Te rog folosește formatul YYYY-MM-DD și HH:MM.",
                None,
            )

        if remind_1day:
            event_id = await event_queries.add_event_with_1day_reminder(
                pool,
                title=title,
                event_date=event_date,
                event_time=event_time,
                description=data.get("description") or title,
                is_recurring=data.get("is_recurring", False),
                remind_before_minutes=remind_minutes,
            )
        else:
            event_id = await event_queries.add_event(
                pool,
                title=title,
                event_date=event_date,
                event_time=event_time,
                description=data.get("description") or title,
                is_recurring=data.get("is_recurring", False),
                remind_before_minutes=remind_minutes,
            )

        time_msg = f" la {time_str}" if event_time else ""
        remind_msg = ""
        if remind_1day:
            remind_msg = " \\+ reminder 1 zi"
        elif remind_minutes:
            remind_msg = f" \\+ reminder {remind_minutes} min"

        return (
            f"Done ✅ Adăugat *{escape_md(title)}* pentru {escape_md(date_str)}{time_msg}{remind_msg}\\.",
            None,
        )

    elif intent == "list_events":
        events = await event_queries.list_events(pool, datetime.now().date())
        if not events:
            return "Nu ai evenimente viitoare\\.", None

        lines = ["📅 *Evenimente Viitoare:*"]
        from bot.formatter import format_date_short

        for e in events:
            time_str = (
                f" 🕒 {e['event_time'].strftime('%H:%M')}"
                if e["event_time"]
                else " 🕒 Toată ziua"
            )
            remind = (
                f" 🔔{e['remind_before_minutes']}"
                if e.get("remind_before_minutes")
                else ""
            )
            day_remind = " 📅" if e.get("remind_1day") else ""
            lines.append(
                f"• {time_str} — *{escape_md(e['title'])}* (`{format_date_short(e['event_date'])}`){remind}{day_remind}"
            )
        return "\n".join(lines), None

    elif intent == "edit_event_reminder":
        event_id = data.get("event_id")
        remind_minutes = data.get("remind_before_minutes")
        remind_1day = data.get("remind_1day")

        if not event_id:
            return "Ce eveniment vrei să editezi?", None

        if remind_minutes is not None:
            await event_queries.update_event_reminder(pool, event_id, remind_minutes)
            return f"Reminder actualizat la *{remind_minutes}* minute\\.", None

        if remind_1day is not None:
            all_events = await event_queries.list_events(
                pool, datetime.now().date() - timedelta(days=1)
            )
            event = next((e for e in all_events if e["id"] == event_id), None)
            if event:
                await event_queries.toggle_1day_reminder(
                    pool, event_id, event["event_date"], remind_1day
                )
                status = "activat" if remind_1day else "dezactivat"
                return f"Reminder 1 zi {status}\\.", None

        return "Trebuie să specifici reminder-ul\\.", None

    return "Event module is ready\\!", None


def get_reminder_keyboard(
    event_id: int, current_reminder: int = 30
) -> InlineKeyboardMarkup:
    """Returns inline keyboard for selecting reminder time."""
    buttons = [
        [
            InlineKeyboardButton(
                "30 min" if current_reminder != 30 else "✅ 30 min",
                callback_data=f"event_reminder:{event_id}:30",
            ),
            InlineKeyboardButton(
                "1 oră" if current_reminder != 60 else "✅ 1 oră",
                callback_data=f"event_reminder:{event_id}:60",
            ),
        ],
        [
            InlineKeyboardButton(
                "1 zi" if current_reminder != 1440 else "✅ 1 zi",
                callback_data=f"event_reminder:{event_id}:1440",
            ),
            InlineKeyboardButton(
                "Fără 🔕", callback_data=f"event_reminder:{event_id}:0"
            ),
        ],
    ]
    return InlineKeyboardMarkup(buttons)

import asyncio
from bot.callback_utils import make_callback_data
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import re
import db.queries.events as event_queries
from bot.formatter import escape_md, safe_markdown


def parse_add_event_text(text: str) -> Dict[str, Any] | None:
    """
    Fast regex parser for add_event intents.
    Returns dict with 'title', 'event_date', 'event_time' or None if no match.
    """
    original = text.strip()

    # Pattern: "add event at/la 17:00: fotbal" or "add event fotbal at 17:00"
    patterns = [
        r"(?:adaug|add|create)\s+(?:eveniment|event)\s+(?:la|at)?\s*(\d{1,2}:\d{2})\s*[:\-]?\s*(.+)$",
        r"(?:adaug|add|create)\s+(?:eveniment|event)\s+(.+?)\s+(?:la|at)\s*(\d{1,2}:\d{2})\s*$",
    ]

    for pattern in patterns:
        m = re.match(pattern, original, re.IGNORECASE)
        if m:
            groups = m.groups()
            if len(groups) == 2:
                # Figure out which is time and which is title
                if ":" in groups[0]:
                    return {
                        "event_time": groups[0],
                        "title": groups[1].strip(),
                        "event_date": datetime.now().strftime("%Y-%m-%d"),
                    }
                else:
                    return {
                        "title": groups[0].strip(),
                        "event_time": groups[1],
                        "event_date": datetime.now().strftime("%Y-%m-%d"),
                    }

    return None


def parse_reminder_text(text: str) -> Dict[str, Any] | None:
    """
    Parse reminder text like:
    - "add reminder today at 12:38 test reminder"
    - "reapă-mă mâine la 10:00 să îmi pregătesc rucsacul"
    - "amintește-mi duminică să verific mail-ul"

    Returns dict with 'title', 'date' (YYYY-MM-DD), 'time' (HH:MM) or None.
    """
    if not text:
        return None

    text = text.strip().lower()
    today = datetime.now().date()

    # Pattern to extract: "add reminder <date> at <time> <title>"
    # or: "reapă-mă <date> la <time> <title>"

    # Find time pattern (HH:MM or HH:MM:SS)
    time_match = re.search(r"(\d{1,2}):(\d{2})(?::\d{2})?", text)
    time_str = None
    if time_match:
        time_str = f"{time_match.group(1)}:{time_match.group(2)}"

    # Handle relative time: "în 2 ore", "peste 30 minute", "peste 1 oră"
    relative_time_match = re.search(
        r"în\s+(\d+)\s+(ore|oră|ore|minute|min)|"
        r"peste\s+(\d+)\s+(ore|oră|minute|min)|"
        r"după\s+(\d+)\s+(ore|oră|minute|min)",
        text,
        re.IGNORECASE,
    )
    if relative_time_match:
        now = datetime.now()
        # Extract number and unit
        for i in range(1, 6, 2):
            num = relative_time_match.group(i)
            unit = relative_time_match.group(i + 1)
            if num:
                num = int(num)
                if "or" in unit.lower():
                    target = datetime.now().replace(
                        second=0, microsecond=0
                    ) + timedelta(minutes=num * 60)
                else:
                    target = datetime.now().replace(
                        second=0, microsecond=0
                    ) + timedelta(minutes=num)
                time_str = target.strftime("%H:%M")
                # If target is in the past, add one day
                if target.date() == today and target.time() < now.time():
                    target = target + timedelta(days=1)
                date_str = target.strftime("%Y-%m-%d")
                break

    # Find date keywords and convert to date
    date_str = None

    if "azi" in text or "today" in text:
        date_str = today.strftime("%Y-%m-%d")
    elif "mâine" in text or "tomorrow" in text:
        date_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "poimâine" in text:
        date_str = (today + timedelta(days=2)).strftime("%Y-%m-%d")
    elif "duminică" in text:
        # Find next Sunday
        days_until_sunday = (6 - today.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        date_str = (today + timedelta(days=days_until_sunday)).strftime("%Y-%m-%d")
    elif "luni" in text:
        days_until = (0 - today.weekday()) % 7
        if days_until == 0:
            days_until = 7
        date_str = (today + timedelta(days=days_until)).strftime("%Y-%m-%d")
    elif "marți" in text:
        days_until = (1 - today.weekday()) % 7
        if days_until == 0:
            days_until = 7
        date_str = (today + timedelta(days=days_until)).strftime("%Y-%m-%d")
    elif "miercuri" in text:
        days_until = (2 - today.weekday()) % 7
        if days_until == 0:
            days_until = 7
        date_str = (today + timedelta(days=days_until)).strftime("%Y-%m-%d")
    elif "joi" in text:
        days_until = (3 - today.weekday()) % 7
        if days_until == 0:
            days_until = 7
        date_str = (today + timedelta(days=days_until)).strftime("%Y-%m-%d")
    elif "vineri" in text:
        days_until = (4 - today.weekday()) % 7
        if days_until == 0:
            days_until = 7
        date_str = (today + timedelta(days=days_until)).strftime("%Y-%m-%d")
    elif "sâmbătă" in text or "sambata" in text:
        days_until = (5 - today.weekday()) % 7
        if days_until == 0:
            days_until = 7
        date_str = (today + timedelta(days=days_until)).strftime("%Y-%m-%d")
    else:
        # Default to today if no date specified
        date_str = today.strftime("%Y-%m-%d")

    # Extract title - everything after the keywords
    # Remove common prefixes to get the title
    title = text
    for prefix in [
        "add reminder",
        "reapă-mă",
        "reapama",
        "amintește-mi",
        "amintește-mi ",
        "să mă reapă",
        "setez reminder",
    ]:
        title = title.replace(prefix, "").strip()

    # Remove date/time patterns from title
    title = re.sub(r"\d{1,2}:\d{2}(?::\d{2})?", "", title).strip()
    title = re.sub(
        r"(azi|astăzi|mâine|poimâine|duminică|luni|marți|miercuri|joi|vineri|sâmbătă)",
        "",
        title,
    ).strip()
    # Clean up common Romanian time prefixes
    title = re.sub(r"\b(la ora|la|ora|at)\b", "", title, flags=re.IGNORECASE).strip()
    # Normalize multiple spaces
    title = re.sub(r"\s+", " ", title).strip()

    # Clean up: remove trailing "test reminder" or similar
    # and get the meaningful part
    title = title.strip(":").strip()

    if not title:
        title = "Reminder"

    # Remove action verbs from title but keep original casing
    title = re.sub(r"^(să|sa|sa|pentru|că|ca)\s+", "", title, flags=re.IGNORECASE)

    return {"title": title, "date": date_str, "time": time_str}


async def handle_event_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any, Optional[int]]:
    if intent in ("add_event", "add_reminder"):
        is_reminder = intent == "add_reminder"

        # Try to get data from Gemini response first
        title = data.get("title") or data.get("description") or data.get("name")
        date_str = data.get("event_date") or data.get("date")
        time_str = data.get("event_time") or data.get("time")

        # If Gemini didn't extract data, parse from user message
        if not title or not date_str:
            user_msg = data.get("_user_message", "") or ""
            parsed = parse_reminder_text(user_msg)
            if parsed:
                title = parsed.get("title")
                date_str = parsed.get("date")
                time_str = parsed.get("time")

        # Option A: If time exists but NO date → use TODAY (implicit)
        if time_str and not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        remind_minutes = data.get("remind_before_minutes", 30) if not is_reminder else 0

        if not title or not date_str:
            return (
                "⚠️ Atenție: Care este evenimentul/reminder-ul și când este?",
                None,
                None,
            )

        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            event_time = None
            if time_str:
                try:
                    event_time = datetime.strptime(time_str, "%H:%M").time()
                except ValueError:
                    # Fallback for ISO times with seconds (Gemini often returns this)
                    try:
                        event_time = datetime.strptime(time_str, "%H:%M:%S").time()
                    except ValueError:
                        raise ValueError(f"Invalid time format: {time_str}")
        except Exception:
            return (
                "❌ Eroare: Nu am putut parsa data sau ora. Te rog folosește formatul YYYY-MM-DD și HH:MM.",
                None,
                None,
            )

        event_id = await event_queries.add_event(
            pool,
            title=title,
            event_date=event_date,
            event_time=event_time,
            description=data.get("description") or title,
            is_recurring=data.get("is_recurring", False),
            remind_before_minutes=remind_minutes,
            event_type="reminder" if is_reminder else "event",
        )

        # Immediate sync to iCloud
        try:
            from core.icloud import sync_events_table_to_calendar

            asyncio.create_task(sync_events_table_to_calendar(pool))
        except Exception as e:
            print(f"Error triggering immediate sync: {e}")

        time_msg = f" la {time_str}" if event_time else ""
        type_msg = "Reminder" if is_reminder else "Eveniment"
        return (
            f"✅ {type_msg} adăugat: *{escape_md(title)}* pentru {date_str}{time_msg}",
            None,
            event_id,
        )

    elif intent == "list_events":
        events = await event_queries.list_events(pool, datetime.now().date())
        if not events:
            return "⚠️ Atenție: Nu ai evenimente viitoare\\.", None, None

        lines = ["📅 *Evenimente Viitoare:*\n━━━━━━━━━━━━━━━━━━━━"]
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
        return "\n".join(lines), None, None

    elif intent == "list_reminders":
        reminders = await event_queries.list_reminders(pool)
        if not reminders:
            return "⚠️ Atenție: Nu ai reminder-e viitoare\\.", None, None

        lines = ["🔔 *Reminder-e Viitoare:*\n━━━━━━━━━━━━━━━━━━━━"]
        from bot.formatter import format_date_short

        for r in reminders:
            time_str = (
                f" la {r['event_time'].strftime('%H:%M')}" if r["event_time"] else ""
            )
            lines.append(
                f"• *{escape_md(r['title'])}* — {format_date_short(r['event_date'])}{time_str}"
            )
        return safe_markdown("\n".join(lines)), None, None

    elif intent in ("delete_event", "delete_reminder"):
        event_id = data.get("id") or data.get("event_id")
        title = data.get("title")

        if event_id:
            await event_queries.delete_event(pool, event_id)
            return "🗑️ Eveniment șters cu succes.", None, event_id

        if title:
            event_type = "reminder" if intent == "delete_reminder" else "event"
            await event_queries.delete_event_by_title(pool, title, event_type)
            return f"🗑️ Eveniment șters: *{escape_md(title)}*\\.", None, None

        return "⚠️ Atenție: Ce eveniment/reminder vrei să ștergi?", None, None

    elif intent == "edit_event_reminder":
        event_id = data.get("event_id")
        remind_minutes = data.get("remind_before_minutes")
        remind_1day = data.get("remind_1day")

        if not event_id:
            return "⚠️ Atenție: Ce eveniment vrei să editezi?", None, None

        if remind_minutes is not None:
            await event_queries.update_event_reminder(pool, event_id, remind_minutes)
            return (
                f"✏️ Reminder actualizat la *{remind_minutes}* minute\\.",
                None,
                event_id,
            )

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
                return f"✏️ Reminder de 1 zi a fost *{status}*\\.", None, event_id

        return "⚠️ Atenție: Trebuie să specifici reminder-ul.", None, None

    elif intent == "resend_reminder":
        title = data.get("title") or data.get("name")
        if not title:
            return "⚠️ Atenție: Care reminder vrei sa retrimiti?", None, None
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM events WHERE LOWER(title) = LOWER($1) AND event_type = 'reminder' ORDER BY id DESC LIMIT 1",
                title,
            )
            if not row:
                return (
                    f"❌ Eroare: Nu am gasit reminder-ul '{escape_md(title)}'.",
                    None,
                    None,
                )
            await conn.execute(
                "UPDATE events SET reminded_at = NULL WHERE id = $1", row["id"]
            )
        return (
            f"✅ Retrimis reminder: *{escape_md(title)}* \\(in max 5 min\\).",
            None,
            None,
        )

    return "❌ Eroare: Comanda invalidă pentru modulul events.", None, None


def get_reminder_keyboard(
    event_id: int, current_reminder: int = 30
) -> InlineKeyboardMarkup:
    """Returns inline keyboard for selecting reminder time."""
    buttons = [
        [
            InlineKeyboardButton(
                "30 min" if current_reminder != 30 else "✅ 30 min",
                callback_data=make_callback_data("event", "reminder", event_id, "30"),
            ),
            InlineKeyboardButton(
                "1 oră" if current_reminder != 60 else "✅ 1 oră",
                callback_data=make_callback_data("event", "reminder", event_id, "60"),
            ),
        ],
        [
            InlineKeyboardButton(
                "1 zi" if current_reminder != 1440 else "✅ 1 zi",
                callback_data=make_callback_data("event", "reminder", event_id, "1440"),
            ),
            InlineKeyboardButton(
                "Fără 🔕",
                callback_data=make_callback_data("event", "reminder", event_id, "0"),
            ),
        ],
    ]
    return InlineKeyboardMarkup(buttons)

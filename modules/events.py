from typing import Dict, Any, Tuple
from datetime import datetime
import db.queries.events as event_queries
from bot.formatter import escape_md

async def handle_event_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Any]:
    if intent == "add_event":
        # Handle flexible keys from Gemini
        title = data.get("title") or data.get("description") or data.get("name")
        date_str = data.get("event_date") or data.get("date")
        time_str = data.get("event_time") or data.get("time")
        
        if not title or not date_str: return "What's the event and when is it?", None
        
        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            event_time = None
            if time_str:
                event_time = datetime.strptime(time_str, "%H:%M").time()
        except Exception:
            return "I couldn't parse the date or time. Please use YYYY-MM-DD and HH:MM.", None
            
        await event_queries.add_event(
            pool, title=title, event_date=event_date, event_time=event_time, 
            description=data.get("description") or title, is_recurring=data.get("is_recurring", False)
        )
        time_msg = f" at {time_str}" if event_time else ""
        return f"Done ✅ Added *{escape_md(title)}* for {escape_md(date_str)}{time_msg}\\.", None

    elif intent == "list_events":
        events = await event_queries.list_events(pool, datetime.now().date())
        if not events: return "You have no upcoming events\\.", None
        
        lines = ["📅 *Evenimente Viitoare:*"]
        from bot.formatter import format_date_short
        for e in events:
            time_str = f" 🕒 {e['event_time'].strftime('%H:%M')}" if e['event_time'] else " 🕒 Toată ziua"
            lines.append(f"• {time_str} — *{escape_md(e['title'])}* (`{format_date_short(e['event_date'])}`)")
        return "\n".join(lines), None

    return "Event module is ready\\!", None

from typing import Dict, Any, Tuple
from datetime import datetime
import db.queries.habits as habit_queries
from bot.formatter import escape_md
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_habit_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Any]:
    """Handles habit-related intents and returns reply text + keyboard."""
    
    if intent == "add_habit":
        name = data.get("name") or data.get("title") or data.get("description")
        if not name:
            return "What habit should I add?", None
            
        habit_id = await habit_queries.add_habit(
            pool, 
            name=name,
            frequency=data.get("frequency", "daily"),
            target_days=data.get("target_days")
        )
        
        from bot.keyboards import habit_keyboard
        return f"Got it ✅ Added *{escape_md(name)}* to your habits\\.", habit_keyboard(habit_id)

    elif intent == "list_habits":
        habits = await habit_queries.list_habits(pool)
        if not habits:
            return "You haven't set up any habits yet\\.", None
            
        today_logged = await habit_queries.get_today_logs(pool)
        
        lines = ["✅ *Status Habit-uri Azi:*"]
        for h in habits:
            status = "✅" if h['id'] in today_logged else "⬜"
            streak = f" — Streak: *{h['streak_count']}* 🔥" if h['streak_count'] > 0 else ""
            lines.append(f"{status} *{escape_md(h['name'])}*{streak}")
            
        from bot.keyboards import habit_list_keyboard
        return "\n".join(lines), habit_list_keyboard(habits)

    elif intent == "log_habit":
        habit_id = data.get("id")
        search_name = str(data.get("name") or data.get("title") or data.get("query") or "")
        
        if not habit_id and search_name:
            if search_name.isdigit():
                habit_id = int(search_name)
            else:
                matches = await habit_queries.get_habits_by_name(pool, search_name)
                if len(matches) == 1:
                    habit_id = matches[0]['id']
                elif len(matches) > 1:
                    from bot.keyboards import habit_list_keyboard
                    return f"I found multiple habits named *{escape_md(search_name)}*. Which one are we logging?", habit_list_keyboard(matches)

        if not habit_id:
            # Maybe the user sent the name, but Gemini should resolve to ID
            return "Which habit are we logging?", None
            
        await habit_queries.log_habit(pool, habit_id, datetime.now().date(), "done")
        habit = await habit_queries.get_habit(pool, habit_id)
        
        streak_msg = f" Current streak: *{habit['streak_count']}* 🔥" if habit['streak_count'] > 0 else ""
        return f"Nice work\\! Logged *{escape_md(habit['name'])}* for today\\.{streak_msg}", None

    elif intent == "delete_habit":
        habit_id = data.get("id")
        search_name = str(data.get("name") or data.get("title") or data.get("query") or "")
        
        if not habit_id and search_name:
            if search_name.isdigit():
                habit_id = int(search_name)
            else:
                matches = await habit_queries.get_habits_by_name(pool, search_name)
                if len(matches) == 1:
                    habit_id = matches[0]['id']
                elif len(matches) > 1:
                    from bot.keyboards import habit_list_keyboard
                    return f"I found multiple habits named *{escape_md(search_name)}*. Which one do you want to delete?", habit_list_keyboard(matches)

        if not habit_id:
            return "Which habit should I delete?", None
            
        habit = await habit_queries.get_habit(pool, habit_id)
        if not habit:
            return "I couldn't find that habit\\.", None
            
        from core.state import set_state
        await set_state(pool, "awaiting_confirmation", "habits", "delete", habit_id)
        
        from bot.keyboards import confirmation_keyboard
        return f"Are you sure you want to delete the habit *{escape_md(habit['name'])}* and all its history?", confirmation_keyboard("habits", "delete", habit_id)

    return "I'm not sure how to handle that habit request yet\\.", None

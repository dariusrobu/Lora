from typing import Dict, Any, Tuple
from datetime import datetime
import db.queries.tasks as task_queries
from bot.formatter import escape_md
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_task_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Any]:
    """Handles task-related intents and returns reply text + keyboard."""
    
    if intent == "add_task":
        title = data.get("title")
        if not title:
            return "What task should I add?", None
            
        due_date_str = data.get("due_date")
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except:
                pass
        
        task_id = await task_queries.add_task(
            pool, 
            title=title,
            notes=data.get("notes"),
            priority=data.get("priority", "medium"),
            due_date=due_date,
            is_recurring=data.get("is_recurring", False),
            recurrence=data.get("recurrence")
        )
        
        from bot.keyboards import task_keyboard
        return f"Done ✅ Added *{escape_md(title)}*", task_keyboard(task_id)

    elif intent == "list_tasks":
        tasks = await task_queries.list_tasks(pool)
        if not tasks:
            return "You have no pending tasks! 🎉", None
            
        lines = ["📋 *Your Pending Tasks:*"]
        for t in tasks:
            due = f" (due {t['due_date']})" if t['due_date'] else ""
            priority = " 🔥" if t['priority'] == "high" else ""
            lines.append(f"• {escape_md(t['title'])}{due}{priority}")
            
        return "\n".join(lines), None

    elif intent == "complete_task":
        # Usually Gemini finds the ID or we get it from a button
        task_id = data.get("id")
        if not task_id:
            return "Which task would you like to complete?", None
            
        await task_queries.complete_task(pool, task_id)
        task = await task_queries.get_task(pool, task_id)
        return f"Completed ✅ *{escape_md(task['title'])}*", None

    elif intent == "delete_task":
        task_id = data.get("id")
        if not task_id:
            return "Which task should I delete?", None
            
        task = await task_queries.get_task(pool, task_id)
        if not task:
            return "I couldn't find that task.", None
            
        # For deletes, we should use confirmation
        from core.state import set_state
        await set_state(pool, "awaiting_confirmation", "tasks", "delete", task_id)
        
        from bot.keyboards import confirmation_keyboard
        return f"Are you sure you want to delete *{escape_md(task['title'])}*?", confirmation_keyboard("tasks", "delete", task_id)

    return "I'm not sure how to handle that task request yet.", None

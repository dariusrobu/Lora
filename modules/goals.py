from typing import Dict, Any, Tuple, Optional
from bot.formatter import escape_md, safe_markdown
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import db.queries.goals as goal_queries

async def handle_goal_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    if intent == "add_goal":
        title = data.get("title")
        description = data.get("description")
        deadline_str = data.get("deadline")
        
        from datetime import datetime
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date() if deadline_str else None
        
        goal = await goal_queries.create_goal(pool, title, description, deadline)
        return f"🎯 Obiectiv adăugat: *{escape_md(goal['title'])}*", None

    elif intent == "list_goals":
        goals = await goal_queries.list_goals(pool)
        if not goals:
            return "🎯 Nu ai obiective active momentan. Vrei să adăugăm unul?", None
        
        lines = ["🎯 *Obiectivele tale*", ""]
        for g in goals:
            deadline_info = f" — deadline: {g['deadline'].strftime('%d %b')}" if g['deadline'] else ""
            lines.append(f"*{escape_md(g['title'])}*{deadline_info}")
            
            # Progress bar
            progress = g['progress'] or 0
            filled = int(progress / 10)
            bar = "█" * filled + "░" * (10 - filled)
            lines.append(f"`{bar}` {progress}%")
            
            # Sub-tasks
            goal_data = await goal_queries.get_goal_with_tasks(pool, g['id'])
            for t in goal_data.get('tasks', []):
                status = "✅" if t['is_completed'] else "⬜"
                lines.append(f"{status} {escape_md(t['title'])}")
            lines.append("")
            
        return "\n".join(lines), None

    elif intent == "add_goal_task":
        goal_title = data.get("title")
        task_title = data.get("task_title")
        
        goal = await goal_queries.get_goal_by_title(pool, goal_title)
        if not goal:
            return f"❌ Nu am găsit obiectivul '{escape_md(goal_title)}'.", None
            
        await goal_queries.add_goal_task(pool, goal['id'], task_title)
        return f"✅ Sub-task adăugat la *{escape_md(goal['title'])}*: {escape_md(task_title)}", None

    elif intent == "complete_goal_task":
        goal_title = data.get("title")
        task_title = data.get("task_title")
        
        goal = await goal_queries.get_goal_by_title(pool, goal_title)
        if not goal:
            return f"❌ Nu am găsit obiectivul '{escape_md(goal_title)}'.", None
            
        task = await goal_queries.get_goal_task_by_title(pool, goal['id'], task_title)
        if not task:
            return f"❌ Nu am găsit sub-task-ul '{escape_md(task_title)}' în obiectivul *{escape_md(goal['title'])}*.", None
            
        await goal_queries.complete_goal_task(pool, task['id'])
        
        # Get updated goal to show new progress
        updated_goal = await goal_queries.get_goal_with_tasks(pool, goal['id'])
        return f"✅ Sub-task finalizat! Progres *{escape_md(updated_goal['title'])}*: {updated_goal['progress']}%", None

    elif intent == "update_goal":
        # Placeholder for other updates like deadline or status
        return "Am actualizat obiectivul.", None

    return "Această acțiune pentru goals nu este încă suportată.", None

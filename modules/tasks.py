from typing import Dict, Any, Tuple
from datetime import datetime
import db.queries.tasks as task_queries
from bot.formatter import escape_md
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_task_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Any]:
    """Handles task-related intents and returns reply text + keyboard."""
    
    if intent == "add_task":
        title = data.get("title") or data.get("description") or data.get("name") or data.get("text")
        if not title:
            # Fallback: if Gemini put the title in the reply or data is empty
            return "What task should I add? (I didn't catch the title)", None
            
        due_date_str = data.get("due_date")
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except:
                pass
        
        project_id = data.get("project_id") or data.get("id")
        project_name = data.get("project") or data.get("project_name")
        
        if not project_id and project_name:
            import db.queries.projects as project_queries
            # Get only active/on-hold projects for linking
            projects = await project_queries.list_projects(pool, exclude_status="archived")
            # Try exact match first
            match = next((p for p in projects if p['name'].lower() == project_name.lower()), None)
            # If no exact match, try partial match
            if not match:
                match = next((p for p in projects if project_name.lower() in p['name'].lower()), None)
            
            if match:
                project_id = match['id']
                # Update project_name to the matched one for the reply
                project_name = match['name']

        task_id = await task_queries.add_task(
            pool, 
            title=title,
            notes=data.get("notes"),
            priority=data.get("priority", "medium"),
            due_date=due_date,
            project_id=project_id,
            is_recurring=data.get("is_recurring", False),
            recurrence=data.get("recurrence")
        )
        
        from bot.keyboards import task_keyboard
        return f"Done ✅ Added *{escape_md(title)}*", task_keyboard(task_id)

    elif intent == "list_tasks":
        project_id = data.get("project_id")
        project_name = data.get("project") or data.get("project_name")
        
        if not project_id and project_name:
            import db.queries.projects as project_queries
            project = await project_queries.get_project_by_name(pool, project_name)
            if project:
                project_id = project['id']

        tasks = await task_queries.list_tasks(pool, project_id=project_id)
        if not tasks:
            msg = f"Momentan nu ai niciun task activ pentru proiectul *{escape_md(project_name)}*! 🎉" if project_name else "Felicitați! 🎉 Nu ai niciun task restant."
            return msg, None
            
        header = f"📋 *Task-uri {escape_md(project_name)}:*" if project_name else "📋 *Task-urile tale:* "
        lines = [header]
        from bot.formatter import format_date_short
        for t in tasks:
            due = f" 📅 `{format_date_short(t['due_date'])}`" if t['due_date'] else ""
            priority = " 🔥" if t['priority'] == "high" else ""
            # Prefix with ID for easier manual reference
            lines.append(f"• {escape_md(t['title'])}{due}{priority} (ID: `{t['id']}`)")
            
        from bot.keyboards import task_list_keyboard
        return "\n".join(lines), task_list_keyboard(tasks)

    elif intent == "complete_task":
        # Usually Gemini finds the ID or we get it from a button
        task_id = data.get("id")
        if not task_id:
            return "Which task would you like to complete?", None
            
        await task_queries.complete_task(pool, task_id)
        task = await task_queries.get_task(pool, task_id)
        return f"Completed ✅ *{escape_md(task['title'])}*", None

    elif intent == "edit_task":
        task_id = data.get("id")
        # Try to find task by search term if ID is missing
        search_term = str(data.get("query") or data.get("search") or data.get("old_title") or data.get("name") or "")
        
        if not task_id and search_term:
            if search_term.isdigit():
                task_id = int(search_term)
            else:
                matches = await task_queries.get_tasks_by_title(pool, search_term)
                if len(matches) == 1:
                    task_id = matches[0]['id']
                elif len(matches) > 1:
                    from bot.keyboards import task_list_keyboard
                    return f"I found multiple tasks matching *{escape_md(search_term)}*. Which one did you mean?", task_list_keyboard(matches)

        if not task_id:
            return "Which task should I edit?", None
        
        # Clean up data to only include valid update fields
        upd = {}
        # If Gemini provided 'new_title', use it. If it provided 'title' and we found the task via search_term, 'title' is likely the new one.
        new_title = data.get("new_title") or (data.get("title") if search_term else None)
        if new_title: upd['title'] = new_title
        
        for k in ['notes', 'priority', 'due_date']:
            if k in data: upd[k] = data[k]
        
        if not upd: return "What should I change about it? (e.g., 'Rename it to X' or 'Set priority to high')", None
        
        await task_queries.update_task(pool, task_id, **upd)
        task = await task_queries.get_task(pool, task_id)
        from bot.keyboards import task_keyboard
        return f"Updated ✅ *{escape_md(task['title'])}*", task_keyboard(task_id)

    elif intent == "delete_task":
        task_id = data.get("id")
        title = str(data.get("title") or data.get("name") or data.get("text") or data.get("query") or "")
        
        if not task_id and title:
            if title.isdigit():
                task_id = int(title)
            else:
                matches = await task_queries.get_tasks_by_title(pool, title)
                if len(matches) == 1:
                    task_id = matches[0]['id']
                elif len(matches) > 1:
                    from bot.keyboards import task_list_keyboard
                    return f"I found multiple tasks matching *{escape_md(title)}*. Which one did you mean?", task_list_keyboard(matches)
            # if 0 matches, we'll fall through to "Which task..."
            
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

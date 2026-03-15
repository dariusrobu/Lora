from typing import Dict, Any, Tuple
import db.queries.projects as project_queries
from bot.formatter import escape_md

async def handle_project_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Any]:
    if intent == "add_project":
        name = data.get("name")
        if not name: return "What should I call the project?", None
        
        project_id = await project_queries.add_project(
            pool, name=name, description=data.get("description"), status=data.get("status", "active")
        )
        return f"Done ✅ Created project *{escape_md(name)}*\\.", None

    elif intent == "list_projects":
        status_filter = data.get("status")
        projects = await project_queries.list_projects(pool, status=status_filter)
        
        if not projects:
            msg = f"You have no *{escape_md(status_filter)}* projects\\." if status_filter else "You have no active projects\\."
            return msg, None
        
        header = f"🏗 *Upcoming/Active Projects:*" if not status_filter else f"🏗 *{status_filter.title()} Projects:*"
        lines = [header]
        for p in projects:
            status_str = f" ({p['status']})" if p['status'] != 'active' else ""
            lines.append(f"• *{escape_md(p['name'])}*{status_str}")
        return "\n".join(lines), None

    elif intent == "archive_project":
        project_id = data.get("id")
        name = data.get("name")
        
        if not project_id and name:
            project = await project_queries.get_project_by_name(pool, name)
            if project: project_id = project['id']
            
        if not project_id: return "Which project should I archive?", None
        
        project = await project_queries.get_project(pool, project_id)
        if not project: return "I couldn't find that project\\.", None
        
        await project_queries.archive_project(pool, project_id)
        return f"Project *{escape_md(project['name'])}* has been archived 📦\\. All tasks are still there, but it won't show in your active list\\.", None

    elif intent == "delete_project":
        project_id = data.get("id")
        if not project_id: return "Which project should I delete?", None
        
        project = await project_queries.get_project(pool, project_id)
        if not project: return "I couldn't find that project\\.", None
        
        from core.state import set_state
        await set_state(pool, "awaiting_confirmation", "projects", "delete", project_id)
        
        from bot.keyboards import confirmation_keyboard
        return f"Are you sure you want to delete project *{escape_md(project['name'])}*?\\nTasks linked to it will NOT be deleted\\.", confirmation_keyboard("projects", "delete", project_id)

    return "Project module is ready\\! (Phase 5 continues)", None

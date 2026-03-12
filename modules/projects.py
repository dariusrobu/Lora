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
        projects = await project_queries.list_projects(pool)
        if not projects: return "You have no active projects\\.", None
        
        lines = ["🏗 *Your Active Projects:*"]
        for p in projects:
            status = f" ({p['status']})" if p['status'] != 'active' else ""
            lines.append(f"• *{escape_md(p['name'])}*{status}")
        return "\n".join(lines), None

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

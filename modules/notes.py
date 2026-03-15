from typing import Dict, Any, Tuple
import db.queries.notes as note_queries
from bot.formatter import escape_md

async def handle_note_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Any]:
    if intent == "add_note":
        content = data.get("content")
        if not content: return "Ce anume vrei să notez? ✍️", None
        
        project_id = data.get("project_id")
        project_name = data.get("project") or data.get("project_name")
        
        if not project_id and project_name:
            import db.queries.projects as project_queries
            project = await project_queries.get_project_by_name(pool, project_name)
            if project:
                project_id = project['id']
                
        note_id = await note_queries.add_note(
            pool, content=content, type=data.get("type", "note"), 
            tags=data.get("tags", []), project_id=project_id
        )
        type_label = "Jurnalizat" if data.get("type") == "journal" else "Am salvat"
        project_msg = f" pentru proiectul *{escape_md(project_name)}*" if project_name else ""
        return f"{type_label}{project_msg} ✅\n\n{escape_md(content)}", None
 
    elif intent == "list_notes":
        type_filter = data.get("type")
        project_id = data.get("project_id")
        project_name = data.get("project") or data.get("project_name")
        
        if not project_id and project_name:
            import db.queries.projects as project_queries
            project = await project_queries.get_project_by_name(pool, project_name)
            if project:
                project_id = project['id']
                
        notes = await note_queries.list_notes(pool, type=type_filter, project_id=project_id)
        if not notes:
            msg = f"Nu ai nicio notiță pentru *{escape_md(project_name)}*\\." if project_name else "Nu ai nicio notiță salvată\\."
            return msg, None
        
        if project_name:
            header = f"📓 *Notițe {escape_md(project_name)}:*"
        elif type_filter == "journal":
            header = "📖 *Jurnalul tău:* "
        else:
            header = "📓 *Notițele tale:* "
        
        lines = [header]
        for n in notes:
            emoji = "📖" if n['type'] == "journal" else "📄"
            summary = n['content'][:50] + "..." if len(n['content']) > 50 else n['content']
            lines.append(f"• {emoji} {escape_md(summary)}")
        return "\n".join(lines), None

    elif intent == "search_notes":
        query = data.get("query")
        if not query: return "Ce anume să caut? 🔍", None
        
        notes = await note_queries.search_notes(pool, query)
        if not notes: return f"Nu am găsit nicio notiță care să conțină `{escape_md(query)}`\\.", None
        
        lines = [f"🔍 *Rezultate pentru '{escape_md(query)}':*"]
        for n in notes:
            emoji = "📖" if n['type'] == "journal" else "📄"
            summary = n['content'][:60] + "..." if len(n['content']) > 60 else n['content']
            lines.append(f"• {emoji} {escape_md(summary)}")
        return "\n".join(lines), None

    return "Note module is ready\\!", None

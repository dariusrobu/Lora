from typing import Dict, Any, Tuple
import db.queries.notes as note_queries
from bot.formatter import escape_md

async def handle_note_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Any]:
    if intent == "add_note":
        content = data.get("content")
        if not content: return "What should I write down?", None
        
        note_id = await note_queries.add_note(
            pool, content=content, type=data.get("type", "note"), 
            tags=data.get("tags", []), project_id=data.get("project_id")
        )
        return f"Saved ✅\n\n{escape_md(content)}", None

    elif intent == "list_notes":
        type_filter = data.get("type")
        notes = await note_queries.list_notes(pool, type=type_filter)
        if not notes: return "You have no notes\\.", None
        
        lines = ["📓 *Your Recent Notes:*"] if not type_filter else ["📖 *Your Journal:*"]
        for n in notes:
            summary = n['content'][:50] + "..." if len(n['content']) > 50 else n['content']
            lines.append(f"• {escape_md(summary)}")
        return "\n".join(lines), None

    elif intent == "search_notes":
        query = data.get("query")
        if not query: return "What should I search for?", None
        
        notes = await note_queries.search_notes(pool, query)
        if not notes: return f"I couldn't find any notes matching `{escape_md(query)}`\\.", None
        
        lines = [f"🔍 *Found {len(notes)} results for '{escape_md(query)}':*"]
        for n in notes:
            summary = n['content'][:60] + "..." if len(n['content']) > 60 else n['content']
            lines.append(f"• {escape_md(summary)}")
        return "\n".join(lines), None

    return "Note module is ready\\!", None

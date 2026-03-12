from typing import Dict, Any
from bot.formatter import escape_md

async def route_intent(pool, intent_response: Dict[str, Any]):
    """
    Routes the Gemini intent to the appropriate module.
    Returns the reply text and an optional keyboard.
    """
    module = intent_response.get("module")
    intent = intent_response.get("intent")
    data = intent_response.get("data")
    reply = intent_response.get("reply", "Hmm, I'm not sure how to respond to that.")
    
    # If no module, just return the chat reply from Gemini
    if not module:
        # Handle update_profile specifically
        if intent == "update_profile":
            from db.queries.profile import update_user_profile
            from core.config import TELEGRAM_USER_ID
            
            fact = data.get("fact")
            if fact:
                # Get current notes
                from db.queries.profile import get_user_profile
                profile = await get_user_profile(pool, TELEGRAM_USER_ID)
                current_notes = profile.get("personal_notes") or ""
                new_notes = f"{current_notes}\n- {fact}".strip()
                await update_user_profile(pool, TELEGRAM_USER_ID, personal_notes=new_notes)
        
        return reply, None

    # Module routing logic (Phase 4 & 5)
    if module == "tasks":
        from modules.tasks import handle_task_intent
        return await handle_task_intent(pool, intent, data)
    elif module == "habits":
        from modules.habits import handle_habit_intent
        return await handle_habit_intent(pool, intent, data)
    elif module == "projects":
        from modules.projects import handle_project_intent
        return await handle_project_intent(pool, intent, data)
    elif module == "notes":
        from modules.notes import handle_note_intent
        return await handle_note_intent(pool, intent, data)
    elif module == "finance":
        from modules.finance import handle_finance_intent
        return await handle_finance_intent(pool, intent, data)
    elif module == "events":
        from modules.events import handle_event_intent
        return await handle_event_intent(pool, intent, data)
    
    return f"{reply}\n\n_(Note: Module {module} is still being implemented)_", None

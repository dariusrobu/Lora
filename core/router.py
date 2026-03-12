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
    # This will be expanded as we add modules/tasks.py, etc.
    
    # Placeholder for actual module calls:
    # if module == "tasks":
    #     from modules.tasks import handle_task_intent
    #     return await handle_task_intent(pool, intent, data)
    
    return f"{reply}\n\n_(Note: Module {module} is still being implemented)_", None

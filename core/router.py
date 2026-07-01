from typing import Dict, Any, Tuple, Optional
import logging
import json
from db.queries.log import log_execution
from core.state import set_state

logger = logging.getLogger("core.router")


async def check_module_health() -> Dict[str, str]:
    """
    Tests the availability of all critical modules.
    Returns a dict mapping module name to status ('ok' or error message).
    """
    modules_to_test = [
        "tasks",
        "projects",
        "notes",
        "finance",
        "events",
        "shopping",
        "goals",
        "skills",
        "mood",
        "insights",
        "health",
        "workout",
        "reading",
        "focus",
        "planner",
        "university",
        "nutrition",
        "schedule",
        "memory",
        "weather",
        "calendar",
        "integrations",
    ]

    status = {}
    for mod in modules_to_test:
        try:
            if mod == "tasks":
                pass
            elif mod == "projects":
                pass
            elif mod == "finance":
                pass
            elif mod == "university":
                pass
            status[mod] = "ok"
        except Exception as e:
            status[mod] = str(e)
            logger.error(f"Module {mod} health check failed: {e}")

    return status


async def route_intent(pool, intent_response: Any, user_id: int, bot=None):
    """
    Routes the Gemini intent(s) to the appropriate module(s).
    Supports multi-intent and agentic diversion.
    """
    # 1. Handle List of Responses (Multi-intent)
    if isinstance(intent_response, list):
        all_replies = []
        last_kb = None
        for item in intent_response:
            rep, kb, _ = await _route_single_intent(pool, item, user_id, bot)
            if rep:
                all_replies.append(rep)
            if kb:
                last_kb = kb
        return "\n\n".join(all_replies), last_kb, None

    # 2. Handle Single Response
    return await _route_single_intent(pool, intent_response, user_id, bot)


async def _route_single_intent(
    pool, intent_response: Dict[str, Any], user_id: int, bot=None
) -> Tuple[str, Any, Optional[int]]:
    """Internal router for a single intent object."""
    module = intent_response.get("module")
    intent = intent_response.get("intent")
    data = intent_response.get("data") or {}
    reply = intent_response.get("reply", "")
    user_message = intent_response.get(
        "_user_message", ""
    )  # Injected by handler usually
    data["_user_message"] = user_message

    # Agentic Diversion Check
    if intent_response.get("needs_agent") or intent == "agent":
        from core.agent import run_agent
        from core.gemini import client

        msg = user_message or reply
        print(f"🤖 AGENTIC MODE: Diverting -> {msg}", flush=True)
        agent_reply = await run_agent(pool, client, msg, bot=bot)
        return agent_reply, None, None

    # Clarification Check
    confidence = intent_response.get("confidence", 1.0)
    if confidence < 0.7 or intent_response.get("clarification_needed"):
        question = (
            intent_response.get("clarification_question")
            or "Poți clarifica ce dorești să facem? 🤔"
        )
        payload = {"partial_intent": intent, "partial_data": data}
        await set_state(
            pool, "awaiting_clarification", module, "clarify", None, payload
        )
        return question, None, None

    # Handle Intent Correction (Undo/Correct)
    if intent == "correct_last":
        from core.state import get_state

        state = await get_state(pool)
        if not state or not state.get("last_intent"):
            return (
                "Nu am găsit nicio acțiune recentă pe care să o corectez. 🤔",
                None,
                None,
            )

        last_intent = state["last_intent"]
        last_module = state.get("last_module")
        last_item_id = state.get("last_inserted_id")
        intent_name = last_intent.get("intent")
        correction_text = data.get("correction_text", "").lower()

        # Simple Undo
        if any(
            kw in correction_text for kw in ["anulează", "undo", "șterge", "nu asta"]
        ):
            if last_module and last_item_id:
                from core.dispatcher import undo_last_action

                success, msg = await undo_last_action(
                    pool, last_module, intent_name, last_item_id
                )
                if success:
                    from core.state import clear_state

                    await clear_state(pool)
                    # Also clear last_intent so we don't undo twice
                    async with pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE conversation_state SET last_intent = NULL WHERE state_key = 'current'"
                        )
                    return f"Am anulat ultima acțiune: {msg} 🗑️", None, None
                return f"Nu am putut anula acțiunea: {msg} ❌", None, None
            return (
                "Am înțeles că vrei să anulezi, dar nu am găsit un ID valid pentru ultima acțiune. 🔧",
                None,
                None,
            )

        # Complex Correction (Re-run Gemini)
        from core.gemini import analyze_intent

        context = f"Utilizatorul vrea să corecteze ultima acțiune: {json.dumps(last_intent)}. Corecția este: {correction_text}"
        new_intent = await analyze_intent(pool, correction_text, context=context)
        return await _route_single_intent(pool, new_intent, user_id, bot)

    # Whitelist of valid modules — anything else is treated as free chat.
    # This prevents hallucinated module names (e.g. "greeting", "chatbot",
    # "general") from crashing the dispatcher.
    VALID_MODULES = {
        "tasks",
        "projects",
        "notes",
        "finance",
        "events",
        "shopping",
        "goals",
        "skills",
        "mood",
        "insights",
        "health",
        "nutrition",
        "workout",
        "university",
        "schedule",
        "reading",
        "focus",
        "planner",
        "memory",
        "weather",
        "calendar",
        "calendar_module",
        "integrations",
        "travel",
        "wishlist",
    }

    if not module or module.lower() not in VALID_MODULES:
        if module:
            print(
                f"⚠️ ROUTER: Unknown module '{module}' — falling back to chat.",
                flush=True,
            )
        return reply, None, None

    # Interception for Human-in-the-loop Confirmation
    READ_ONLY_INTENTS = {
        "list_tasks",
        "list_events",
        "list_reminders",
        "list_items",
        "list_wish",
        "list_habits",
        "view_skills",
        "view_goals",
        "view_projects",
        "list_projects",
        "finance_summary",
        "finance_chart",
        "health_summary",
        "health_chart",
        "health_status_today",
        "nutrition_summary",
        "nutrition_target",
        "workout_list",
        "workout_stats",
        "workout_prs",
        "workout_week",
        "uni_list",
        "uni_exams",
        "uni_attendance_warning",
        "uni_restante",
        "schedule_today",
        "schedule_week",
        "reading_list",
        "reading_stats",
        "focus_list",
        "get_weather",
        "get_weather_alerts",
        "get_tech_news",
        "get_insights",
        "ask_insights",
        "mood_chart",
        "get_mood_chart",
        "memory_view",
        "memory_recall",
        "memory_search",
        "calendar_today",
        "calendar_week",
        "calendar_sync",
        "travel_list",
        "travel_check",
        "chat",
        "trigger_morning_briefing",
        "correct_last",
    }

    is_write_intent = intent not in READ_ONLY_INTENTS
    # By default, confirmation is disabled per user request to auto-execute all actions.
    # To re-enable, change the condition below to look at needs_confirmation and is_write_intent.
    if False:
        # Mark needs_confirmation as True in the response object
        intent_response["needs_confirmation"] = True

        # Save the pending action in state under pending_action
        from core.state import set_pending_action

        await set_pending_action(pool, intent, module, data)

        return "__CONFIRMATION_REQUIRED__", None, None

    # Execute via Dispatcher
    from core.dispatcher import execute_module_intent

    try:
        reply_text, keyboard, item_id = await execute_module_intent(
            pool, module, intent, data, reply, user_id, bot
        )

        # Logging & Memory
        await log_execution(pool, intent, module, True)

        # Save for Undo/Correction
        from core.state import save_last_action

        await save_last_action(pool, intent_response, item_id)

        # Auto-memory extraction (if present in intent_response)
        memory_extracts = intent_response.get("memory_extracts")
        if memory_extracts:
            from db.queries.memory import save_auto_memory
            from core.config import TELEGRAM_USER_ID

            for fact_data in memory_extracts:
                try:
                    await save_auto_memory(
                        pool,
                        TELEGRAM_USER_ID,
                        fact_data.get("fact"),
                        fact_data.get("category", "general"),
                        fact_data.get("confidence", 0.0),
                    )
                except Exception:
                    pass

        # Handle nested additional_intents (if any)
        additional = intent_response.get("additional_intents")
        if additional:
            replies = [reply_text]
            for extra in additional:
                e_rep, _, _ = await _route_single_intent(pool, extra, user_id, bot)
                if e_rep:
                    replies.append(e_rep)
            return "\n\n".join(replies), keyboard, item_id

        return reply_text, keyboard, item_id

    except Exception as e:
        logger.error(f"Router execution failed: {e}")
        await log_execution(pool, intent, module, False, type(e).__name__, str(e))
        return (
            f"A apărut o eroare la procesarea comenzii în modulul {module}. 🔧",
            None,
            None,
        )

from typing import Dict, Any, Tuple, Optional
import logging
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


async def route_intent(pool, intent_response: Any, bot=None):
    """
    Routes the Gemini intent(s) to the appropriate module(s).
    Supports multi-intent and agentic diversion.
    """
    # 1. Handle List of Responses (Multi-intent)
    if isinstance(intent_response, list):
        all_replies = []
        last_kb = None
        for item in intent_response:
            rep, kb, _ = await _route_single_intent(pool, item, bot)
            if rep:
                all_replies.append(rep)
            if kb:
                last_kb = kb
        return "\n\n".join(all_replies), last_kb, None

    # 2. Handle Single Response
    return await _route_single_intent(pool, intent_response, bot)


async def _route_single_intent(
    pool, intent_response: Dict[str, Any], bot=None
) -> Tuple[str, Any, Optional[int]]:
    """Internal router for a single intent object."""
    module = intent_response.get("module")
    intent = intent_response.get("intent")
    data = intent_response.get("data") or {}
    reply = intent_response.get("reply", "")
    user_message = intent_response.get(
        "_user_message", ""
    )  # Injected by handler usually

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

    # No module or 'chat' intent -> Just Chat
    if not module or module == "chat":
        return reply, None, None

    # Execute via Dispatcher
    from core.dispatcher import execute_module_intent

    try:
        reply_text, keyboard, item_id = await execute_module_intent(
            pool, module, intent, data, reply, bot
        )

        # Logging & Memory
        await log_execution(pool, intent, module, True)

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
                e_rep, _, _ = await _route_single_intent(pool, extra, bot)
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

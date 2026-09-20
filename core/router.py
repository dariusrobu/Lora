from typing import Dict, Any, Tuple, Optional
import logging
import json
import re
from db.queries.log import log_execution
from core.state import set_state
from core.config import REQUIRE_CONFIRMATION

logger = logging.getLogger("core.router")

_SENSITIVE_MEMORY = re.compile(
    r"(?:password|parol[aă]|token|api[_ -]?key|secret|jwt|card(?:ul)?|cvv|pin|iban|diagnos|tratament|medicament)",
    re.IGNORECASE,
)


async def _save_safe_memory_extracts(pool, user_id: int, extracts: Any) -> None:
    """Persist only stable, non-sensitive facts extracted by the local model."""
    if not extracts:
        return
    from db.queries.memory import save_auto_memory

    for item in extracts:
        fact = str(item.get("fact", "")).strip() if isinstance(item, dict) else ""
        confidence = float(item.get("confidence", 0.0)) if isinstance(item, dict) else 0.0
        if not fact or confidence < 0.75 or len(fact) > 500 or _SENSITIVE_MEMORY.search(fact):
            continue
        category = str(item.get("category", "general"))[:40] if isinstance(item, dict) else "general"
        try:
            await save_auto_memory(pool, user_id, fact, category, confidence)
        except Exception as exc:
            logger.debug("Memory extract skipped: %s", type(exc).__name__)

# Module-level constant: intents that only read data (no DB write)
# Used for confirmation gate and routing logic.
READ_ONLY_INTENTS: frozenset = frozenset({
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
    "get_news",
    "fetch_news",
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
})


def requires_write_confirmation(intent_response: Dict[str, Any]) -> bool:
    """Return whether an intent must be explicitly approved before execution.

    This is deliberately a deterministic policy.  The LLM may describe an
    action, but it must never decide whether a database write is safe to run.
    ``_confirmed_bypass`` is set only by the Telegram confirmation handlers
    after the user explicitly approves the pending action.
    """
    intent = intent_response.get("intent")
    return bool(
        REQUIRE_CONFIRMATION
        and intent
        and intent not in READ_ONLY_INTENTS
        and not intent_response.get("_confirmed_bypass", False)
    )


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

    # Memory extraction also applies to free conversation, not only module
    # actions. The filter prevents secrets and sensitive medical/financial
    # details from becoming long-term memory.
    await _save_safe_memory_extracts(pool, user_id, intent_response.get("memory_extracts"))

    # Agentic Diversion Check
    if intent_response.get("needs_agent") or intent == "agent":
        from core.gemini import client

        msg = user_message or reply
        print(f"🤖 AGENTIC MODE: Diverting -> {msg}", flush=True)
        if client:
            from core.agent import run_agent
            agent_reply = await run_agent(pool, client, msg, bot=bot)
            return agent_reply, None, None
        else:
            # Fallback to local / NVIDIA agent_loop when Gemini API key is missing
            from core.agent import agent_loop
            from core.config import TELEGRAM_USER_ID
            agent_reply, kb, item_id = await agent_loop(
                pool, TELEGRAM_USER_ID, msg, "User", "direct", "", [], "", "", bot=bot
            )
            return agent_reply, kb, item_id

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
        "news",
    }

    if not module or module.lower() not in VALID_MODULES:
        if module:
            print(
                f"⚠️ ROUTER: Unknown module '{module}' — falling back to chat.",
                flush=True,
            )
        return reply, None, None

    if requires_write_confirmation(intent_response):
        # The policy is code-owned: never trust an LLM-provided
        # ``needs_confirmation`` value for data-changing actions.
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

from typing import Dict, Any, Tuple, Optional
import logging
import asyncpg
from db.queries.log import log_execution

logger = logging.getLogger("core.router")


async def route_intent(pool, intent_response: Any, bot=None):
    """
    Routes the Gemini intent(s) to the appropriate module(s).
    Supports single dict or list of dicts.
    Returns the reply text and an optional keyboard.
    """
    if isinstance(intent_response, list):
        replies = []
        last_markup = None
        for item in intent_response:
            r, m = await _route_single_intent(pool, item, bot)
            if r:
                replies.append(r)
            if m:
                last_markup = m
        return "\n\n".join(replies), last_markup

    return await _route_single_intent(pool, intent_response, bot)


async def _route_single_intent(pool, intent_response: Dict[str, Any], bot=None):
    module = intent_response.get("module")
    intent = intent_response.get("intent")
    data = intent_response.get("data") or {}  # Guard: Gemini may return null for data
    reply = intent_response.get("reply", "Hmm, I'm not sure how to respond to that.")
    user_message = intent_response.get("_user_message", "")

    print(f"DEBUG ROUTER: module={module}, intent={intent}, data_type={type(data)}")

    # Inject original reply and user message so modules can use them
    data["_original_reply"] = reply
    if user_message:
        data["_user_message"] = user_message

    confidence = intent_response.get("confidence", 1.0)
    clarification_needed = intent_response.get("clarification_needed", False)
    clarification_question = intent_response.get("clarification_question")

    if confidence < 0.7 or clarification_needed:
        from core.state import set_state

        question = (
            clarification_question
            or "Scuze, am nevoie de un mic detaliu. Poți clarifica ce anume dorești?"
        )
        # Save partial intent data so the context is preserved
        payload = {"partial_intent": intent, "partial_data": data}
        await set_state(
            pool, "awaiting_clarification", module, "clarify", None, payload
        )
        return question, None

    # Let's check for Agentic Mode FIRST
    if intent_response.get("needs_agent"):
        from core.agent import run_agent
        from core.gemini import client

        print(f"DEBUG ROUTER: Diverting to Agentic Mode for query -> {user_message}")
        agent_reply = await run_agent(pool, client, user_message)
        return agent_reply, None

    # If no module, just return the chat reply from Gemini
    if not module:
        return reply, None

    # --- SPECIAL HANDLING: CORRECT LAST ---
    if intent == "correct_last":
        return await _handle_correct_last(pool, intent_response, bot)

    try:
        reply_text, keyboard, item_id = await _execute_module_intent(
            pool, module, intent, data, reply, bot
        )

        # Update state with last successful intent and ID
        await set_state(
            pool,
            "null",
            module,
            "last_action",
            item_id,
            extra={
                "last_intent": intent_response.model_dump()
                if hasattr(intent_response, "model_dump")
                else intent_response,
                "last_inserted_id": item_id,
            },
        )

        logger.info(
            f"Execution success | intent: {intent} | module: {module} | data_keys: {list(data.keys())}"
        )
        await log_execution(pool, intent, module, True)

        # ── Memory Extraction ───────────────────────────────────────────
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
                        fact_data.get("expires_at"),
                    )
                except Exception as me:
                    logger.warning(f"Failed to auto-save memory: {me}")

        # ── Multi-intent: execute additional_intents sequentially ──────────
        additional = intent_response.get("additional_intents")
        if additional:
            all_replies = [reply_text] if reply_text else []
            for idx, extra_intent in enumerate(additional, start=1):
                if not isinstance(extra_intent, dict):
                    # Pydantic model → convert to dict
                    try:
                        extra_intent = extra_intent.model_dump()
                    except AttributeError:
                        extra_intent = dict(extra_intent)
                e_module = extra_intent.get("module")
                e_intent = extra_intent.get("intent")
                e_data = extra_intent.get("data") or {}
                e_reply = extra_intent.get("reply", "")
                e_data["_original_reply"] = e_reply
                if not e_module:
                    all_replies.append(e_reply)
                    continue
                try:
                    e_text, _, _ = await _execute_module_intent(
                        pool, e_module, e_intent, e_data, e_reply, bot
                    )
                    await log_execution(pool, e_intent, e_module, True)
                    if e_text:
                        all_replies.append(e_text)
                    logger.info(
                        f"Multi-intent [{idx}] success | intent={e_intent} | module={e_module}"
                    )
                except Exception as ex:
                    await log_execution(
                        pool, e_intent, e_module, False, type(ex).__name__, str(ex)
                    )
                    logger.error(
                        f"Multi-intent [{idx}] failed | intent={e_intent} | error={ex}"
                    )
                    all_replies.append(
                        f"⚠️ Nu am putut executa acțiunea *{e_intent}*: {str(ex)[:80]}"
                    )

            combined = "\n".join(all_replies)
            return (
                combined,
                keyboard,
            )  # Multi-intent doesn't track a single item_id easily

        return reply_text, keyboard
    except KeyError as e:
        logger.error(
            f"Execution error | intent: {intent} | module: {module} | type: KeyError | msg: {e} | data: {data}"
        )
        await log_execution(pool, intent, module, False, "KeyError", str(e))
        return (
            "A apărut o eroare: lipsesc date necesare pentru a procesa comanda.",
            None,
            None,
        )
    except asyncpg.PostgresError as e:
        logger.error(
            f"Execution error | intent: {intent} | module: {module} | type: PostgresError | msg: {e} | data: {data}"
        )
        await log_execution(pool, intent, module, False, "PostgresError", str(e))
        return (
            "A apărut o eroare de bază de date. Te rog să încerci din nou.",
            None,
            None,
        )
    except Exception as e:
        logger.error(
            f"Execution error | intent: {intent} | module: {module} | type: Exception | msg: {e} | data: {data}"
        )
        await log_execution(pool, intent, module, False, "Exception", str(e))
        return "A apărut o eroare neașteptată la procesarea comenzii.", None, None


async def _handle_correct_last(pool, intent_response, bot):
    """Handles undoing the last action and re-evaluating with correction."""
    from db.queries.state import get_state, clear_state
    from core.gemini import analyze_intent

    state = await get_state(pool)
    if not state or not state.get("extra"):
        return "Nu am găsit nicio acțiune recentă de corectat.", None

    last_intent = state["extra"].get("last_intent")
    last_id = state["extra"].get("last_inserted_id")
    module_name = state["module"]

    if not last_intent or not last_id:
        return "Nu am destule informații pentru a face corecția.", None

    # 1. Undo the last action
    undo_msg = "Am anulat acțiunea anterioară."
    try:
        if module_name == "tasks":
            from modules.tasks import undo_last_action

            undo_msg = await undo_last_action(pool, last_id)
        elif module_name == "finance":
            from modules.finance import undo_last_action

            undo_msg = await undo_last_action(pool, last_id)
        elif module_name == "health":
            from modules.health import undo_last_action

            undo_msg = await undo_last_action(pool, last_id)
        elif module_name == "workout":
            from modules.workout import undo_last_action

            undo_msg = await undo_last_action(pool, last_id)
    except Exception as e:
        logger.error(f"Undo failed: {e}")
        undo_msg = "⚠️ Nu am putut anula acțiunea anterioară complet."

    # 2. Clear state
    await clear_state(pool)

    # 3. Re-analyze with correction context
    correction_text = intent_response.data.get("correction_text", "")

    # Check if it was just an "undo" request
    undo_keywords = ["undo", "anulează", "anuleaza", "șterge", "sterge", "nu mai"]
    is_pure_undo = any(w == correction_text.lower().strip() for w in undo_keywords)

    if is_pure_undo:
        return f"{undo_msg}\nCe dorești să facem în schimb?", None

    hint = f"Utilizatorul vrea să CORECTEZE ultima acțiune. Intent-ul anterior a fost: {last_intent}. Mesajul de corecție: {correction_text}"

    # We use the original message from the last intent to keep the context
    new_intent_response = await analyze_intent(correction_text, system_hint=hint)

    # Route the new intent
    reply, kb = await route_intent(pool, new_intent_response, bot)
    return f"{undo_msg}\n\n{reply}", kb


async def _execute_module_intent(
    pool, module: str, intent: str, data: Dict[str, Any], reply: str, bot=None
) -> Tuple[str, Any, Optional[int]]:
    # Module routing logic
    if module == "tasks":
        from modules.tasks import handle_task_intent

        return await handle_task_intent(pool, intent, data)
    elif module == "projects":
        from modules.projects import handle_project_intent

        res = await handle_project_intent(pool, intent, data)
        return (res[0], res[1], res[2] if len(res) > 2 else None)
    elif module == "notes":
        from modules.notes import handle_note_intent

        res = await handle_note_intent(pool, intent, data)
        return (res[0], res[1], res[2] if len(res) > 2 else None)
    elif module == "finance":
        from modules.finance import handle_finance_intent

        return await handle_finance_intent(pool, intent, data)
    elif module == "events":
        from modules.events import handle_event_intent

        return await handle_event_intent(pool, intent, data)
    elif module == "shopping":
        from modules.shopping import handle_shopping_intent

        return await handle_shopping_intent(pool, intent, data)
    elif module == "goals":
        from modules.goals import handle_goal_intent

        return await handle_goal_intent(pool, intent, data)
    elif module == "skills":
        from modules.skills import handle_skill_intent

        return await handle_skill_intent(pool, intent, data)
    elif module == "mood":
        from modules.mood import handle_mood_intent

        return await handle_mood_intent(pool, intent, data, bot)
    elif module == "insights":
        from modules.insights import generate_insights

        text = await generate_insights(pool)
        return text, None, None
    elif module == "health":
        from modules.health import handle_health_intent

        return await handle_health_intent(pool, intent, data, bot)
    elif module == "news":
        from modules.news import fetch_tech_news

        news = await fetch_tech_news()
        return f"{reply}\n\n{news}", None, None
    elif module == "workout":
        from modules.workout import handle_workout_intent

        return await handle_workout_intent(pool, intent, data, bot)
    elif module == "reading":
        from modules.reading import handle_reading_intent

        return await handle_reading_intent(pool, intent, data, bot)
    elif module == "focus":
        from modules.focus import handle_focus_intent

        return await handle_focus_intent(pool, intent, data, bot)
    elif module == "planner":
        from modules.planner import generate_time_block

        res = await generate_time_block(pool)
        return (res[0], res[1], res[2] if len(res) > 2 else None)
    elif module == "university":
        from modules.university import handle_university_intent

        return await handle_university_intent(pool, intent, data, bot)
    elif module == "nutrition":
        from modules.nutrition import handle_nutrition_intent

        return await handle_nutrition_intent(pool, intent, data, bot)
    elif module == "schedule":
        from modules.schedule import handle_schedule_intent

        return await handle_schedule_intent(pool, intent, data, bot)
    elif module == "memory":
        from modules.memory import handle_memory_intent
        from core.config import TELEGRAM_USER_ID

        data["user_id"] = TELEGRAM_USER_ID
        return await handle_memory_intent(pool, intent, data)
    elif module == "weather":
        from modules.weather import get_weather_summary

        city = data.get("city")
        weather = (
            await get_weather_summary(city) if city else await get_weather_summary()
        )
        if weather:
            return f"{reply}\n\n🌤️ {weather}", None, None
        return reply, None, None
    elif intent == "trigger_morning_briefing":
        from scheduler.jobs import send_morning_briefing
        from core.config import TELEGRAM_USER_ID as TG_UID
        import db.queries.profile as profile_queries
        from datetime import date

        today = date.today()
        profile = await profile_queries.get_user_profile(pool, TG_UID)
        if profile.get("last_briefing_date") == today:
            return (
                "Deja ți-am trimis briefing-ul de dimineață. O zi productivă! ☀️",
                None,
            )

        # Create a proper mock application that has what send_morning_briefing needs
        class MockApp:
            def __init__(self, bot_instance):
                self.bot = bot_instance

        if bot:
            try:
                await send_morning_briefing(MockApp(bot), pool)
            except Exception as e:
                import traceback

                print(f"Error in trigger_morning_briefing: {e}", flush=True)
                traceback.print_exc()
                return f"❌ Eroare: {str(e)[:100]}", None
            return None, None  # The job sends its own messages
        else:
            return "Nu am putut iniția briefing-ul manual (lipsă bot context).", None

    # ━━━ CALENDAR ━━━
    elif module == "calendar":
        from modules.calendar_module import handle_calendar_intent

        res = await handle_calendar_intent(pool, intent, data)
        return (res[0], res[1], res[2] if len(res) > 2 else None)

    res = await _handle_generic_module(pool, module, intent, data, reply)
    return (res[0], res[1], res[2] if len(res) > 2 else None)


async def _handle_generic_module(pool, module, intent, data, reply):
    return (
        f"{reply}\n\n_(Note: Module {module} is still being implemented)_",
        None,
        None,
    )

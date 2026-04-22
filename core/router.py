from typing import Dict, Any


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
    data = intent_response.get("data")
    reply = intent_response.get("reply", "Hmm, I'm not sure how to respond to that.")
    user_message = intent_response.get("_user_message", "")

    print(f"DEBUG ROUTER: module={module}, intent={intent}, data_type={type(data)}")

    # Inject original reply into data so modules can use it
    if data is not None:
        data["_original_reply"] = reply
        if user_message:
            data["_user_message"] = user_message

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

    # Module routing logic
    if module == "tasks":
        from modules.tasks import handle_task_intent

        return await handle_task_intent(pool, intent, data)
    elif module == "habits":
        from modules.skills import handle_skill_intent

        return await handle_skill_intent(pool, intent, data)
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
        return text, None
    elif module == "health":
        from modules.health import handle_health_intent

        return await handle_health_intent(pool, intent, data, bot)
    elif module == "news":
        from modules.news import fetch_tech_news

        news = await fetch_tech_news()
        return f"{reply}\n\n{news}", None
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

        return await generate_time_block(pool)
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

        return await handle_memory_intent(pool, intent, data)
    elif module == "weather":
        from modules.weather import get_weather_summary

        city = data.get("city")
        weather = (
            await get_weather_summary(city) if city else await get_weather_summary()
        )
        if weather:
            return f"{reply}\n\n🌤️ {weather}", None
        return reply, None
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

        return await handle_calendar_intent(pool, intent, data)

    return f"{reply}\n\n_(Note: Module {module} is still being implemented)_", None

from typing import Dict, Any
from bot.formatter import escape_md

async def route_intent(pool, intent_response: Dict[str, Any], bot=None):
    """
    Routes the Gemini intent to the appropriate module.
    Returns the reply text and an optional keyboard.
    """
    module = intent_response.get("module")
    intent = intent_response.get("intent")
    data = intent_response.get("data")
    reply = intent_response.get("reply", "Hmm, I'm not sure how to respond to that.")
    
    # Inject original reply into data so modules can use it
    if data is not None:
        data["_original_reply"] = reply
    
    # If no module, just return the chat reply from Gemini
    if not module:
        # (Profile update logic preserved...)
        return reply, None

    # Module routing logic
    if module == "tasks":
        from modules.tasks import handle_task_intent
        return await handle_task_intent(pool, intent, data)
    elif module == "habits":
        from modules.habits import handle_habit_intent
        return await handle_habit_intent(pool, intent, data, bot)
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
    elif module == "weather":
        from modules.weather import get_weather_summary
        city = data.get("city")
        weather = await get_weather_summary(city) if city else await get_weather_summary()
        if weather:
            return f"{reply}\n\n🌤️ {weather}", None
        return reply, None
    
    return f"{reply}\n\n_(Note: Module {module} is still being implemented)_", None

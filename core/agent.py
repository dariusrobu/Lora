# core/agent.py
import json
import re
from datetime import date, datetime, timedelta
from typing import Dict, Any, Tuple, Optional
import pytz
from db.queries.tasks import list_tasks
from db.queries.events import list_events
from db.queries.health import get_health_log
from db.queries.finance import (
    get_daily_transactions,
    get_monthly_summary,
    get_budget_status,
    get_monthly_category_totals,
)
from db.queries.goals import get_all_goals
from db.queries.university import list_subjects
from db.queries.notes import search_notes
from db.queries.shopping import list_shopping_items
from db.queries.focus import get_weekly_focus_stats
from db.queries.mood import get_monthly_mood_data
from db.queries.projects import list_projects
from db.queries.workout import get_recent_workouts
from db.queries.skills import get_all_skills
from db.queries.memory import semantic_search_memories, save_memory_fact
from db.queries.insights import get_insight_data

from core.config import TIMEZONE, TELEGRAM_USER_ID
import logging

logger = logging.getLogger("core.agent")

_BLOCKED_MEMORY = re.compile(
    r"(?:password|parol[aă]|token|api[_ -]?key|secret|jwt|cvv|pin|iban|diagnos|tratament|medicament)",
    re.IGNORECASE,
)


class _DisabledCloudType:
    """Compatibility placeholder for retired Gemini tool declarations.

    The local agent below does not use these declarations.  Keeping inert
    objects temporarily avoids importing the Google SDK while old helper code
    is progressively removed.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    @classmethod
    def from_text(cls, *args: Any, **kwargs: Any) -> "_DisabledCloudType":
        return cls()

    @classmethod
    def from_function_response(
        cls, *args: Any, **kwargs: Any
    ) -> "_DisabledCloudType":
        return cls()


class _DisabledCloudTypes:
    Tool = _DisabledCloudType
    GoogleSearch = _DisabledCloudType
    FunctionDeclaration = _DisabledCloudType
    Schema = _DisabledCloudType
    Content = _DisabledCloudType
    Part = _DisabledCloudType

    class Type:
        OBJECT = "OBJECT"
        STRING = "STRING"
        NUMBER = "NUMBER"
        INTEGER = "INTEGER"

    class GenerateContentConfig(_DisabledCloudType):
        pass


types = _DisabledCloudTypes()

# Tools definition for Gemini
# We use FunctionDeclaration for precise manual control over execution and DB pool injection.
agent_tools = types.Tool(
    google_search=types.GoogleSearch(),
    function_declarations=[
        types.FunctionDeclaration(
            name="tool_get_tasks",
            description="Returns pending tasks. You can optionally filter by project name.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "project_name": types.Schema(
                        type=types.Type.STRING,
                        description="Optional name of the project",
                    )
                },
            ),
        ),
        types.FunctionDeclaration(
            name="tool_get_events",
            description="Returns all events and calendar appointments for a specific date (YYYY-MM-DD).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "date": types.Schema(
                        type=types.Type.STRING,
                        description="Date in YYYY-MM-DD format (default is today)",
                    )
                },
            ),
        ),
        types.FunctionDeclaration(
            name="tool_get_health",
            description="Returns health metrics (sleep, water, nutrition, weight) for a specific date.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "date": types.Schema(
                        type=types.Type.STRING,
                        description="Date in YYYY-MM-DD format (default is today)",
                    )
                },
            ),
        ),
        types.FunctionDeclaration(
            name="tool_get_goals_progress",
            description="Returns the list of active goals and their current progress/subtasks.",
        ),
        types.FunctionDeclaration(
            name="tool_get_finance_summary",
            description="Returns expenses and total spendings for a specific period (today or a specific month).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "period": types.Schema(
                        type=types.Type.STRING,
                        description="Period to query: 'today' or 'current_month' (default is 'today')",
                    )
                },
            ),
        ),
        types.FunctionDeclaration(
            name="tool_get_budget_status",
            description="Returns current month spending vs budget limits for all categories that have a limit set.",
        ),
        types.FunctionDeclaration(
            name="tool_get_university_schedule",
            description="Returns the university schedule for a specific date (classes, seminars).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "date": types.Schema(
                        type=types.Type.STRING,
                        description="Date in YYYY-MM-DD format (default is today)",
                    )
                },
            ),
        ),
        types.FunctionDeclaration(
            name="tool_get_university_attendance",
            description="Returns subjects and current attendance stats.",
        ),
        types.FunctionDeclaration(
            name="tool_search_notes",
            description="Searches user's notes using full-text search. Returns matching notes with content, tags, and timestamps.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="Search query for notes content or tags",
                    )
                },
            ),
        ),
        types.FunctionDeclaration(
            name="tool_get_shopping_list",
            description="Returns all unbought items from the shopping list with categories.",
        ),
        types.FunctionDeclaration(
            name="tool_get_focus_stats",
            description="Returns focus session statistics for the current week including completed sessions, interrupted sessions, total minutes, and average duration.",
        ),
        types.FunctionDeclaration(
            name="tool_get_mood_trend",
            description="Returns mood tracking data for the current month showing daily mood values.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "days": types.Schema(
                        type=types.Type.INTEGER,
                        description="Number of days to look back (default 30)",
                    )
                },
            ),
        ),
        types.FunctionDeclaration(
            name="tool_get_projects",
            description="Returns all projects with their status, description, and creation date.",
        ),
        types.FunctionDeclaration(
            name="tool_get_workouts",
            description="Returns recent workouts with exercise details, duration, and sport type.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "days": types.Schema(
                        type=types.Type.INTEGER,
                        description="Number of days to look back (default 7)",
                    )
                },
            ),
        ),
        types.FunctionDeclaration(
            name="tool_get_skills",
            description="Returns all skills and habits with their current streaks and last log dates.",
        ),
        types.FunctionDeclaration(
            name="tool_system_action",
            description="Executes a modification action (write) in a specific module. Use this to add, update, delete, or log data (e.g. add_task, finance_log, meal_log, health_log).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "module": types.Schema(
                        type=types.Type.STRING,
                        description="The target module (e.g. tasks, finance, health, university, workout)",
                    ),
                    "intent": types.Schema(
                        type=types.Type.STRING,
                        description="The specific intent (e.g. add_task, finance_log, workout_log)",
                    ),
                    "data": types.Schema(
                        type=types.Type.OBJECT,
                        description="The data payload for the intent (e.g. {'amount': 50, 'category': 'food'})",
                    ),
                },
                required=["module", "intent", "data"],
            ),
        ),
        types.FunctionDeclaration(
            name="tool_undo",
            description="Undoes the last action performed in a specific module. Use this when the user says 'nu asta', 'am greșit', 'anulează'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "module": types.Schema(
                        type=types.Type.STRING,
                        description="The module to undo in (e.g. tasks, finance, health)",
                    )
                },
                required=["module"],
            ),
        ),
        types.FunctionDeclaration(
            name="tool_search_memory",
            description="Searches user's long-term memory for facts, preferences, and personal details.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="Search query (e.g. 'cafea', 'preferințe', 'sâmbătă')",
                    )
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="tool_add_memory",
            description="Saves a new fact or preference to user's long-term memory.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "fact": types.Schema(
                        type=types.Type.STRING,
                        description="The fact to remember (e.g. 'Îmi place cafeaua fără zahăr')",
                    ),
                    "category": types.Schema(
                        type=types.Type.STRING,
                        description="Category (e.g. 'preferences', 'habits', 'bio')",
                    ),
                },
                required=["fact", "category"],
            ),
        ),
        types.FunctionDeclaration(
            name="tool_get_insights",
            description="Returns a timeline of mood, productivity, and habits for the last 30 days to identify patterns.",
        ),

        types.FunctionDeclaration(
            name="tool_get_apple_calendar",
            description="Fetches real-time events directly from all Apple Calendar (iCloud) calendars. Use this for the most up-to-date schedule.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "days_ahead": types.Schema(
                        type=types.Type.INTEGER,
                        description="Number of days to look ahead (default 1)",
                    )
                },
            ),
        ),
    ],
)


async def _execute_tool(pool, call_name: str, args: Dict[str, Any], bot=None) -> str:
    """Dispatches a tool call to the correct DB query or system action."""
    today = date.today()

    # Strip 'tool_' prefix if present for robust matching
    normalized_name = call_name[5:] if call_name.startswith("tool_") else call_name

    try:
        if normalized_name == "get_tasks":
            project_name = args.get("project_name")
            project_id = None
            if project_name:
                from db.queries.projects import get_project_by_name

                proj = await get_project_by_name(pool, project_name)
                if proj:
                    project_id = proj["id"]

            tasks = await list_tasks(pool, status="pending", project_id=project_id)
            return json.dumps(tasks, default=str)

        elif normalized_name == "get_events":
            target_date_str = args.get("date")
            target_date = today
            if target_date_str:
                try:
                    target_date = date.fromisoformat(target_date_str)
                except ValueError:
                    target_date = today

            # Get from DB
            db_events = await list_events(pool, target_date, target_date)

            # Also get from iCloud for real-time (optional, but good for "what events do I have" questions)
            from core.icloud import fetch_all_calendars_events

            days = (target_date - today).days
            if days < 0:
                days = 0
            icloud_events = await fetch_all_calendars_events(days_ahead=days + 1)

            # Filter iCloud events for that specific day
            icloud_today = [
                e for e in icloud_events if e["start"].date() == target_date
            ]

            return json.dumps(
                {"database_events": db_events, "icloud_events": icloud_today},
                default=str,
            )

        elif normalized_name == "get_apple_calendar":
            days = args.get("days_ahead", 1)
            from core.icloud import fetch_all_calendars_events

            events = await fetch_all_calendars_events(days_ahead=days)
            return json.dumps(events, default=str)

        elif normalized_name == "get_health":
            target_date_str = args.get("date")
            target_date = today
            if target_date_str:
                try:
                    target_date = date.fromisoformat(target_date_str)
                except ValueError:
                    target_date = today
            health = await get_health_log(pool, target_date)
            return json.dumps(health, default=str) if health else "{}"

        elif normalized_name == "get_goals_progress":
            goals = await get_all_goals(pool)
            return json.dumps(goals, default=str)

        elif normalized_name == "search_memory":
            query = args.get("query")
            facts = await semantic_search_memories(pool, TELEGRAM_USER_ID, query)
            return json.dumps(facts, default=str)

        elif normalized_name == "add_memory":
            fact = args.get("fact")
            cat = args.get("category", "general")
            if not fact or len(str(fact)) > 500 or _BLOCKED_MEMORY.search(str(fact)):
                return json.dumps({"status": "rejected", "reason": "sensitive_or_invalid_memory"})
            fact_id = await save_memory_fact(pool, TELEGRAM_USER_ID, cat, fact, "agent")
            return json.dumps({"status": "saved", "id": fact_id})

        elif normalized_name == "get_insights":
            timeline = await get_insight_data(pool, days=30)
            return json.dumps(timeline, default=str)


        elif normalized_name == "get_finance_summary":
            period = args.get("period", "today")
            if period == "current_month":
                summary = await get_monthly_summary(pool, today.month, today.year)
                cat_totals = await get_monthly_category_totals(
                    pool, today.month, today.year
                )
                return json.dumps(
                    {"summary": summary, "category_totals": cat_totals}, default=str
                )
            else:
                fin = await get_daily_transactions(pool, today)
                return json.dumps(fin, default=str)

        elif normalized_name == "get_budget_status":
            status = await get_budget_status(pool)
            return json.dumps(status, default=str)

        elif normalized_name == "get_university_schedule":
            target_date_str = args.get("date")
            target_date = today
            if target_date_str:
                try:
                    target_date = date.fromisoformat(target_date_str)
                except ValueError:
                    target_date = today

            from db.queries.schedule import get_schedule_for_date

            sched = await get_schedule_for_date(pool, target_date)
            return json.dumps(sched, default=str)

        elif normalized_name == "get_university_attendance":
            subs = await list_subjects(pool)
            return json.dumps(subs, default=str)

        elif normalized_name == "search_notes":
            query = args.get("query", "")
            notes = await search_notes(pool, query)
            return json.dumps(notes, default=str)

        elif normalized_name == "get_shopping_list":
            items = await list_shopping_items(pool)
            return json.dumps(items, default=str)

        elif normalized_name == "get_focus_stats":
            today = datetime.now(pytz.timezone(TIMEZONE)).date()
            start = today - timedelta(days=today.weekday())
            stats = await get_weekly_focus_stats(pool, start, today)
            return json.dumps(stats, default=str)

        elif normalized_name == "get_mood_trend":
            days = args.get("days", 30)
            today = datetime.now(pytz.timezone(TIMEZONE)).date()
            start = today - timedelta(days=days)
            mood = await get_monthly_mood_data(pool, start, today)
            return json.dumps(mood, default=str)

        elif normalized_name == "get_projects":
            projects = await list_projects(pool)
            return json.dumps(projects, default=str)

        elif normalized_name == "get_workouts":
            days = args.get("days", 7)
            workouts = await get_recent_workouts(pool, days)
            return json.dumps(workouts, default=str)

        elif normalized_name == "get_skills":
            skills = await get_all_skills(pool)
            return json.dumps(skills, default=str)

        elif normalized_name == "system_action":
            from core.dispatcher import execute_module_intent

            module = args.get("module")
            intent = args.get("intent")
            data = args.get("data", {})

            # Execute via dispatcher
            reply_text, markup, item_id = await execute_module_intent(
                pool, module, intent, data, reply="", bot=bot
            )
            return json.dumps(
                {"confirmation": reply_text, "item_id": item_id, "status": "success"},
                default=str,
            )

        elif normalized_name == "undo":
            from core.state import get_state

            state = await get_state(pool)
            if not state or state["module"] != args.get("module"):
                return json.dumps(
                    {
                        "error": "Nu am găsit nicio acțiune recentă de anulat în acest modul."
                    }
                )

            module = state["module"]
            last_id = state["item_id"]

            import importlib

            try:
                mod = importlib.import_module(f"modules.{module}")
                if hasattr(mod, "undo_last_action"):
                    res = await mod.undo_last_action(pool, state.get("intent"), last_id)
                    return json.dumps(
                        {"confirmation": res if isinstance(res, str) else res[0]},
                        default=str,
                    )
                return json.dumps({"error": f"Modulul {module} nu suportă anularea."})
            except Exception as e:
                return json.dumps({"error": f"Eroare la anulare: {str(e)}"})

        return json.dumps({"error": f"Unknown tool: {call_name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def run_agent(
    pool, client, user_query: str, bot=None, max_steps: int = 10
) -> str:
    """Compatibility entry point; cloud agent execution is permanently disabled."""
    logger.warning("Rejected retired cloud agent request for: %s", user_query[:100])
    return "Agentul cloud este dezactivat. Lora folosește agentul local Ollama."


def _select_relevant_tools(user_message: str) -> str | None:
    """
    Dynamically selects only the tool categories relevant to the user message.
    Reduces prompt size by ~70% for local LLMs (3B/7B), improving speed and accuracy.

    Returns a trimmed tools string, or None if the message appears to be
    general chat/knowledge (no tools needed → agent uses action_type='final' directly).
    """
    msg = user_message.lower()

    # Keyword → tool group mapping
    TOOL_GROUPS = {
        "tasks_projects": {
            "keywords": ["task", "sarcin", "todo", "proiect", "project", "deadline", "priorit", "adaug task", "complet", "finalizez", "sterge task"],
            "tools": [
                "- Intent: \"add_task\" | Module: \"tasks\" | Data: title (required), due_date?, project?, priority?",
                "- Intent: \"list_tasks\" | Module: \"tasks\" | Data: (none)",
                "- Intent: \"complete_task\" | Module: \"tasks\" | Data: task_id? or title?",
                "- Intent: \"delete_task\" | Module: \"tasks\" | Data: task_id? or title?",
                "- Intent: \"edit_task\" | Module: \"tasks\" | Data: task_id, title?, due_date?, priority?",
                "- Intent: \"add_project\" | Module: \"projects\" | Data: name (required), description?",
                "- Intent: \"list_projects\" | Module: \"projects\" | Data: (none)",
                "- Intent: \"update_project\" | Module: \"projects\" | Data: id, name?, status?",
                "- Intent: \"delete_project\" | Module: \"projects\" | Data: id",
            ],
        },
        "finance_shopping": {
            "keywords": ["bani", "cheltuiala", "cheltuiel", "venit", "platit", "platesc", "ron", "lei", "euro", "cumpar", "cumparat", "shopping", "lista", "cosmar", "budget", "buget", "finance", "finant", "cheltuit"],
            "tools": [
                "- Intent: \"finance_log\" | Module: \"finance\" | Data: entries=[{amount, category, type (income/expense), description}]",
                "- Intent: \"finance_summary\" | Module: \"finance\" | Data: period? (today/current_month)",
                "- Intent: \"delete_finance\" | Module: \"finance\" | Data: id",
                "- Intent: \"add_item\" | Module: \"shopping\" | Data: item (required), category?",
                "- Intent: \"list_items\" | Module: \"shopping\" | Data: (none)",
                "- Intent: \"delete_item\" | Module: \"shopping\" | Data: id or item_name",
                "- Intent: \"add_wish\" | Module: \"wishlist\" | Data: item (required), description?, price?, priority?",
                "- Intent: \"list_wish\" | Module: \"wishlist\" | Data: (none)",
            ],
        },
        "health_fitness": {
            "keywords": ["sanatate", "health", "sleep", "somn", "dormit", "apa", "water", "greutate", "kg", "kilograme", "calorii", "mancare", "nutritie", "nutrition", "sport", "antrenament", "workout", "gym", "sala", "alergat", "tigara", "fumat", "mood", "stare", "energie"],
            "tools": [
                "- Intent: \"health_log\" | Module: \"health\" | Data: sleep_hours?, water_ml?, weight_kg?, cigarettes?",
                "- Intent: \"health_summary\" | Module: \"health\" | Data: (none)",
                "- Intent: \"meal_log\" | Module: \"nutrition\" | Data: meal_type (required), description (required), calories, protein, carbs, fat",
                "- Intent: \"nutrition_summary\" | Module: \"nutrition\" | Data: (none)",
                "- Intent: \"workout_log\" | Module: \"workout\" | Data: sport_name, duration_min, calories?, notes?",
                "- Intent: \"workout_list\" | Module: \"workout\" | Data: (none)",
                "- Intent: \"log_mood\" | Module: \"mood\" | Data: mood (great/good/neutral/bad/terrible)",
            ],
        },
        "goals_skills": {
            "keywords": ["obiectiv", "goal", "obicei", "habit", "skill", "abilitate", "progres", "progress", "streak", "citit", "carte", "reading", "focus", "pomodoro", "concentrare"],
            "tools": [
                "- Intent: \"add_goal\" | Module: \"goals\" | Data: title (required), time_horizon, linked_keywords?",
                "- Intent: \"view_goals\" | Module: \"goals\" | Data: (none)",
                "- Intent: \"complete_goal\" | Module: \"goals\" | Data: title?",
                "- Intent: \"log_skill\" | Module: \"skills\" | Data: skill_name (required), value (0-10), weight?",
                "- Intent: \"view_skills\" | Module: \"skills\" | Data: (none)",
                "- Intent: \"add_habit\" | Module: \"skills\" | Data: habit_name (required), frequency?",
                "- Intent: \"log_habit\" | Module: \"skills\" | Data: habit_name (required)",
                "- Intent: \"reading_add\" | Module: \"reading\" | Data: title (required), author (required), total_pages?",
                "- Intent: \"reading_update\" | Module: \"reading\" | Data: id, pages_read",
                "- Intent: \"reading_list\" | Module: \"reading\" | Data: (none)",
                "- Intent: \"focus_start\" | Module: \"focus\" | Data: duration_min (required)",
                "- Intent: \"focus_stop\" | Module: \"focus\" | Data: (none)",
            ],
        },
        "events_calendar": {
            "keywords": ["eveniment", "event", "calendar", "orar", "programare", "agenda", "azi", "maine", "saptamana", "curs", "uni", "universitate", "examen", "nota"],
            "tools": [
                "- Intent: \"add_event\" | Module: \"events\" | Data: title (required), event_date (YYYY-MM-DD), event_time?",
                "- Intent: \"list_events\" | Module: \"events\" | Data: date?",
                "- Intent: \"delete_event\" | Module: \"events\" | Data: id",
                "- Intent: \"schedule_today\" | Module: \"schedule\" | Data: (none)",
                "- Intent: \"schedule_week\" | Module: \"schedule\" | Data: (none)",
                "- Intent: \"uni_add_subject\" | Module: \"university\" | Data: name (required), schedule?",
                "- Intent: \"uni_add_grade\" | Module: \"university\" | Data: subject_name (required), grade (required), credits?",
                "- Intent: \"uni_add_exam\" | Module: \"university\" | Data: subject_name (required), date (required)",
                "- Intent: \"uni_list\" | Module: \"university\" | Data: (none)",
            ],
        },
        "memory_notes_weather": {
            "keywords": ["nota", "notita", "memoreaza", "aminteste", "memory", "vreme", "meteo", "temperatura", "ploua", "travel", "calatorie", "bagaj"],
            "tools": [
                "- Intent: \"memory_view\" | Module: \"memory\" | Data: (none)",
                "- Intent: \"memory_search\" | Module: \"memory\" | Data: query (required)",
                "- Intent: \"memory_save\" | Module: \"memory\" | Data: fact (required), category (required)",
                "- Intent: \"get_weather\" | Module: \"weather\" | Data: city?",
                "- Intent: \"travel_add\" | Module: \"travel\" | Data: items (list), list_name, trip_type?",
                "- Intent: \"travel_list\" | Module: \"travel\" | Data: (none)",
            ],
        },
        "news": {
            "keywords": ["stiri", "stire", "noutati", "news", "politica", "economie", "guvern", "presa", "actualitate"],
            "tools": [
                "- Intent: \"get_news\" | Module: \"news\" | Data: topic? (\"politica\"|\"economie\"|\"tech\"|\"general\"|\"all\"|custom), limit?",
                "- Intent: \"get_tech_news\" | Module: \"news\" | Data: (none)",
            ],
        },
    }

    matched_tools = []
    for group in TOOL_GROUPS.values():
        if any(kw in msg for kw in group["keywords"]):
            matched_tools.extend(group["tools"])

    # No domain match → pure chat/knowledge question, return None (no tools)
    if not matched_tools:
        return None

    header = """RESPONSE FORMAT:
{
  "action_type": "tool" | "final",   // MUST be "tool" or "final" only
  "thought": "reasoning",
  "intent": "add_task",              // the intent name from the list below
  "module": "tasks",                 // the module name
  "data": { "title": "..." },        // parameters (extract from user message)
  "final_reply": "..."               // ONLY when action_type="final"
}

CRITICAL: action_type is ONLY "tool" or "final". NEVER put the intent name there.

AVAILABLE INTENTS (use with action_type="tool"):
"""
    return header + "\n".join(matched_tools) + "\n"


async def agent_loop(
    pool,
    user_id: int,
    user_message: str,
    user_name: str,
    tone: str,
    context_snapshot: str,
    history: list,
    personal_notes: str = "",
    system_hint: str = "",
    bot=None,
    max_steps: int = 15,
) -> Tuple[str, Any, Optional[int]]:
    """
    ReAct agent loop using local LLM (qwen2.5:7b for structured).
    Returns (final_reply, keyboard, item_id) — same as route_intent.
    """
    from core.gemini import generate_structured_response, build_temporal_context, preprocess_text, _format_history_for_prompt, AgentAction
    from core.dispatcher import execute_module_intent
    import json

    user_message = preprocess_text(user_message)
    temporal_context = build_temporal_context(TIMEZONE)

    hint = f"\nHINT: {system_hint}" if system_hint else ""

    # --- Dynamic Tool Selection: reduce prompt by ~70% for local LLMs ---
    # Selects only relevant tool categories based on user message keywords.
    # Falls back to full list if message seems like an action command.
    tools_list = _select_relevant_tools(user_message)

    _FULL_TOOLS_LIST = """
RESPONSE FORMAT:
{
  "action_type": "tool" | "final",   // MUST be "tool" or "final" only
  "thought": "reasoning",
  "intent": "add_task",              // the intent name from the list below
  "module": "tasks",                 // the module name
  "data": { "title": "..." },        // parameters (extract from user message)
  "final_reply": "..."               // ONLY when action_type="final"
}

CRITICAL: action_type is ONLY "tool" or "final". NEVER put the intent name there.

CONVERSATIONAL ACTION RULES:
- Detect implicit intentions, not only explicit commands. "Trebuie să cumpăr apă" suggests shopping and a reminder question.
- Never invent missing amounts, dates, times, products, or places. Ask one short clarification when a required field is missing.
- If the message contains multiple independent actions, put the first in intent/data and the others in additional_intents.
- For a possible action without a time ("să nu uit să sun pe mama"), ask when rather than guessing.
- Keep final replies natural Romanian and never expose intent/module names.

AVAILABLE INTENTS (use with action_type="tool"):
- Intent: "add_task" | Module: "tasks" | Data: title (required), due_date?, project?, priority?
- Intent: "list_tasks" | Module: "tasks" | Data: (none)
- Intent: "complete_task" | Module: "tasks" | Data: task_id? or title?
- Intent: "delete_task" | Module: "tasks" | Data: task_id? or title?
- Intent: "edit_task" | Module: "tasks" | Data: task_id, title?, due_date?, priority?
- Intent: "add_project" | Module: "projects" | Data: name (required), description?
- Intent: "list_projects" | Module: "projects" | Data: (none)
- Intent: "update_project" | Module: "projects" | Data: id, name?, status?
- Intent: "delete_project" | Module: "projects" | Data: id
- Intent: "add_event" | Module: "events" | Data: title (required), event_date (YYYY-MM-DD), event_time?
- Intent: "list_events" | Module: "events" | Data: date?
- Intent: "delete_event" | Module: "events" | Data: id
- Intent: "edit_event_reminder" | Module: "events" | Data: id, title?, event_date?
- Intent: "finance_log" | Module: "finance" | Data: entries=[{amount, category, type (income/expense), description}]
- Intent: "finance_summary" | Module: "finance" | Data: period? (today/current_month)
- Intent: "delete_finance" | Module: "finance" | Data: id
- Intent: "health_log" | Module: "health" | Data: sleep_hours?, water_ml?, weight_kg?, cigarettes?
- Intent: "health_summary" | Module: "health" | Data: (none)
- Intent: "meal_log" | Module: "nutrition" | Data: meal_type (required), description (required), calories, protein, carbs, fat
- Intent: "nutrition_summary" | Module: "nutrition" | Data: (none)
- Intent: "workout_log" | Module: "workout" | Data: sport_name, duration_min, calories?, notes?
- Intent: "workout_list" | Module: "workout" | Data: (none)
- Intent: "log_mood" | Module: "mood" | Data: mood (great/good/neutral/bad/terrible)
- Intent: "add_goal" | Module: "goals" | Data: title (required), time_horizon, linked_keywords?
- Intent: "view_goals" | Module: "goals" | Data: (none)
- Intent: "complete_goal" | Module: "goals" | Data: title?
- Intent: "log_skill" | Module: "skills" | Data: skill_name (required), value (0-10), weight?
- Intent: "view_skills" | Module: "skills" | Data: (none)
- Intent: "add_habit" | Module: "skills" | Data: habit_name (required), frequency?
- Intent: "log_habit" | Module: "skills" | Data: habit_name (required)
- Intent: "add_item" | Module: "shopping" | Data: item (required), category?
- Intent: "list_items" | Module: "shopping" | Data: (none)
- Intent: "delete_item" | Module: "shopping" | Data: id or item_name
- Intent: "reading_add" | Module: "reading" | Data: title (required), author (required), total_pages?
- Intent: "reading_update" | Module: "reading" | Data: id, pages_read
- Intent: "reading_list" | Module: "reading" | Data: (none)
- Intent: "travel_add" | Module: "travel" | Data: items (list), list_name, trip_type?
- Intent: "travel_list" | Module: "travel" | Data: (none)
- Intent: "focus_start" | Module: "focus" | Data: duration_min (required)
- Intent: "focus_stop" | Module: "focus" | Data: (none)
- Intent: "get_weather" | Module: "weather" | Data: city?
- Intent: "memory_view" | Module: "memory" | Data: (none)
- Intent: "memory_search" | Module: "memory" | Data: query (required)
- Intent: "memory_save" | Module: "memory" | Data: fact (required), category (required)
- Intent: "schedule_today" | Module: "schedule" | Data: (none)
- Intent: "schedule_week" | Module: "schedule" | Data: (none)
- Intent: "uni_add_subject" | Module: "university" | Data: name (required), schedule?
- Intent: "uni_add_grade" | Module: "university" | Data: subject_name (required), grade (required), credits?
- Intent: "uni_add_exam" | Module: "university" | Data: subject_name (required), date (required)
- Intent: "uni_list" | Module: "university" | Data: (none)
- Intent: "add_wish" | Module: "wishlist" | Data: item (required), description?, price?, priority?
- Intent: "list_wish" | Module: "wishlist" | Data: (none)
- Intent: "delete_wish" | Module: "wishlist" | Data: id or item
- Intent: "get_news" | Module: "news" | Data: topic? ("politica"|"economie"|"tech"|"general"|"all"|custom), limit?
- Intent: "get_tech_news" | Module: "news" | Data: (none)

EXAMPLE — User says "adauga task sa cumpar paine":
{"action_type": "tool", "thought": "User wants to add a task to buy bread", "intent": "add_task", "module": "tasks", "data": {"title": "cumpăr pâine"}, "final_reply": null}

EXAMPLE — User says "salut":
{"action_type": "final", "thought": "User is greeting", "intent": null, "module": null, "data": {}, "final_reply": "Salut! Cu ce te pot ajuta?"}

EXAMPLE — User says "ce imi poti zice despre atv uri":
{"action_type": "final", "thought": "User is asking a general question about ATVs", "intent": null, "module": null, "data": {}, "final_reply": "ATV-urile (All-Terrain Vehicles) sunt vehicule de teren ideale pentru off-road..."}
"""

    # If dynamic selection returned None → general chat, use the full list as safety net
    if tools_list is None:
        tools_list = _FULL_TOOLS_LIST

    results_log = []
    last_keyboard = None

    for step in range(1, max_steps + 1):
        prev_results = ""
        if results_log:
            for i, r in enumerate(results_log, 1):
                prev_results += f"\n  Step {i}: {r['tool']} → {r['result'][:300]}"

        history_str = _format_history_for_prompt(history[-8:]) if history else "None"

        agent_prompt = f"""You are Lora's agent. Loop: think → tool → observe → repeat → final.

RULES:
- action_type is ALWAYS "tool" or "final". NEVER anything else.
- To perform a user action (add, list, edit, delete, log, etc.), first use action_type="tool" to run the required tool.
- IMPORTANT: Once the tool has run and the results show the action succeeded, do NOT run the tool again. Instead, use action_type="final" to summarize the result for the user.
- For chat, greetings, or general knowledge questions (e.g. asking about ATVs, tech, advice), use action_type="final" directly with your response in final_reply. DO NOT call "list_tasks" or any tool unless the user explicitly mentions their personal tasks, notes, goals, or database items.
- Extract all needed fields into data from the user message.
- Speak naturally in Romanian, as a consistent personal partner: acknowledge
  context, explain briefly, and suggest one practical next step when useful.
- Use the recent conversation to resolve "asta", "cel de mai devreme", and
  relative dates before asking a question.
- Be proactive for planning and blocked goals, but never perform a write without
  the confirmation gate enforced by the application.
- After tool executes, observe the result and decide: more tools or final.

Current step: {step}/{max_steps}

{tools_list}
(Data fields marked with ? are optional.)

{temporal_context}

RECENT CONVERSATION:
{history_str}

PREVIOUS TOOL RESULTS:
{prev_results or "None yet"}

Personal notes: {personal_notes or "None"}
Context: {context_snapshot or "None"}

User message: {user_message}{hint}

JSON response (ONLY this, no extra text):
{{"action_type":"tool"|"final","thought":"...","intent":"...","module":"...","data":{{}},"final_reply":"..."}}"""

        messages = [{"role": "system", "content": agent_prompt}]
        raw = await generate_structured_response(messages, AgentAction)

        try:
            action = json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"Agent step {step}: invalid JSON: {raw[:200]}")
            if step >= max_steps:
                return "Scuze, nu am putut procesa cererea. Încearcă din nou.", None, None
            results_log.append({"tool": "_parse_error", "result": "JSON parse failed, retrying..."})
            continue

        action_type = action.get("action_type", "final")
        intent = action.get("intent")
        module = action.get("module")
        data = action.get("data") or {}
        thought = action.get("thought", "")
        final_reply = action.get("final_reply")

        # KNOWN_INTENTS for normalization — LLM sometimes misplaces fields
        KNOWN_INTENTS = {
            "add_task", "list_tasks", "complete_task", "delete_task", "edit_task",
            "add_project", "list_projects", "update_project", "delete_project",
            "add_event", "list_events", "delete_event", "edit_event_reminder",
            "finance_log", "finance_summary", "delete_finance", "finance_undo",
            "health_log", "health_summary",
            "meal_log", "nutrition_summary", "nutrition_target",
            "workout_log", "workout_list", "workout_stats",
            "log_mood",
            "add_goal", "view_goals", "complete_goal", "delete_goal",
            "log_skill", "view_skills", "add_habit", "log_habit",
            "add_item", "list_items", "delete_item",
            "reading_add", "reading_update", "reading_list",
            "travel_add", "travel_list",
            "focus_start", "focus_stop",
            "get_weather",
            "memory_view", "memory_search", "memory_save",
            "schedule_today", "schedule_week",
            "uni_add_subject", "uni_add_grade", "uni_add_exam", "uni_list",
            "add_wish", "list_wish", "delete_wish",
            "get_news", "get_tech_news", "fetch_news",
            "chat",
        }
        INTENT_TO_MODULE = {
            "add_task": "tasks", "list_tasks": "tasks", "complete_task": "tasks",
            "delete_task": "tasks", "edit_task": "tasks",
            "add_project": "projects", "list_projects": "projects",
            "update_project": "projects", "delete_project": "projects",
            "add_event": "events", "list_events": "events", "delete_event": "events",
            "edit_event_reminder": "events",
            "finance_log": "finance", "finance_summary": "finance",
            "delete_finance": "finance", "finance_undo": "finance",
            "health_log": "health", "health_summary": "health",
            "meal_log": "nutrition", "nutrition_summary": "nutrition",
            "nutrition_target": "nutrition",
            "workout_log": "workout", "workout_list": "workout", "workout_stats": "workout",
            "log_mood": "mood",
            "add_goal": "goals", "view_goals": "goals", "complete_goal": "goals",
            "delete_goal": "goals",
            "log_skill": "skills", "view_skills": "skills",
            "add_habit": "skills", "log_habit": "skills",
            "add_item": "shopping", "list_items": "shopping", "delete_item": "shopping",
            "reading_add": "reading", "reading_update": "reading", "reading_list": "reading",
            "travel_add": "travel", "travel_list": "travel",
            "focus_start": "focus", "focus_stop": "focus",
            "get_weather": "weather",
            "memory_view": "memory", "memory_search": "memory", "memory_save": "memory",
            "schedule_today": "schedule", "schedule_week": "schedule",
            "uni_add_subject": "university", "uni_add_grade": "university",
            "uni_add_exam": "university", "uni_list": "university",
            "add_wish": "wishlist", "list_wish": "wishlist", "delete_wish": "wishlist",
            "get_news": "news", "get_tech_news": "news", "fetch_news": "news",
        }

        # Normalize: LLM sometimes puts the intent name in action_type
        if action_type in KNOWN_INTENTS:
            intent = action_type
            action_type = "tool"
            module = module or INTENT_TO_MODULE.get(intent)
        if action_type not in ("tool", "final") and intent in KNOWN_INTENTS and intent != "chat":
            action_type = "tool"
            module = module or INTENT_TO_MODULE.get(intent)

        # Fallback data extraction when LLM misses to fill it
        if action_type == "tool" and intent in KNOWN_INTENTS and not data:
            data = {}
            if intent == "add_task":
                # Use whole user message as title
                data["title"] = user_message

        logger.info(f"🤖 AGENT Step {step}: type={action_type}, intent={intent}, module={module}, thought={thought}")

        if action_type == "final":
            # Verify all user requests are handled before finalizing
            if results_log:
                verify_prompt = f"""User asked: {user_message}

Completed tools so far:
{chr(10).join(f"- {r['tool']}: {r['result'][:200]}" for r in results_log)}

Are ALL requests from the user's message now handled? If yes, reply with the final answer in Romanian.
If not, list what is still MISSING.

Reply ONLY with JSON:
{{"all_done": true, "final_reply": "your final answer in Romanian"}}
OR
{{"all_done": false, "missing": "what's still unhandled"}}"""

                try:
                    verify_raw = await generate_structured_response(
                        [{"role": "system", "content": verify_prompt}], AgentAction
                    )
                    verify = json.loads(verify_raw)
                    if not verify.get("all_done"):
                        missing = verify.get("missing", "")
                        logger.info(f"🔄 VERIFY: not done yet — missing: {missing}")
                        results_log.append({"tool": "_verify", "result": f"Still needed: {missing}"})
                        continue
                    final_reply = final_reply or verify.get("final_reply")
                except Exception as e:
                    logger.warning(f"Verification call failed: {e}. Proceeding with final reply.")

            if not final_reply:
                final_reply = "Am terminat! Cu ce te mai pot ajuta?"
            return final_reply, last_keyboard, None

        if action_type == "tool" and intent and intent != "chat":
            if not module:
                logger.warning(f"Agent: tool {intent} has null module, setting to 'tasks' fallback")
                module = "tasks"

            # The agent has its own execution loop, so it must enforce the
            # same write policy as the normal router before touching a module.
            # Otherwise an agent-selected tool could bypass human approval.
            from core.router import requires_write_confirmation

            if module == "finance" and intent in {"add_item", "add_finance", "finance_log"}:
                from modules.finance import prepare_finance_action

                intent, data = await prepare_finance_action(pool, intent, data)

            pending_intent = {"intent": intent, "module": module, "data": data}
            if requires_write_confirmation(pending_intent):
                from core.state import set_pending_action

                await set_pending_action(pool, intent, module, data)
                return "__CONFIRMATION_REQUIRED__", None, None

            # Check if this exact tool and data has already been executed in this agent run (loop prevention)
            def clean_data_keys(d):
                if not isinstance(d, dict):
                    return d
                return {k: v for k, v in d.items() if not k.startswith("_")}

            clean_data = clean_data_keys(data)
            duplicate = next(
                (r for r in results_log if r.get("tool") == f"{module}.{intent}" and clean_data_keys(r.get("data")) == clean_data),
                None
            )
            if duplicate:
                logger.info(f"Loop detected: {module}.{intent} already executed with data {clean_data}. Ending loop.")
                return duplicate["result"], last_keyboard, None

            reply_text, keyboard, item_id = "", None, None
            try:
                reply_text, keyboard, item_id = await execute_module_intent(
                    pool, module, intent, data, "", user_id, bot
                )
            except Exception as e:
                reply_text = f"Eroare: {str(e)}"
                logger.error(f"Agent tool error {module}.{intent}: {e}")

            logger.info(f"⚙️ AGENT tool {module}.{intent} → {reply_text[:200]}")
            results_log.append({
                "tool": f"{module}.{intent}",
                "data": data.copy() if isinstance(data, dict) else data,
                "result": reply_text or "OK"
            })

            # Formatted read-only digests return immediately
            if module == "news":
                return reply_text, keyboard, item_id

            if item_id:
                from core.state import save_last_action
                await save_last_action(pool, action, item_id)

            if keyboard:
                last_keyboard = keyboard

            # Continue the loop for more tool calls
            continue

        # Fallback: treat as final
        return action.get("final_reply") or "Am terminat! Cu ce te mai pot ajuta?", last_keyboard, None

    return "Am depășit limita de pași. Reformulează te rog.", None, None

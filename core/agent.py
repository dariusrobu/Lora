# core/agent.py
import json
import asyncio
from datetime import date, datetime, timedelta
from typing import Dict, Any
import pytz
from google.genai import types
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
from core.council import (
    send_report_to_council,
    get_projects,
    get_summary,
    get_recent_decisions,
)
from core.config import TIMEZONE, TELEGRAM_USER_ID

# Tools definition for Gemini
# We use FunctionDeclaration for precise manual control over execution and DB pool injection.
agent_tools = types.Tool(
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
            name="tool_get_council_status",
            description="Fetches strategic updates from the Business Council: active projects, recent decisions, and executive summary.",
        ),
        types.FunctionDeclaration(
            name="tool_send_council_report",
            description="Sends a formal report to the Business Council about your progress.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "project_id": types.Schema(
                        type=types.Type.STRING,
                        description="The project ID to report on (e.g. 'P1', 'LORA_V2')",
                    ),
                    "summary": types.Schema(
                        type=types.Type.STRING,
                        description="A brief executive summary of the progress or blockers.",
                    ),
                    "completed_task_titles": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description="List of task titles completed since the last report.",
                    ),
                },
                required=["project_id", "summary"],
            ),
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
    ]
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
            fact_id = await save_memory_fact(pool, TELEGRAM_USER_ID, cat, fact, "agent")
            return json.dumps({"status": "saved", "id": fact_id})

        elif normalized_name == "get_insights":
            timeline = await get_insight_data(pool, days=30)
            return json.dumps(timeline, default=str)

        elif normalized_name == "get_council_status":
            projects = await get_projects()
            summary = await get_summary()
            decisions = await get_recent_decisions(limit=5)
            return json.dumps(
                {
                    "projects": projects,
                    "summary": summary,
                    "recent_decisions": decisions,
                },
                default=str,
            )

        elif normalized_name == "send_council_report":
            project_id = args.get("project_id")
            summary = args.get("summary")
            task_titles = args.get("completed_task_titles", [])

            # Map titles to mock dicts for the existing send_report_to_council
            tasks_data = [{"title": t} for t in task_titles]

            success = await send_report_to_council(project_id, tasks_data, summary)
            return json.dumps({"status": "sent" if success else "failed"})

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
                    res = await mod.undo_last_action(pool, last_id)
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
    """Runs a ReAct loop with Gemini, executing DB tools dynamically."""

    print(f"🤖 AGENTIC MODE TRIGGERED: '{user_query}'", flush=True)

    date_str = date.today().strftime("%Y-%m-%d")

    system_instruction = f"""
Ești Lora, într-un mod TOTAL AGENTIC.
Data curentă: {date_str}.
Trebuie să gestionezi ORICE cerere a utilizatorului.
Ai acces la tools pentru a INTEROGA (read) și pentru a EXECUTA ACȚIUNI (write/system_action) în baza de date.

REGULI IMPORTANTE:
1. Dacă utilizatorul vrea să STEARGĂ ceva (ex: "șterge tranzacția cu ID 10"), folosește `tool_system_action` cu module='finance', intent='delete_finance', data={{'id': 10}}.
2. Dacă utilizatorul spune ce a mâncat, ESTIMEAZĂ TU caloriile/macro (P/C/F) și loghează-le folosind `tool_system_action` cu module='nutrition', intent='meal_log', data={{'calories': X, 'protein': Y, 'carbs': Z, 'fat': W, 'description': '...'}}.
3. Poți face acțiuni multiple secvențial (ex: caută ID-urile, apoi șterge-le pe rând).
4. Nu te limita la "undo" dacă ai ID-ul specific.
5. Când ai terminat acțiunile, sintetizează un răspuns FINAL, cald și organizat în limba română (MarkdownV2).
6. Nu menționa procesul tău intern, dă-i direct rezultatul final sau confirmarea.
"""

    contents = [
        types.Content(role="user", parts=[types.Part.from_text(text=user_query)])
    ]

    for step in range(max_steps):
        print(f"🔄 Agent Step {step + 1}/{max_steps}", flush=True)

        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=[agent_tools],
                    temperature=0.3,
                ),
            )
        except Exception as e:
            print(f"Agent Error at generation: {e}", flush=True)
            return "A apărut o problemă în timpul analizei agentului meu. Mai încearcă o dată."

        # Append the assistant's action to the contents array
        if response.candidates and response.candidates[0].content:
            contents.append(response.candidates[0].content)

        function_calls = []
        for part in response.candidates[0].content.parts:
            if part.function_call:
                function_calls.append(part.function_call)

        if not function_calls:
            # No tools called -> LLM decided it has the final answer
            final_text = response.text
            print(f"🏁 Agent finished successfully in {step + 1} steps.", flush=True)
            return final_text

        # Execute tools and return FunctionResponses
        func_responses_parts = []
        for fc in function_calls:
            args = {k: v for k, v in fc.args.items()} if fc.args else {}
            print(f"   ⚙️ Agent calling tool: {fc.name} with args: {args}", flush=True)

            result_str = await _execute_tool(pool, fc.name, args, bot=bot)

            # Format according to genai SDK requirements
            fr_part = types.Part.from_function_response(
                name=fc.name, response={"result": result_str}
            )
            func_responses_parts.append(fr_part)

        # Append tool results to conversation
        contents.append(types.Content(role="user", parts=func_responses_parts))

    print("⚠️ Agent hit max_steps without returning plain text.", flush=True)
    return "Analiză incompletă: am atins limita de complexitate, te rog reformulează cererea mai specific."

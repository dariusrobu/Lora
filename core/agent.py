# core/agent.py
import json
import asyncio
from datetime import date
from typing import Dict, Any
import pytz
from google.genai import types
from db.queries.tasks import list_tasks
from db.queries.events import list_events
from db.queries.health import get_health_log
from db.queries.finance import get_daily_transactions
from db.queries.goals import get_all_goals
from db.queries.schedule import get_today_schedule
from db.queries.university import list_subjects
from core.config import TIMEZONE

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
            name="tool_get_events_today",
            description="Returns all events and calendar appointments scheduled for the current day.",
        ),
        types.FunctionDeclaration(
            name="tool_get_health_today",
            description="Returns the health metrics logged today (sleep, water, nutrition, weight).",
        ),
        types.FunctionDeclaration(
            name="tool_get_goals_progress",
            description="Returns the list of active goals and their current progress/subtasks.",
        ),
        types.FunctionDeclaration(
            name="tool_get_finance_summary",
            description="Returns expenses and total spendings for today.",
        ),
        types.FunctionDeclaration(
            name="tool_get_university_schedule",
            description="Returns the university schedule for today (classes, seminars).",
        ),
        types.FunctionDeclaration(
            name="tool_get_university_attendance",
            description="Returns subjects and current attendance stats.",
        ),
    ]
)


async def _execute_tool(pool, call_name: str, args: Dict[str, Any]) -> str:
    """Executes the mapped function and returns JSON string result."""
    from datetime import datetime

    today = datetime.now(pytz.timezone(TIMEZONE)).date()

    try:
        if call_name == "tool_get_tasks":
            # For simplicity, returning all pending tasks for agent string matching
            tasks = await list_tasks(pool, status="pending")
            return json.dumps(tasks, default=str)

        elif call_name == "tool_get_events_today":
            events = await list_events(pool, today)
            return json.dumps(events, default=str)

        elif call_name == "tool_get_health_today":
            health = await get_health_log(pool, today)
            return json.dumps(health, default=str) if health else "{}"

        elif call_name == "tool_get_goals_progress":
            goals = await get_all_goals(pool)
            return json.dumps(goals, default=str)

        elif call_name == "tool_get_finance_summary":
            fin = await get_daily_transactions(pool, today)
            return json.dumps(fin, default=str)

        elif call_name == "tool_get_university_schedule":
            sched = await get_today_schedule(pool)
            return json.dumps(sched, default=str)

        elif call_name == "tool_get_university_attendance":
            subs = await list_subjects(pool)
            return json.dumps(subs, default=str)

        return json.dumps({"error": f"Unknown tool: {call_name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def run_agent(pool, client, user_query: str, max_steps: int = 5) -> str:
    """Runs a ReAct loop with Gemini, executing DB tools dynamically."""

    print(f"🤖 AGENTIC MODE TRIGGERED: '{user_query}'", flush=True)

    date_str = date.today().strftime("%Y-%m-%d")

    system_instruction = f"""
Ești Lora, într-un mod analitic (Agentic Mode).
Data curentă: {date_str}.
Trebuie să rezolvi o interogare complexă a utilizatorului.
Ai acces la tools pentru a interoga baza de date (task-uri, evenimente, sănătate, obiective, finanțe).
Folosește tools-urile pe rând dacă e nevoie de răspunsuri combinate.
Când ai toate datele necesare, sintetizează un răspuns FINAL, util și clar în limba română folosind MarkdownV2.
Nu menționa procesul tău intern ("Am folosit tool-ul x..."), dă-i direct soluția/analiza.
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
            print(f"   ⚙️ Agent calling tool: {fc.name}", flush=True)
            args = {k: v for k, v in fc.args.items()} if fc.args else {}

            result_str = await _execute_tool(pool, fc.name, args)

            # Format according to genai SDK requirements
            fr_part = types.Part.from_function_response(
                name=fc.name, response={"result": result_str}
            )
            func_responses_parts.append(fr_part)

        # Append tool results to conversation
        contents.append(types.Content(role="user", parts=func_responses_parts))

    print("⚠️ Agent hit max_steps without returning plain text.", flush=True)
    return "Analiză incompletă: am atins limita de complexitate, te rog reformulează cererea mai specific."

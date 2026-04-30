from typing import Dict, Any

# Import module queries
import db.queries.tasks as task_queries
import db.queries.finance as finance_queries
import db.queries.skills as skill_queries
import db.queries.health as health_queries

async def execute_tool(name: str, args: Dict[str, Any], pool, user_id: int) -> str:
    """Executes a tool call and returns the result as a string for Gemini."""
    try:
        print(f"🛠️ EXECUTING TOOL: {name} with args {args}", flush=True)
        
        if name == "add_task":
            # Map tool args to function args
            # add_task(pool, title, priority='medium', due_date=None, project=None)
            task_id = await task_queries.add_task(
                pool, 
                title=args.get("title"),
                priority=args.get("priority", "medium"),
                due_date=args.get("due_date"),
                project=args.get("project")
            )
            return f"Succes: Task adăugat cu ID {task_id}."

        elif name == "finance_log":
            # finance_log(pool, user_id, amount, type, category, description=None)
            await finance_queries.log_finance(
                pool,
                user_id=user_id,
                amount=args.get("amount"),
                type=args.get("type", "expense"),
                category=args.get("category", "altele"),
                description=args.get("description")
            )
            return "Succes: Tranzacție financiară înregistrată."

        elif name == "log_skill":
            # log_skill(pool, skill_name, value, notes=None)
            await skill_queries.log_skill(
                pool,
                skill_name=args.get("skill_name"),
                value=args.get("value"),
                notes=args.get("notes")
            )
            return f"Succes: Progres înregistrat pentru {args.get('skill_name')}."

        elif name == "health_log":
            # health_log(pool, log_date, sleep_hours=None, water_ml=None, weight_kg=None, sleep_quality=None)
            from datetime import datetime
            today = datetime.now().date()
            await health_queries.log_health(
                pool,
                log_date=today,
                sleep_hours=args.get("sleep_hours"),
                water_ml=args.get("water_ml"),
                weight_kg=args.get("weight_kg"),
                sleep_quality=args.get("sleep_quality")
            )
            return "Succes: Date de sănătate înregistrate."

        return f"Eroare: Tool-ul '{name}' nu este implementat încă."
    except Exception as e:
        print(f"❌ TOOL EXECUTION ERROR ({name}): {e}", flush=True)
        return f"Eroare la executarea tool-ului: {str(e)}"

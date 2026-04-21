import asyncio
from datetime import datetime
import pytz
from core.config import TIMEZONE
import db.queries.tasks as task_queries
import db.queries.skills as skill_queries
import db.queries.events as event_queries
import db.queries.finance as finance_queries
import db.queries.notes as note_queries
import db.queries.health as health_queries
import db.queries.journal as journal_queries
from core.memory import get_context_memory


async def build_context(pool, current_message: str = None) -> str:
    """
    Builds a text snapshot of the user's current status for Gemini.
    OPTIMIZED: Uses asyncio.gather to fetch data in parallel.
    """
    user_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(user_tz)
    today = now.date()

    # 1. Prepare tasks to be executed in parallel
    t_tasks = task_queries.list_tasks(pool)
    t_events = event_queries.list_events(pool, today, today)
    # Filter for upcoming events/reminders
    t_reminders = event_queries.list_events(pool, today) 
    t_skills = skill_queries.get_all_skills(pool)
    t_health = health_queries.get_health_log(pool, today)
    t_finance = finance_queries.get_monthly_summary(pool, today.month, today.year)
    t_notes = note_queries.list_notes(pool, limit=3)
    t_journal = journal_queries.get_recent_journal_entries(pool, limit=1)
    
    if current_message:
        t_memory = get_context_memory(pool, current_message)
    else:
        async def empty_str(): return ""
        t_memory = empty_str()

    # 2. Parallel Data Fetching
    results = await asyncio.gather(
        t_tasks,
        t_events,
        t_reminders,
        t_skills,
        t_health,
        t_finance,
        t_notes,
        t_journal,
        t_memory
    )

    (
        tasks,
        events,
        reminders_all,
        skills,
        health,
        finance,
        notes,
        journal,
        memory_facts
    ) = results

    snapshot = []
    snapshot.append(f"--- STATUS CURENT ({now.strftime('%H:%M')}) ---")

    # Tasks
    pending = [t for t in tasks if t["status"] == "pending"]
    overdue = [t for t in pending if t["due_date"] and t["due_date"] < today]
    snapshot.append(f"Tasks pending: {len(pending)} ({len(overdue)} overdue)")
    for t in pending[:5]:
        snapshot.append(f"• {t['title']} (prioritate: {t['priority']})")

    # Events
    if events:
        snapshot.append("\n--- EVENIMENTE AZI ---")
        for e in events:
            time_str = e["event_time"].strftime("%H:%M") if e["event_time"] else "toată ziua"
            snapshot.append(f"• {e['title']} la {time_str}")

    # Reminders
    reminders = [r for r in reminders_all if r["event_type"] == "reminder"]
    if reminders:
        snapshot.append("\n--- REMINDERE VIITOARE ---")
        for r in reminders[:3]:
            snapshot.append(f"• {r['title']} ({r['event_date']})")

    # Skills
    if skills:
        snapshot.append("\n--- SKILLS (EX-HABITS) ---")
        for s in skills[:5]:
            snapshot.append(f"• {s['name']}: {s['last_value'] or 0} {s['unit']}")

    # Health
    if health:
        snapshot.append("\n--- SĂNĂTATE AZI ---")
        snapshot.append(f"• Somn: {health.get('sleep_hours')}h, Apă: {health.get('water_ml')}ml")

    # Finance
    if finance:
        snapshot.append("\n--- FINANȚE LUNA ASTA ---")
        snapshot.append(f"• Cheltuieli: {int(finance.get('expense', 0))} RON")

    # Memory
    if memory_facts and memory_facts != "Nicio amintire relevantă identificată.":
        snapshot.append("\n--- CE ȘTIU DESPRE TINE (MEMORIE) ---")
        snapshot.append(memory_facts)

    return "\n".join(snapshot)

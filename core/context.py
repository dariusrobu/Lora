import asyncio
from datetime import datetime, timedelta
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

    # 0. Fetch user profile
    from db.queries.profile import get_user_profile

    profile = await get_user_profile(
        pool, 12345
    )  # We need to pass the actual user_id here eventually
    # NOTE: TELEGRAM_USER_ID from config is a good fallback
    from core.config import TELEGRAM_USER_ID

    profile = await get_user_profile(pool, TELEGRAM_USER_ID)

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
        # Simple category inference for better memory matching
        low_msg = current_message.lower()
        hint_category = None
        if any(
            w in low_msg
            for w in ["bani", "cheltuieli", "pret", "ron", "lei", "finance"]
        ):
            hint_category = "finance"
        elif any(w in low_msg for w in ["task", "proiect", "todo"]):
            hint_category = "tasks"
        elif any(w in low_msg for w in ["sala", "antrenament", "sport", "workout"]):
            hint_category = "workout"
        elif any(
            w in low_msg for w in ["sanatate", "apa", "somn", "greutate", "health"]
        ):
            hint_category = "health"

        t_memory = get_context_memory(pool, current_message, hint_category)
    else:

        async def empty_str():
            return ""

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
        t_memory,
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
        memory_facts,
    ) = results

    snapshot = []
    snapshot.append(f"--- STATUS CURENT ({now.strftime('%H:%M')}) ---")

    if profile:
        tone = profile.get("preferred_tone") or profile.get("tone", "direct")
        start = profile.get("active_hours_start", "08:00")
        end = profile.get("active_hours_end", "22:00")
        snapshot.append(f"Profil: Tone={tone}, Ore active={start}-{end}")

        freq = profile.get("frequent_categories")
        if freq and isinstance(freq, dict):
            f_cats = freq.get("finance", {})
            t_cats = freq.get("tasks", {})
            if f_cats:
                snapshot.append(
                    f"Categorii frecvente (Finance): {', '.join(list(f_cats.keys())[:3])}"
                )
            if t_cats:
                snapshot.append(
                    f"Proiecte frecvente (Tasks): {', '.join(list(t_cats.keys())[:3])}"
                )

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
            time_str = (
                e["event_time"].strftime("%H:%M") if e["event_time"] else "toată ziua"
            )
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
        snapshot.append(
            f"• Somn: {health.get('sleep_hours')}h, Apă: {health.get('water_ml')}ml"
        )

    # Finance
    if finance:
        snapshot.append("\n--- FINANȚE LUNA ASTA ---")
        snapshot.append(f"• Cheltuieli: {int(finance.get('expense', 0))} RON")

    # Memory
    if memory_facts and memory_facts != "Nicio amintire relevantă identificată.":
        snapshot.append("\n--- CE ȘTIU DESPRE TINE (MEMORIE) ---")
        snapshot.append(memory_facts)

    return "\n".join(snapshot)


def build_temporal_context(timezone: str) -> str:
    """
    Generates a temporal context string for Gemini to help resolve relative dates.
    """
    try:
        user_tz = pytz.timezone(timezone)
    except Exception:
        user_tz = pytz.UTC

    now = datetime.now(user_tz)
    day_names = {
        0: "Luni",
        1: "Marți",
        2: "Miercuri",
        3: "Joi",
        4: "Vineri",
        5: "Sâmbătă",
        6: "Duminică",
    }
    current_day = day_names[now.weekday()]

    # Calculations for examples
    tomorrow = now + timedelta(days=1)
    next_monday = now + timedelta(days=(7 - now.weekday()))

    # "In weekend" (next Saturday)
    days_until_sat = (5 - now.weekday()) % 7
    if (
        days_until_sat == 0 and now.weekday() == 5
    ):  # If today is Saturday, usually "weekend" means next one if it's late, or current.
        # But prompt says "sâmbăta următoare"
        days_until_sat = 7
    elif days_until_sat == 0:  # already Saturday
        days_until_sat = 0

    next_sat = now + timedelta(days=days_until_sat)

    return f"""--- CONTEXT TEMPORAL ---
Data curentă: {now.strftime("%Y-%m-%d")}
Ora curentă: {now.strftime("%H:%M")}
Ziua săptămânii: {current_day}

Exemple de rezolvare pentru azi:
- "mâine" = {tomorrow.strftime("%Y-%m-%d")}
- "săptămâna viitoare luni" = {next_monday.strftime("%Y-%m-%d")}
- "în weekend" = {next_sat.strftime("%Y-%m-%d")} (Sâmbătă)

Toate datele din JSON trebuie să fie în format ISO 8601 (YYYY-MM-DD).
Dacă ora nu este specificată, folosește doar data.
"""

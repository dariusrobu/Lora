import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, Any
import pytz
from core.config import TIMEZONE
import db.queries.tasks as task_queries
import db.queries.skills as skill_queries
import db.queries.events as event_queries
import db.queries.finance as finance_queries
import db.queries.notes as note_queries
import db.queries.health as health_queries
import db.queries.journal as journal_queries
import db.queries.goals
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

    async def get_projects_context():
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    p.id, 
                    p.name, 
                    p.description, 
                    p.status, 
                    p.deadline, 
                    p.priority, 
                    p.category, 
                    p.progress_pct, 
                    p.updated_at,
                    COALESCE(
                        (
                            SELECT json_agg(t_sub) FROM (
                                SELECT t.id, t.title, t.priority, to_char(t.due_date, 'YYYY-MM-DD') as due_date
                                FROM tasks t
                                WHERE t.project_id = p.id AND t.status = 'pending'
                                ORDER BY t.priority = 'high' DESC, t.due_date ASC NULLS LAST, t.id ASC
                                LIMIT 3
                            ) t_sub
                        ), 
                        '[]'::json
                    ) as pending_tasks
                FROM projects p
                WHERE p.status != 'archived'
                ORDER BY p.updated_at DESC
            """)
            return [dict(r) for r in rows]

    from db.queries.history import get_recent_history

    t_projects = get_projects_context()
    t_history = get_recent_history(pool, TELEGRAM_USER_ID, limit=5)

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

        t_memory = get_context_memory(
            pool, TELEGRAM_USER_ID, current_message, hint_category
        )
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
        t_projects,
        t_history,
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
        active_projects,
        recent_history,
    ) = results

    # 3. Process mentions and projects
    conversation_texts = [h["content"] for h in recent_history if h.get("content")]
    if current_message and (
        not conversation_texts or current_message != conversation_texts[-1]
    ):
        conversation_texts.append(current_message)
    conversation_texts = conversation_texts[-5:]

    mentioned_projects = []
    other_projects = []

    for proj in active_projects:
        proj_name = proj["name"]
        mentioned = False
        for text in conversation_texts:
            if text and proj_name.lower() in text.lower():
                mentioned = True
                break

        if mentioned:
            mentioned_projects.append(proj)
        else:
            other_projects.append(proj)

    sorted_projects = mentioned_projects + other_projects

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

    # Active Projects
    if sorted_projects:
        snapshot.append("\n## Proiectele active")
        for proj in sorted_projects:
            is_active_mention = any(
                proj["name"].lower() in text.lower()
                for text in conversation_texts
                if text
            )
            marker = " ⚡ Proiect activ în conversație" if is_active_mention else ""

            last_active = proj["updated_at"]
            last_active_str = (
                last_active.strftime("%Y-%m-%d %H:%M") if last_active else "N/A"
            )
            progress = proj.get("progress_pct") or 0
            desc = f" - {proj['description']}" if proj.get("description") else ""

            snapshot.append(f"• **{proj['name']}**{marker}{desc}")
            snapshot.append(
                f"  Progres: {progress}%, Ultima activitate: {last_active_str}"
            )

            p_tasks = proj.get("pending_tasks") or []
            if isinstance(p_tasks, str):
                import json

                try:
                    p_tasks = json.loads(p_tasks)
                except Exception:
                    p_tasks = []

            if p_tasks:
                snapshot.append("  Tasks deschise:")
                for t in p_tasks[:3]:
                    due_str = f" (due: {t['due_date']})" if t.get("due_date") else ""
                    snapshot.append(
                        f"    - {t['title']} [prioritate: {t['priority']}]{due_str}"
                    )

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


async def build_morning_briefing_context(pool) -> Dict[str, Any]:
    """
    Gathers structured data for the prioritized morning briefing.
    Returns a comprehensive dictionary for Gemini to synthesize.
    """
    user_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(user_tz)
    today = now.date()
    from core.config import TELEGRAM_USER_ID
    from modules.weather import get_weather_summary
    from db.queries.schedule import get_today_schedule, get_current_week_type
    from db.queries.events import list_events
    from db.queries.health import get_health_log
    from db.queries.profile import get_user_profile
    from db.queries.university import get_upcoming_exams

    from core.icloud import fetch_all_calendars_events
    from db.queries.memory import get_random_memory_lane
    import os

    # Gather iCloud events if credentials exist
    icloud_events = []
    if os.getenv("ICLOUD_USERNAME") and os.getenv("ICLOUD_APP_PASSWORD"):
        try:
            # fetch_all_calendars_events returns a list of dicts
            all_ic_events = await fetch_all_calendars_events(days_ahead=1)
            # Filter for today
            icloud_events = [e for e in all_ic_events if e["start"].date() == today]
        except Exception:
            pass

    # 1. Fetch profile first to get location
    profile = await get_user_profile(pool, TELEGRAM_USER_ID)
    lat = profile.get("latitude") if profile else None
    lon = profile.get("longitude") if profile else None

    # 2. Gather all raw data in parallel
    results = await asyncio.gather(
        task_queries.list_tasks(pool),
        skill_queries.get_all_skills(pool),
        finance_queries.get_monthly_summary(pool, today.month, today.year),
        finance_queries.get_budget_status(pool),
        get_weather_summary(lat=lat, lon=lon),
        get_today_schedule(pool),
        list_events(pool, today, today),
        get_health_log(pool, today),
        get_current_week_type(pool),
        get_upcoming_exams(pool, days=7),
        db.queries.goals.check_goal_alignment(pool, TELEGRAM_USER_ID),
        get_random_memory_lane(pool),
    )

    (
        tasks,
        skills,
        finance_summary,
        budget_status,
        weather,
        schedule,
        events,
        health,
        week_type,
        exams,
        goal_alignment,
        memory_lane,
    ) = results

    # 2. Process tasks
    urgent_tasks = [t for t in tasks if t["due_date"] and t["due_date"] <= today]
    decide_keywords = ["blocat", "waiting", "asteptare", "depinde", "blocked"]
    decide_tasks = [
        t
        for t in tasks
        if any(
            kw in (t["title"] or "").lower() or kw in (t["notes"] or "").lower()
            for kw in decide_keywords
        )
    ]

    focus_task = None
    if urgent_tasks:
        urgent_tasks.sort(
            key=lambda x: (
                0 if x["priority"] == "high" else 1 if x["priority"] == "medium" else 2,
                x["due_date"] or today,
            )
        )
        focus_task = urgent_tasks[0]
    elif tasks:
        tasks.sort(
            key=lambda x: (
                0 if x["priority"] == "high" else 1 if x["priority"] == "medium" else 2,
                x["due_date"] or (today + timedelta(days=365)),
            )
        )
        focus_task = tasks[0]

    # 3. Process finance
    balance = finance_summary.get("income", 0) - finance_summary.get("expense", 0)
    alerts = []
    for b in budget_status:
        limit = float(b["monthly_limit"])
        spent = float(b["current_spent"])
        if spent >= limit * 0.8:
            alerts.append(
                {
                    "category": b["category"],
                    "limit": limit,
                    "spent": spent,
                    "percentage": round((spent / limit) * 100),
                }
            )

    # 4. Process streaks
    active_streaks = []
    for s in skills:
        streak = await skill_queries.get_skill_streak(pool, s["id"])
        if streak >= 3:
            active_streaks.append({"name": s["name"], "streak": streak})

    return {
        "user_name": profile.get("name") or "User",
        "today": today.strftime("%Y-%m-%d"),
        "weather": weather,
        "university": {
            "week_type": week_type,
            "classes": [
                {
                    "subject": c["subject_name"],
                    "time": str(c["start_time"]),
                    "room": c["room"],
                }
                for c in schedule
            ],
        },
        "events": [{"title": e["title"], "time": str(e["event_time"])} for e in events],
        "urgent_tasks": [
            {
                "title": t["title"],
                "due_date": str(t["due_date"]),
                "priority": t["priority"],
            }
            for t in urgent_tasks[:5]
        ],
        "decide_tasks": [
            {"title": t["title"], "notes": t["notes"]} for t in decide_tasks[:3]
        ],
        "focus_recommended": {
            "title": focus_task["title"],
            "priority": focus_task["priority"],
            "due_date": str(focus_task["due_date"]),
        }
        if focus_task
        else None,
        "finance": {"monthly_balance": balance, "budget_alerts": alerts},
        "active_streaks": active_streaks,
        "health_status": {
            "sleep": health.get("sleep_hours") if health else None,
            "water": health.get("water_ml") if health else None,
        },
        "upcoming_exams": [
            {
                "subject": e["subject_name"],
                "date": str(e["exam_date"]),
                "type": e["exam_type"],
            }
            for e in exams
        ],

        "goal_alignment_nudge": goal_alignment,
        "memory_lane": memory_lane,
        "icloud_events": icloud_events,
    }


async def build_weekly_review_context(
    pool, start_date: date, end_date: date
) -> Dict[str, Any]:
    """
    Gathers comprehensive data for the weekly review report.
    """
    from db.queries import tasks as task_queries
    from db.queries import finance as finance_queries
    from db.queries import workout as workout_queries
    from db.queries import skills as skill_queries

    results = await asyncio.gather(
        task_queries.get_weekly_task_stats(pool, start_date, end_date),
        finance_queries.get_budget_status(pool),  # To compare spent vs limit
        finance_queries.get_finance_history(pool, days=7),
        workout_queries.get_recent_workouts(pool, days=7),
        skill_queries.get_all_skills(pool),
        pool.fetch(
            "SELECT content, created_at FROM notes WHERE created_at::date BETWEEN $1 AND $2",
            start_date,
            end_date,
        ),
    )

    task_stats, budget_status, finance_history, workouts, skills, notes = results

    # Process streaks for skills
    skill_data = []
    for s in skills:
        streak = await skill_queries.get_skill_streak(pool, s["id"])
        skill_data.append({"name": s["name"], "streak": streak})

    return {
        "period": {"start": str(start_date), "end": str(end_date)},
        "tasks": task_stats,
        "finance": {
            "budgets": [
                {
                    "category": b["category"],
                    "spent": float(b["current_spent"]),
                    "limit": float(b["monthly_limit"]),
                }
                for b in budget_status
            ],
            "history": [
                {"date": str(f["tx_date"]), "total": float(f["total"])}
                for f in finance_history
            ],
        },
        "workouts": [{"type": w["type"], "date": str(w["log_date"])} for w in workouts],
        "skills": skill_data,
        "university_notes_count": len(notes),
        "notable_notes": [n["content"][:100] + "..." for n in notes[:5]],
    }

from datetime import datetime
import pytz
from core.config import TIMEZONE
import db.queries.tasks as task_queries
import db.queries.habits as habit_queries
import db.queries.events as event_queries
import db.queries.finance as finance_queries
import db.queries.projects as project_queries
import db.queries.notes as note_queries
import db.queries.profile as profile_queries
from core.config import TELEGRAM_USER_ID

async def build_context(pool) -> str:
    """
    Returns a formatted string containing a snapshot of all relevant 
    modules for Lora's current turn.
    """
    user_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(user_tz)
    today = now.date()
    
    # 1. User Profile
    profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
    
    snapshot = []
    snapshot.append(f"Today's Date: {today.strftime('%Y-%m-%d (%A)')}")
    snapshot.append(f"Current Time: {now.strftime('%H:%M')}")
    snapshot.append(f"User Name: {profile.get('name', 'User')}")
    snapshot.append(f"Tone Preference: {profile.get('tone', 'warm')}")
    
    # 2. Tasks
    tasks = await task_queries.list_tasks(pool)
    pending_tasks = [t for t in tasks if t['status'] == 'pending']
    overdue = [t for t in pending_tasks if t['due_date'] and t['due_date'] < today]
    due_today = [t for t in pending_tasks if t['due_date'] == today]
    
    snapshot.append("\n--- TASKS ---")
    if overdue:
        snapshot.append(f"⚠️ Overdue: {', '.join([t['title'] for t in overdue])}")
    if due_today:
        snapshot.append(f"Due Today: {', '.join([t['title'] for t in due_today])}")
    elif not overdue:
        snapshot.append("No urgent tasks pending.")

    # 3. Habits
    habits = await habit_queries.list_habits(pool)
    today_logs = await habit_queries.get_today_logs(pool)
    habit_lines = []
    for h in habits:
        status = "Done" if h['id'] in today_logs else "Pending"
        habit_lines.append(f"{h['name']} ({status}, streak: {h['streak_count']})")
    
    snapshot.append("\n--- HABITS ---")
    if habit_lines:
        snapshot.append(", ".join(habit_lines))
    else:
        snapshot.append("No habits set up.")

    # 4. Events
    events = await event_queries.list_events(pool, today, today)
    snapshot.append("\n--- EVENTS TODAY ---")
    if events:
        for e in events:
            t_str = f" at {e['event_time'].strftime('%H:%M')}" if e['event_time'] else ""
            snapshot.append(f"• {e['title']}{t_str}")
    else:
        snapshot.append("No events scheduled for today.")

    # 5. Finance
    finances = await finance_queries.get_monthly_summary(pool, today.month, today.year)
    snapshot.append("\n--- FINANCE (THIS MONTH) ---")
    snapshot.append(f"Income: {finances['income']} RON | Expenses: {finances['expense']} RON")

    # 6. Projects
    projects = await project_queries.list_projects(pool)
    snapshot.append("\n--- ACTIVE PROJECTS ---")
    if projects:
        snapshot.append(", ".join([p['name'] for p in projects]))
    else:
        snapshot.append("No active projects.")

    # 7. Recent Notes
    notes = await note_queries.list_notes(pool, limit=3)
    snapshot.append("\n--- RECENT NOTES ---")
    if notes:
        for n in notes:
            content = n['content'][:60] + "..." if len(n['content']) > 60 else n['content']
            snapshot.append(f"• {content}")
    else:
        snapshot.append("No recent notes.")

    return "\n".join(snapshot)

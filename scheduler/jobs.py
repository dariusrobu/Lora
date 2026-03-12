from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, time
import pytz
from core.config import TELEGRAM_USER_ID, TIMEZONE
from bot.formatter import escape_md
from telegram.constants import ParseMode
import db.queries.profile as profile_queries
import db.queries.tasks as task_queries
import db.queries.habits as habit_queries
import db.queries.events as event_queries
import db.queries.finance as finance_queries

async def send_morning_briefing(application, pool):
    """Sends a daily summary of tasks, events, and habits."""
    user_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(user_tz)
    today = now.date()

    # 1. Idempotency check
    profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
    if profile.get('last_briefing_date') == today:
        return

    # 2. Gather data
    tasks = await task_queries.list_tasks(pool)
    overdue = [t for t in tasks if t['due_date'] and t['due_date'] < today]
    due_today = [t for t in tasks if t['due_date'] == today]
    
    events = await event_queries.list_events(pool, today, today)
    habits = await habit_queries.list_habits(pool)
    finances = await finance_queries.get_monthly_summary(pool, today.month, today.year)

    # 3. Format message
    lines = [f"Good morning, {escape_md(profile.get('name', 'User'))}! ☀️\n"]
    
    lines.append("📋 *Tasks*")
    if overdue:
        lines.append(f"⚠️ Overdue: {len(overdue)}")
    lines.append(f"Today: {len(due_today) if due_today else 'Nothing due today'}\n")

    lines.append("📅 *Events Today*")
    if events:
        for e in events:
            t_str = f" at {e['event_time'].strftime('%H:%M')}" if e['event_time'] else ""
            lines.append(f"• {escape_md(e['title'])}{t_str}")
    else:
        lines.append("No events today\n")

    lines.append("✅ *Habits*")
    lines.append(f"You have {len(habits)} habits to track today\\. Ready?\n")

    lines.append("💰 *Finance*")
    lines.append(f"Spent this month: `{finances['expense']} RON`")

    # 4. Send
    await application.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text="\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2
    )

    # 5. Update last_briefing_date
    await profile_queries.update_user_profile(pool, TELEGRAM_USER_ID, last_briefing_date=today)

async def send_eod_reflection(application, pool):
    """Checks in with the user at the end of the day."""
    profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
    today = datetime.now(pytz.timezone(TIMEZONE)).date()
    
    if profile.get('last_eod_date') == today:
        return

    from bot.keyboards import mood_keyboard
    reply = f"Hey {escape_md(profile.get('name', 'User'))}, end of day 🌙\n\nHow did today go?"
    
    await application.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text=reply,
        reply_markup=mood_keyboard(),
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    await profile_queries.update_user_profile(pool, TELEGRAM_USER_ID, last_eod_date=today)

async def missed_habit_nudge(application, pool):
    """Silently logs 'missed' for habits not completed yesterday."""
    from datetime import timedelta
    yesterday = datetime.now(pytz.timezone(TIMEZONE)).date() - timedelta(days=1)
    
    habits = await habit_queries.list_habits(pool)
    async with pool.acquire() as conn:
        for h in habits:
            # Check if log exists for yesterday
            exists = await conn.fetchval(
                "SELECT 1 FROM habit_logs WHERE habit_id = $1 AND log_date = $2",
                h['id'], yesterday
            )
            if not exists:
                await habit_queries.log_habit(pool, h['id'], yesterday, 'missed')
                print(f"Logged missed habit: {h['name']} for {yesterday}")

async def check_event_reminders(application, pool):
    """Checks for upcoming events and sends reminders."""
    # Simplified logic for now: query all events and check time diffs
    # This will be refined in Phase 8
    pass

def setup_scheduler(application, pool):
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    
    # Get times from config
    from core.config import MORNING_BRIEFING_TIME, EOD_REFLECTION_TIME
    m_h, m_m = map(int, MORNING_BRIEFING_TIME.split(':'))
    e_h, e_m = map(int, EOD_REFLECTION_TIME.split(':'))

    scheduler.add_job(send_morning_briefing, 'cron', hour=m_h, minute=m_m, args=[application, pool])
    scheduler.add_job(send_eod_reflection, 'cron', hour=e_h, minute=e_m, args=[application, pool])
    scheduler.add_job(missed_habit_nudge, 'cron', hour=(m_h + 1) % 24, minute=m_m, args=[application, pool])
    scheduler.add_job(check_event_reminders, 'interval', minutes=15, args=[application, pool])
    
    scheduler.start()
    print("Scheduler started.")
    return scheduler

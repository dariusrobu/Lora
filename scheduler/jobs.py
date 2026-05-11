from bot.callback_utils import make_callback_data
import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.icloud import (
    sync_events_table_to_calendar,
    sync_tasks_with_deadlines,
)
from datetime import datetime, timedelta, date, time
import pytz
from core.config import (
    TELEGRAM_USER_ID,
    TIMEZONE,
    MORNING_BRIEFING_TIME,
    EOD_REFLECTION_TIME,
    HABIT_REMINDER_TIME,
    JOURNAL_NIGHT_TIME,
    COUNCIL_GROUP_CHAT_ID,
)
from bot.formatter import escape_md, safe_markdown
from telegram.constants import ParseMode
import db.queries.profile as profile_queries
import db.queries.tasks as task_queries
import db.queries.skills as skill_queries
import db.queries.events as event_queries
import db.queries.finance as finance_queries
import db.queries.health as health_queries


async def send_daily_report(application, pool) -> bool:
    """Collects and sends daily report to Council API."""
    try:
        import json
        from core.council import send_report_to_council
        from core.config import TELEGRAM_USER_ID as TG_ID
        from datetime import date
        from db.queries.log import log_execution
        import traceback

        today = date.today()
        project_id = str(TG_ID)

        # 1. Tasks Completed
        completed = await task_queries.get_completed_tasks_today(pool)

        # 2. Tasks Created Today
        async with pool.acquire() as conn:
            created_rows = await conn.fetch(
                "SELECT title FROM tasks WHERE DATE(created_at) = CURRENT_DATE"
            )
            tasks_created = [{"title": r["title"]} for r in created_rows]

        # 3. Tasks Pending Overdue
        async with pool.acquire() as conn:
            overdue_rows = await conn.fetch(
                "SELECT title, due_date FROM tasks WHERE status != 'done' AND due_date < CURRENT_DATE AND deleted_at IS NULL"
            )
            tasks_pending_overdue = [
                {"title": r["title"], "due_date": r["due_date"].isoformat() if r["due_date"] else None} 
                for r in overdue_rows
            ]

        # 4. Finance Summary
        async with pool.acquire() as conn:
            fin_total = await conn.fetchval(
                "SELECT SUM(amount) FROM finances WHERE DATE(tx_date) = CURRENT_DATE AND type = 'expense'"
            )
            fin_cat = await conn.fetch(
                "SELECT category, SUM(amount) as total FROM finances WHERE DATE(tx_date) = CURRENT_DATE AND type = 'expense' GROUP BY category"
            )
            finance_summary = {
                "total": float(fin_total) if fin_total else 0.0,
                "per_category": {r["category"]: float(r["total"]) for r in fin_cat}
            }

        # 5. Active Goals
        async with pool.acquire() as conn:
            goals_rows = await conn.fetch(
                "SELECT title, progress_percent FROM goals WHERE status = 'active'"
            )
            active_goals = [
                {"title": r["title"], "progress_percent": float(r["progress_percent"]) if r["progress_percent"] else 0.0} 
                for r in goals_rows
            ]

        # 6. Mood and Energy
        async with pool.acquire() as conn:
            health_row = await conn.fetchrow(
                "SELECT mood, energy FROM health_logs WHERE log_date = CURRENT_DATE"
            )
            mood = int(health_row["mood"]) if health_row and health_row["mood"] is not None else None
            energy = int(health_row["energy"]) if health_row and health_row["energy"] is not None else None

        # 7. Streaks Active
        from db.queries.skills import get_skill_streak
        async with pool.acquire() as conn:
            skills = await conn.fetch("SELECT id, name FROM skills")
        
        streaks_active = []
        for s in skills:
            streak = await get_skill_streak(pool, s["id"])
            if streak > 0:
                streaks_active.append({"name": s["name"], "streak": streak})

        # Payload construction
        payload = {
            "tasks_completed": completed or [],
            "tasks_created": tasks_created or [],
            "tasks_pending_overdue": tasks_pending_overdue or [],
            "finance_summary": finance_summary,
            "active_goals": active_goals or [],
            "mood": mood,
            "energy": energy,
            "streaks_active": streaks_active or [],
            "date": today.isoformat()
        }

        # Send report
        result = await send_report_to_council(
            project_id=project_id,
            payload=payload
        )

        # Log to execution_log
        payload_size = len(json.dumps(payload, default=str))
        await log_execution(
            pool=pool,
            intent="council_report",
            module="jobs",
            success=result,
            error_type=None,
            error_message=f"Payload size: {payload_size} bytes" if result else f"Failed to send report. Payload size: {payload_size} bytes"
        )

        if result:
            print(f"Report sent to Council for {today}.", flush=True)

        if COUNCIL_GROUP_CHAT_ID and COUNCIL_GROUP_CHAT_ID != "":
            task_titles = [t.get("title") for t in completed if t.get("title")]
            report_text = (
                f"[REPORT] {today.strftime('%Y-%m-%d')}\n"
                f"Tasks completed: {len(task_titles)}\n"
                + "\n".join(f"• {t}" for t in task_titles[:5])
            )
            if len(task_titles) > 5:
                report_text += f"\n... and {len(task_titles) - 5} more"

            await application.bot.send_message(
                chat_id=COUNCIL_GROUP_CHAT_ID,
                text=report_text,
            )
            print("Report posted to Council group.", flush=True)
            
        return result

    except Exception as e:
        import traceback
        print(f"CRITICAL error in send_daily_report: {e}", flush=True)
        traceback.print_exc()
        try:
            from db.queries.log import log_execution
            await log_execution(
                pool=pool,
                intent="council_report",
                module="jobs",
                success=False,
                error_type=e.__class__.__name__,
                error_message=str(e)
            )
        except:
            pass
        return False


# NOTE: This bot uses long polling and should NOT be run in multiple instances simultaneously.
# A PID lock file (lora.pid) in main.py prevents duplicate polling instances.

_global_scheduler = None


async def check_wake_time_and_schedule(application, pool):
    """Daily check at 05:00 to schedule the morning briefing based on wake_time."""
    try:
        from db.queries.day_plans import get_day_plan
        from core.config import MORNING_BRIEFING_TIME, TELEGRAM_USER_ID, TIMEZONE
        import pytz
        from datetime import date, datetime

        user_tz = pytz.timezone(TIMEZONE)
        today = date.today()

        # 1. Check if already sent (idempotency)
        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if profile.get("last_briefing_date") == today:
            print(f"Briefing already sent for {today} — skipping schedule.", flush=True)
            return

        # 2. Get wake_time from day_plans
        plan = await get_day_plan(pool, today)
        wake_time = plan.get("wake_time") if plan else None

        if not wake_time:
            wake_time = MORNING_BRIEFING_TIME
            print(
                f"No wake_time found for {today}, using fallback: {wake_time}",
                flush=True,
            )
        else:
            print(f"Found wake_time for {today}: {wake_time}", flush=True)

        # 3. Schedule the job
        wake_h, wake_m = map(int, wake_time.split(":"))
        run_time = datetime.now(user_tz).replace(
            hour=wake_h, minute=wake_m, second=0, microsecond=0
        )

        # If wake_time is already in the past (e.g. at 05:00 we see wake_time=04:30), run ASAP or skip
        if run_time < datetime.now(user_tz):
            run_time = datetime.now(user_tz) + timedelta(seconds=10)

        global _global_scheduler
        if _global_scheduler:
            _global_scheduler.add_job(
                send_morning_briefing,
                "date",
                run_date=run_time,
                args=[application, pool],
                id=f"morning_briefing_{today}",
                replace_existing=True,
                misfire_grace_time=3600,
            )
            print(f"Morning briefing scheduled for {run_time}", flush=True)
        else:
            print("Error: Global scheduler not initialized.", flush=True)

    except Exception as e:
        print(f"Error in check_wake_time_and_schedule: {e}", flush=True)
        import traceback

        traceback.print_exc()


async def sync_calendar_job(pool):
    """Background job to keep Apple Calendar and Reminders in sync."""
    import asyncio
    from core.icloud import (
        sync_university_schedule_to_calendar,
        sync_tasks_to_reminders,
        sync_from_icloud_to_lora,
        cleanup_calendar_orphans,
        sync_exams_to_calendar,
    )

    print("⏳ Starting periodic Apple Sync (Calendar & Reminders)...", flush=True)
    try:
        await asyncio.gather(
            cleanup_calendar_orphans(pool),
            sync_university_schedule_to_calendar(pool),
            sync_events_table_to_calendar(pool),
            sync_tasks_with_deadlines(pool),
            sync_exams_to_calendar(pool),
            sync_tasks_to_reminders(pool),
            sync_from_icloud_to_lora(pool),
        )
        print("✅ Periodic Apple Sync completed.", flush=True)
    except Exception as e:
        print(f"❌ Periodic Apple Sync failed: {e}", flush=True)


async def cleanup_history_job(pool):
    """Periodic job to cleanup message history older than 30 days."""
    from db.queries.history import cleanup_history

    print("🧹 Starting message history cleanup...", flush=True)
    try:
        deleted = await cleanup_history(pool, days=30)
        print(f"✅ Cleanup finished: deleted {deleted} old messages.", flush=True)
    except Exception as e:
        print(f"❌ History cleanup failed: {e}", flush=True)


async def daily_shopping_cleanup(pool):
    """Nightly cleanup of bought items from the shopping list."""
    from db.queries.shopping import clear_bought_items

    print("🧹 Starting nightly shopping list cleanup...", flush=True)
    try:
        await clear_bought_items(pool)
        print("✅ Nightly shopping cleanup finished.", flush=True)
    except Exception as e:
        print(f"❌ Shopping cleanup failed: {e}", flush=True)


async def update_profile_job(pool):
    """Weekly job to analyze behavior and update user profile."""
    from modules.profile import update_profile_from_behavior
    from core.config import TELEGRAM_USER_ID

    print("🔄 Starting weekly profile update...", flush=True)
    try:
        await update_profile_from_behavior(pool, TELEGRAM_USER_ID)
        print("✅ Weekly profile update finished.", flush=True)
    except Exception as e:
        print(f"❌ Profile update failed: {e}", flush=True)


async def send_morning_briefing(application, pool, force=False):
    """Sends a daily summary of tasks, events, skills, and health."""
    import os
    from decimal import Decimal

    class UniversalEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            return super(UniversalEncoder, self).default(obj)

    try:
        user_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(user_tz)
        today = now.date()

        # 1. Idempotency check
        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if not force and profile.get("last_briefing_date") == today:
            return

        print(f"Starting prioritized morning briefing for {today}...", flush=True)

        # 2. Gather prioritized context
        from core.context import build_morning_briefing_context
        from core.gemini import get_proactive_response
        from bot.formatter import safe_markdown, split_message, escape_md

        briefing_data = await build_morning_briefing_context(pool)

        # 3. Construct Gemini Prompt
        name = briefing_data.get("user_name", "User")
        tone = profile.get("tone", "warm")
        city = profile.get("city_name", "Locația ta")

        instruction = f"""Ești Lora, asistenta inteligentă a lui {name}.
Generezi un Morning Briefing COMPLET, PRIORITIZAT și ELEGANT pentru Telegram.

STIL: Modern Assistant (Structurat dar uman). 
- Folosește linii separatoare: ━━━━━━━━━━━━━━━━━━━━
- Antet cu data și locația (Locația ta actuală: {city}).
- Secțiuni clare cu titluri în MAJUSCULE (ex: 🎯 PRIORITĂȚI).
- Ton: {tone}, Romglish natural.

CUPRINS (Include doar dacă există date):
1. ANTET: Ziua curentă | {city}. (Folosește datele meteo: {briefing_data.get('weather')}).
2. 🎓 PROGRAM ACADEMIC: Cursuri azi (Ora, Sala, Materia).
3. 📅 EVENIMENTE: Calendar iCloud (ora și titlu) + Remindere critice.
4. 🎯 PRIORITĂȚI: Task-uri High și Medium. OBLIGATORIU: Scrie titlul complet al taskului și proiectul în paranteze pătrate, ex: "Faza 8 — Intelligence layer [Proiect: Lora]". NU TĂIA titlul.
5. 💰 SITUAȚIA FINANCIARĂ: Balanța reală din date.
6. 🔥 HABIT STREAKS: Menționează skill-urile cu streak.
7. 🧠 MEMORY LANE: O referință la progresul tău pe termen lung.
8. 💡 LORA INSIGHT: Alinierea cu obiectivele tale.

REGULI STRICTE:
- MarkdownV2 (caractere RAW).
- NU TĂIA TEXTUL. Dacă începi o secțiune, trebuie să o termini complet.
- Fii specific și precis. Răspunde cu întregul conținut solicitat.
"""

        gemini_context = json.dumps(briefing_data, indent=2, cls=UniversalEncoder)

        # 4. Generate text via Gemini
        briefing_text_raw = await get_proactive_response(instruction, gemini_context)

        if not briefing_text_raw or briefing_text_raw.strip() == "":
            briefing_text_raw = "Bună dimineața! Se pare că azi e o zi liberă sau nu am date noi. Bucură-te de liniște! ☀️"

        # Add header
        day_ro: dict[str, str] = {
            "Monday": "Luni",
            "Tuesday": "Marți",
            "Wednesday": "Miercuri",
            "Thursday": "Joi",
            "Friday": "Vineri",
            "Saturday": "Sâmbătă",
            "Sunday": "Duminică",
        }
        day_name = day_ro.get(today.strftime("%A"), today.strftime("%A"))
        date_str = escape_md(f"{day_name}, {today.strftime('%d %B %Y')}")

        header = [
            "━━━━━━━━━━━━━━━",
            f"☀️ *Bună dimineața, {escape_md(name)}\\!*",
            f"_{date_str}_",
            "━━━━━━━━━━━━━━━\n",
        ]

        final_text = "\n".join(header) + safe_markdown(briefing_text_raw)

        # 5. Send Telegram text message
        chunks = split_message(final_text)
        for chunk in chunks:
            try:
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=chunk,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            except Exception as e:
                print(
                    f"Morning brief MarkdownV2 failed, falling back to plain: {e}",
                    flush=True,
                )
                await application.bot.send_message(chat_id=TELEGRAM_USER_ID, text=chunk)

        # 6. Generate and send Voice Podcast
        try:
            from bot.tts import text_to_speech

            print("🎙️ Starting TTS generation for Morning Briefing...", flush=True)

            podcast_instruction = f"""Ești Lora. Generezi un podcast vocal scurt bazat pe briefing-ul de azi. 
Scrie să sune natural când e citit cu voce, EXCLUSIV în limba română (MAXIM 200 cuvinte).
Salută-l pe {name}, prezintă prioritățile și încheie motivant. Fără liste, fără titluri."""

            tts_input = await get_proactive_response(
                podcast_instruction, briefing_text_raw
            )
            voice_file = await text_to_speech(
                tts_input or briefing_text_raw, podcast_mode=True
            )

            with open(voice_file, "rb") as f:
                await application.bot.send_voice(
                    chat_id=TELEGRAM_USER_ID,
                    voice=f,
                    caption="🎙️ *Lora Podcast: Briefing Prioritizat*",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            if os.path.exists(voice_file):
                os.remove(voice_file)
        except Exception as e:
            print(f"❌ Podcast generation error: {e}", flush=True)

        # 7. Mark as sent
        await profile_queries.update_user_profile(
            pool, TELEGRAM_USER_ID, last_briefing_date=today
        )
        print(f"Prioritized morning briefing sent and logged for {today}.", flush=True)

        # 8. Interactive Day Plan Flow
        from core.state import set_state

        await application.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text="Cum vrei să-ți arate ziua azi? Spune-mi vocal sau în scris 🗓",
        )
        await set_state(pool, "awaiting_day_plan_input", "day_plans", "generate", None)
        print("Awaiting day plan input state set.", flush=True)

    except Exception as e:
        import traceback
        import logging

        logger = logging.getLogger(__name__)
        logger.error(
            f"CRITICAL error in send_morning_briefing: {e}\n{traceback.format_exc()}"
        )
        print(f"CRITICAL error in send_morning_briefing: {e}", flush=True)
        traceback.print_exc()
        # Try to notify user if possible
        try:
            await application.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=f"❌ Eroare la briefing: {str(e)[:200]}",
            )
        except Exception as notify_error:
            print(f"Could not notify user of error: {notify_error}", flush=True)


async def check_contextual_nudges(application, pool):
    """Hourly check for proactive context-based nudges."""
    try:
        user_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(user_tz)
        today = now.date()
        hour = now.hour

        # 1. Deadline Tomorrow (Alert at 19:00+)
        if hour >= 19:
            if await _should_send_nudge(pool, "deadline_tomorrow"):
                tomorrow = today + timedelta(days=1)
                async with pool.acquire() as conn:
                    tasks = await conn.fetch(
                        "SELECT title FROM tasks WHERE due_date = $1 AND status != 'done' AND deleted_at IS NULL LIMIT 3",
                        tomorrow,
                    )
                    if tasks:
                        titles = ", ".join([t["title"] for t in tasks])
                        msg = f"🔔 Reminder: Ai task-uri cu deadline mâine: {titles}. Te ocupi de ele diseară?"
                        await application.bot.send_message(
                            chat_id=TELEGRAM_USER_ID, text=msg
                        )
                        await _mark_nudge_sent(pool, "deadline_tomorrow")

        # 2. No expenses logged (48h)
        if await _should_send_nudge(pool, "no_expenses_48h"):
            async with pool.acquire() as conn:
                last_tx = await conn.fetchval("SELECT MAX(created_at) FROM finances")
                if not last_tx or last_tx < now - timedelta(hours=48):
                    msg = "💸 Ai uitat să loghezi cheltuielile? Nu am mai văzut nicio activitate de 2 zile."
                    await application.bot.send_message(
                        chat_id=TELEGRAM_USER_ID, text=msg
                    )
                    await _mark_nudge_sent(pool, "no_expenses_48h")

        # 3. Workout streak risk (18:00+)
        if hour >= 18:
            if await _should_send_nudge(pool, "workout_streak_risk"):
                async with pool.acquire() as conn:
                    # Check if any workout logged today
                    logged_today = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM workout_logs WHERE log_date = CURRENT_DATE)"
                    )
                    if not logged_today:
                        # Check if user has any active streak
                        skills = await conn.fetch(
                            "SELECT id FROM skills WHERE name ILIKE '%workout%' OR name ILIKE '%sala%' OR name ILIKE '%sport%'"
                        )
                        for s in skills:
                            streak = await skill_queries.get_skill_streak(pool, s["id"])
                            if streak >= 1:
                                msg = "💪 Streak-ul tău e în pericol! Nu ai logat antrenamentul azi. Mai ai timp pentru o sesiune scurtă."
                                await application.bot.send_message(
                                    chat_id=TELEGRAM_USER_ID, text=msg
                                )
                                await _mark_nudge_sent(pool, "workout_streak_risk")
                                break

        # 4. Budget Exceeded
        if await _should_send_nudge(pool, "budget_exceeded"):
            budgets = await finance_queries.get_budget_status(pool)
            for b in budgets:
                if float(b["current_spent"]) > float(b["monthly_limit"]):
                    msg = f"⚠️ Atenție: Ai depășit bugetul pentru {b['category']}\\! (Limită: {b['monthly_limit']} RON)"
                    await application.bot.send_message(
                        chat_id=TELEGRAM_USER_ID,
                        text=msg,
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )
                    await _mark_nudge_sent(pool, "budget_exceeded")
                    break

    except Exception as e:
        print(f"Error in check_contextual_nudges: {e}", flush=True)


async def _should_send_nudge(pool, nudge_type: str) -> bool:
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM sent_nudges WHERE nudge_type = $1 AND nudge_date = CURRENT_DATE)",
            nudge_type,
        )
        return not exists


async def _mark_nudge_sent(pool, nudge_type: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sent_nudges (nudge_type) VALUES ($1) ON CONFLICT DO NOTHING",
            nudge_type,
        )


async def send_eod_reflection(application, pool, force=False):
    """EOD Reflection: Start interactive flow with Mood question."""
    try:
        user_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(user_tz)
        today = now.date()

        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if not force and profile.get("last_eod_date") == today:
            return

        name = profile.get("name", "User")
        print(f"Starting interactive EOD reflection for {today}...", flush=True)

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [
            [
                InlineKeyboardButton("🚀 Productivă", callback_data="eod:mood:great"),
                InlineKeyboardButton("😐 Medie", callback_data="eod:mood:neutral"),
                InlineKeyboardButton("📉 Slabă", callback_data="eod:mood:terrible"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        report_status = await send_daily_report(application, pool)
        report_text = ""
        if report_status:
            report_text = "\n\n_Raport trimis la Council ✓_"
        elif os.getenv("COUNCIL_API_URL"):
             report_text = "\n\n_Raport Council: eșuat ✗_"

        message = (
            f"🌙 *Bună seara, {escape_md(name)}\\!* \n\n"
            "E timpul pentru o scurtă reflexie\\. *Cum a fost ziua ta azi?*"
            + report_text
        )

        await application.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        from core.state import set_state

        await set_state(pool, "awaiting_eod_mood", "eod", "mood", None)

    except Exception as e:
        import traceback

        print(f"CRITICAL error in send_eod_reflection: {e}", flush=True)
        traceback.print_exc()


async def check_eod_timeout(application, pool):
    """Checks if EOD reflection was completed; marks as skipped if not."""
    try:
        from core.state import get_state, clear_state

        state = await get_state(pool)

        if state and state.get("module") == "eod":
            print("EOD Reflection timed out. Marking as skipped.", flush=True)
            await clear_state(pool)

            user_tz = pytz.timezone(TIMEZONE)
            today = datetime.now(user_tz).date()

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO journal_entries (entry_date, skipped)
                    VALUES ($1, TRUE)
                    ON CONFLICT (entry_date) DO UPDATE SET skipped = TRUE
                    """,
                    today,
                )

                # Also mark profile so it doesn't trigger again
                await conn.execute(
                    "UPDATE user_profile SET last_eod_date = $1 WHERE telegram_id = $2",
                    today,
                    TELEGRAM_USER_ID,
                )

            await application.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text="Sesiunea de reflexie a expirat\\. O seară liniștită\\! 🌙",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
    except Exception as e:
        print(f"Error in check_eod_timeout: {e}", flush=True)

        await profile_queries.update_user_profile(
            pool, TELEGRAM_USER_ID, last_eod_date=today
        )
        print(f"EOD reflection sent for {today}.", flush=True)

    except Exception as e:
        import traceback

        print(f"CRITICAL error in send_eod_reflection: {e}", flush=True)
        traceback.print_exc()


async def send_journal_night(application, pool):
    """Journal Night: 3 reflection questions + mood + tomorrow planning."""
    try:
        user_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(user_tz)
        today = now.date()

        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if profile.get("last_journal_date") == today:
            print(f"Journal night already sent for {today} — skipping.", flush=True)
            return

        name = profile.get("name", "User")
        print(f"Starting journal night for {today}...", flush=True)

        from db.queries.tasks import get_completed_tasks_today

        v_tasks = await get_completed_tasks_today(pool)
        task_count = len(v_tasks)
        task_status = (
            f"{task_count} tasks completate"
            if task_count > 0
            else "niciun task completat"
        )

        message = (
            f"🌙 *Bună seara, {escape_md(name)}.*\n\n"
            f"Azi ai {task_status}.\n\n"
            "Răspunde la cele 3 întrebări ca să închidem ziua:\n"
            "*1.* Ce a mers bine azi?\n"
            "*2.* Ce ai vrea să faci diferit?\n"
            "*3.* Cum vrei să arate ziua de mâine? \\(tasks, program, priorități\\)\n\n"
            "📌 *La ce oră te trezești mâine?* \\(ex: la 7, pe la 8:30\\)"
        )

        try:
            await application.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=safe_markdown(message),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as e:
            print(
                f"Evening/Journal message MarkdownV2 failed, falling back: {e}",
                flush=True,
            )
            await application.bot.send_message(chat_id=TELEGRAM_USER_ID, text=message)

        try:
            from bot.tts import text_to_speech
            import os

            tts_text = f"Bună seara, {name}. {task_status}. Răspunde la cele 3 întrebări ca să închidem ziua."
            voice_file = await text_to_speech(tts_text)
            with open(voice_file, "rb") as f:
                await application.bot.send_voice(
                    chat_id=TELEGRAM_USER_ID,
                    voice=f,
                    caption="🎙️ *Lora: Journal Night*",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            if os.path.exists(voice_file):
                os.remove(voice_file)
        except Exception as e:
            print(f"Journal night TTS failed: {e}", flush=True)

        from core.state import set_state

        await set_state(pool, "awaiting_evening_response", "journal", "save", None)
        await profile_queries.update_user_profile(
            pool, TELEGRAM_USER_ID, last_journal_date=today
        )
        print(f"Journal night initiated for {today}.", flush=True)

    except Exception as e:
        import traceback

        print(f"CRITICAL error in send_journal_night: {e}", flush=True)
        traceback.print_exc()


async def check_class_reminders(application, pool) -> None:
    """Verifică cursurile care încep în 15 minute și trimite reminder."""
    try:
        from db.queries.schedule import get_upcoming_classes, is_vacation
        from bot.formatter import escape_md
        from telegram.constants import ParseMode

        # Skip reminders during vacation
        if await is_vacation(pool):
            return

        # We check slightly ahead (16m) to ensure we don't miss it between 5m intervals
        classes = await get_upcoming_classes(pool, minutes_ahead=16)

        for c in classes:
            # 1. Verificare SELECT (ÎNAINTE de trimitere)
            existing = await pool.fetchval(
                """
                SELECT 1 FROM schedule_reminders_sent
                WHERE schedule_id = $1 AND reminder_date = CURRENT_DATE
            """,
                c["id"],
            )

            if existing:
                continue  # skip — deja trimis azi

            start = c["start_time"].strftime("%H:%M")
            end = c["end_time"].strftime("%H:%M")
            room = (
                f"Sala *{escape_md(c['room'])}*"
                if c.get("room")
                else "Sala necunoscută"
            )
            type_str = "Curs" if c["class_type"] == "curs" else "Seminar"

            msg = (
                f"🔔 *{escape_md(c['subject_name'])}* începe în 15 minute\\!\n"
                f"📖 {type_str} · `{start}–{end}`\n"
                f"📍 {room}"
            )

            from telegram import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Prezent",
                            callback_data=make_callback_data(
                                "attendance", "present", c["id"]
                            ),
                        ),
                        InlineKeyboardButton(
                            "❌ Absent",
                            callback_data=make_callback_data(
                                "attendance", "absent", c["id"]
                            ),
                        ),
                    ]
                ]
            )

            # 2. Trimite mesaj
            try:
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=msg,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=keyboard,
                )
            except Exception as e:
                print(
                    f"Class reminder MarkdownV2 failed, falling back: {e}", flush=True
                )
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=msg,
                    reply_markup=keyboard,
                )

            # 3. Loghează DUPĂ trimitere (cu ON CONFLICT DO NOTHING)
            await pool.execute(
                """
                INSERT INTO schedule_reminders_sent (schedule_id, reminder_date)
                VALUES ($1, CURRENT_DATE)
                ON CONFLICT (schedule_id, reminder_date) DO NOTHING
            """,
                c["id"],
            )

    except Exception as e:
        print(f"Error in check_class_reminders: {e}", flush=True)


async def send_weekly_review(application, pool, force=False):
    """Generates and sends the automated narrative weekly review."""
    from bot.formatter import safe_markdown, split_message
    from core.context import build_weekly_review_context
    from core.gemini import get_proactive_response

    try:
        user_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(user_tz)
        today = now.date()

        # Idempotency check
        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if not force and profile.get("last_weekly_review_date") == today:
            print(f"Weekly review already sent for {today} — skipping.", flush=True)
            return

        # Period: Last 7 days including today
        days_to_monday = today.weekday()
        start_date = today - timedelta(days=days_to_monday)
        end_date = today

        print(
            f"Starting narrative weekly review for {start_date} to {end_date}...",
            flush=True,
        )

        context_data = await build_weekly_review_context(pool, start_date, end_date)

        instruction = """Ești Lora, asistenta personală a utilizatorului. Generezi un WEEKLY REVIEW narativ, empatic și inteligent.
        NU trimite o listă de cifre sec. Transformă datele brute într-o poveste a săptămânii care tocmai se încheie.
        
        CONSTRUCȚIE:
        - Ce a mers bine (realizări, sport, productivitate).
        - Ce poate fi îmbunătățit (cheltuieli, task-uri amânate).
        - FOCUS RECOMANDAT: O singură sugestie clară pentru săptămâna care urmează.
        
        Ton: Romglish, cald, direct. Fără introduceri lungi.
        Formatare: MarkdownV2 (fără backslash-uri de escapare inutile la date)."""

        report_content = await get_proactive_response(
            instruction, json.dumps(context_data, default=str)
        )

        if not report_content:
            return

        # Save to DB
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO weekly_reviews (week_start, week_end, content)
                VALUES ($1, $2, $3)
                """,
                start_date,
                end_date,
                report_content,
            )

            # Update user profile
            await conn.execute(
                "UPDATE user_profile SET last_weekly_review_date = $1 WHERE telegram_id = $2",
                today,
                TELEGRAM_USER_ID,
            )

        # Send to user
        header = f"📊 *Weekly Review: {start_date.strftime('%d %b')} — {end_date.strftime('%d %b')}*\\n\\n"
        final_text = header + safe_markdown(report_content)

        chunks = split_message(final_text)
        for chunk in chunks:
            await application.bot.send_message(
                chat_id=TELEGRAM_USER_ID, text=chunk, parse_mode=ParseMode.MARKDOWN_V2
            )

    except Exception as e:
        print(f"CRITICAL error in send_weekly_review: {e}", flush=True)
        import traceback

        traceback.print_exc()

        pass

        # 6. Send Voice Version (TTS)
        try:
            from bot.tts import text_to_speech
            import os

            # Clean text for TTS
            tts_clean = (
                report_content.replace("*", "")
                .replace("📊", "")
                .replace("✅", "")
                .replace("🔁", "")
                .replace("💰", "")
                .replace("📈", "")
                .replace("🔍", "")
                .strip()
            )
            voice_file = await text_to_speech(tts_clean, podcast_mode=True)
            with open(voice_file, "rb") as f:
                await application.bot.send_voice(
                    chat_id=TELEGRAM_USER_ID,
                    voice=f,
                    caption="🎙️ *Lora: Weekly Review*",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            if os.path.exists(voice_file):
                os.remove(voice_file)
        except Exception as ve:
            print(f"Weekly review voice error: {ve}", flush=True)

        # 7. Update Idempotency
        await profile_queries.update_user_profile(
            pool, TELEGRAM_USER_ID, last_weekly_review_date=today
        )
        print(f"Weekly review sent and logged for {today}.", flush=True)

    except Exception as e:
        import traceback

        print(f"CRITICAL error in send_weekly_review: {e}", flush=True)
        traceback.print_exc()


async def send_monthly_review(application, pool) -> None:
    """Aggregates monthly data and sends a reflective review on the 1st of each month."""
    from datetime import datetime, date
    import calendar
    import pytz
    from core.config import TIMEZONE, TELEGRAM_USER_ID
    from telegram.constants import ParseMode

    try:
        user_tz = pytz.timezone(TIMEZONE)
        today = datetime.now(user_tz).date()

        # 1. Idempotency Check
        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if profile.get("last_monthly_review_date") == today:
            print(f"Monthly review already sent for {today} — skipping.", flush=True)
            return

        # 2. Date Range (entire previous month)
        prev_month = today.month - 1 if today.month > 1 else 12
        prev_year = today.year if today.month > 1 else today.year - 1
        _, last_day = calendar.monthrange(prev_year, prev_month)
        start_date = date(prev_year, prev_month, 1)
        end_date = date(prev_year, prev_month, last_day)

        month_name_ro = {
            1: "Ianuarie",
            2: "Februarie",
            3: "Martie",
            4: "Aprilie",
            5: "Mai",
            6: "Iunie",
            7: "Iulie",
            8: "August",
            9: "Septembrie",
            10: "Octombrie",
            11: "Noiembrie",
            12: "Decembrie",
        }.get(prev_month, str(prev_month))

        print(f"Starting monthly review for {month_name_ro} {prev_year}...", flush=True)

        # 3. Aggregated Data Collection
        task_stats = await task_queries.get_monthly_task_stats(
            pool, start_date, end_date
        )

        async with pool.acquire() as conn:
            finance_rows = await conn.fetch(
                """
                SELECT type, SUM(amount) as total
                FROM finances
                WHERE tx_date BETWEEN $1 AND $2
                GROUP BY type
                """,
                start_date,
                end_date,
            )
        finance_by_type = {r["type"]: float(r["total"]) for r in finance_rows}
        total_expense = finance_by_type.get("expense", 0)

        prev_month_stats = await finance_queries.get_monthly_summary(
            pool, prev_month, prev_year
        )

        import db.queries.mood as mood_queries

        monthly_moods = await mood_queries.get_monthly_mood_distribution(
            pool, start_date, end_date
        )
        mood_labels = {
            "great": "super",
            "good": "bine",
            "neutral": "ok",
            "okay": "ok",
            "bad": "slab",
            "terrible": "rău",
        }
        mood_parts = [
            f"{count} zile {mood_labels.get(m.lower(), m)}"
            for m, count in monthly_moods.items()
            if count > 0
        ]
        mood_summary = (
            f"😊 Mood: {', '.join(mood_parts)}"
            if mood_parts
            else "😊 Mood: date insuficiente"
        )

        health_month = await health_queries.get_health_history(pool, 31)
        health_month = [
            h
            for h in health_month
            if start_date <= h.get("log_date", date(2000, 1, 1)) <= end_date
        ]
        avg_sleep = sum(
            h["sleep_hours"] for h in health_month if h.get("sleep_hours")
        ) / max(len([h for h in health_month if h.get("sleep_hours")]), 1)
        avg_water = sum(h["water_ml"] for h in health_month if h.get("water_ml")) / max(
            len([h for h in health_month if h.get("water_ml")]), 1
        )
        weights = [h["weight_kg"] for h in health_month if h.get("weight_kg")]
        weight_trend = ""
        if len(weights) >= 2:
            weight_trend = (
                "↑"
                if weights[-1] > weights[0]
                else "↓"
                if weights[-1] < weights[0]
                else "→"
            )

        from modules.insights import generate_insights

        patterns = await generate_insights(pool)
        patterns_section = ""
        if patterns and "nu am suficiente date" not in patterns.lower():
            patterns_section = f"\n🧠 *Patterns observate*\n{patterns}"

        try:
            from core.correlations import compute_correlations

            raw_correlations = await compute_correlations(pool)
            if raw_correlations:
                strong_count = sum(
                    1 for c in raw_correlations if c.get("strength") == "puternică"
                )
                patterns_section += f"\n🧬 *Corelații:* {len(raw_correlations)} pattern-uri, {strong_count} puternice"
        except Exception:
            pass

        from db.queries.goals import get_all_goals

        goals = await get_all_goals(pool)
        active_goals = [g for g in goals if g.get("status") == "active"]
        goals_summary = (
            f"🎯 {len(active_goals)} goals active"
            if active_goals
            else "🎯 Niciun goal activ"
        )

        finance_vs_prev = ""
        if prev_month_stats.get("expense", 0) > 0:
            diff = total_expense - prev_month_stats["expense"]
            sign = "+" if diff > 0 else ""
            finance_vs_prev = f" (vs luna trecută: {sign}{int(diff)} RON)"

        async with pool.acquire() as conn:
            event_count = await conn.fetchval(
                "SELECT COUNT(*) FROM events WHERE event_date BETWEEN $1 AND $2",
                start_date,
                end_date,
            )

        data_summary = f"""
LUNA: {month_name_ro} {prev_year}
📊 Tasks: {task_stats["completed"]} completate din {task_stats["created"]} create ({int(task_stats["completed"] / max(task_stats["created"], 1) * 100)}%)
💰 Finanțe: {int(total_expense)} RON cheltuiți{finance_vs_prev}
😊 Mood: {mood_summary}
😴 Sănătate: somn mediu {avg_sleep:.1f}h, apă medie {avg_water / 1000:.1f}L{", greutate " + weight_trend if weight_trend else ""}
🎯 Goals active: {len(active_goals)}
📅 Evenimente luna aceasta: {event_count}
PATTERNS: {patterns_section}
"""
        from core.gemini import get_proactive_response

        system_instruction = f"""
Ești Lora, asistenta personală a lui {profile.get("name", "User")}.
Generează un monthly review structurat în română.
Tone: reflectiv, direct, calm, fără hype.
Interzis: bravos, vibes, wins, achievements.

Structură FIXĂ (MarkdownV2):
📊 *Review Lunar — {month_name_ro} {prev_year}*

✅ *Tasks*: {task_stats["completed"]} completate din {task_stats["created"]} ({int(task_stats["completed"] / max(task_stats["created"], 1) * 100)}%)

🔁 *Habits*: [top 2 consistente] / [cel mai ratat — vezi din date dacă ai destule]

💰 *Finanțe*
{int(total_expense)} RON cheltuiți{finance_vs_prev}

😊 *Mood*: {mood_summary}

😴 *Sănătate*: somn mediu {avg_sleep:.1f}h · apă medie {avg_water / 1000:.1f}L{", greutate " + weight_trend if weight_trend else ""}

🎯 *Goals*: {goals_summary}

📅 *Evenimente*: {event_count}

{patterns_section}

🔍 *Pattern observat*: [Dacă există corelații semnificative — somn < 6.5h × productivitate, zile cu apă < 1.5L × mood, etc. Max 2 propoziții factuale.]

💡 *Luna viitoare*: [1 lucru specific și concret — ales din date, nu generic]

MAX 200 cuvinte. DOAR textul review-ului, fără introducere/concluzie extra.
"""
        review_text = await get_proactive_response(system_instruction, data_summary)

        if not review_text:
            review_text = f"📊 *Review Lunar — {month_name_ro} {prev_year}*\n\nLuna aceasta ai completat {task_stats['completed']} tasks din {task_stats['created']} create."

        await application.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=safe_markdown(review_text),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        try:
            from bot.tts import text_to_speech
            import os

            tts_clean = (
                review_text.replace("*", "")
                .replace("📊", "")
                .replace("✅", "")
                .replace("🔁", "")
                .replace("💰", "")
                .replace("📈", "")
                .replace("🔍", "")
                .replace("😊", "")
                .replace("😴", "")
                .replace("🎯", "")
                .replace("📅", "")
                .strip()
            )
            voice_file = await text_to_speech(tts_clean, podcast_mode=True)
            with open(voice_file, "rb") as f:
                await application.bot.send_voice(
                    chat_id=TELEGRAM_USER_ID,
                    voice=f,
                    caption="🎙️ *Lora: Monthly Review*",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            if os.path.exists(voice_file):
                os.remove(voice_file)
        except Exception as ve:
            print(f"Monthly review voice error: {ve}", flush=True)

        await profile_queries.update_user_profile(
            pool, TELEGRAM_USER_ID, last_monthly_review_date=today
        )
        print(f"Monthly review sent and logged for {today}.", flush=True)

    except Exception as e:
        import traceback

        print(f"CRITICAL error in send_monthly_review: {e}", flush=True)
        traceback.print_exc()


async def send_weekly_finance_summary(application, pool) -> None:
    """Sends a detailed finance breakdown on Monday morning."""
    from datetime import timedelta, datetime
    import pytz
    from core.config import TIMEZONE, TELEGRAM_USER_ID
    from bot.formatter import escape_md
    from telegram.constants import ParseMode

    try:
        user_tz = pytz.timezone(TIMEZONE)
        today = datetime.now(user_tz).date()

        # 1. Idempotency Check
        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if profile.get("last_finance_summary_date") == today:
            print(f"Finance summary already sent for {today} — skipping.", flush=True)
            return

        print(f"Starting weekly finance summary for {today}...", flush=True)

        # 2. Date Range (Previous Monday to Sunday)
        start_date = today - timedelta(days=7)
        end_date = today - timedelta(days=1)

        # 3. Aggregated Data Collection
        finance_summary = await finance_queries.get_weekly_finance_summary(
            pool, start_date, end_date
        )

        async with pool.acquire() as conn:
            weekly_breakdown = await conn.fetch(
                """
                SELECT category, SUM(amount) as total 
                FROM finances 
                WHERE type = 'expense' AND tx_date BETWEEN $1 AND $2 
                GROUP BY category 
                ORDER BY total DESC
                """,
                start_date,
                end_date,
            )

        # Calculate monthly budget remaining
        now = datetime.now(user_tz)
        monthly_stats = await finance_queries.get_monthly_summary(
            pool, now.month, now.year
        )
        async with pool.acquire() as conn:
            total_limit = await conn.fetchval(
                "SELECT SUM(monthly_limit) FROM budget_limits"
            )

        budget_remaining = (
            (float(total_limit) - float(monthly_stats["expense"])) if total_limit else 0
        )

        finance_lines = []
        for b in weekly_breakdown[:5]:
            finance_lines.append(
                f"• {escape_md(b['category'])}: `{int(b['total'])} RON`"
            )

        finance_ctx = "\n".join(finance_lines)

        # 4. Format Message
        message = (
            f"💰 *Rezumat Financiar Săptămânal*\n"
            f"_{start_date.strftime('%d.%m')} — {end_date.strftime('%d.%m')}_\n\n"
            f"*Top Cheltuieli:*\n"
            f"{finance_ctx}\n"
            f"────────────\n"
            f"💵 Total săptămână: `{int(finance_summary['total'])} RON`\n"
            f"📉 Buget lunar rămas: `{int(budget_remaining)} RON`"
        )

        # 5. Send Telegram message
        await application.bot.send_message(
            chat_id=TELEGRAM_USER_ID, text=message, parse_mode=ParseMode.MARKDOWN_V2
        )

        # 6. Update Idempotency
        await profile_queries.update_user_profile(
            pool, TELEGRAM_USER_ID, last_finance_summary_date=today
        )
        print(f"Weekly finance summary sent and logged for {today}.", flush=True)

    except Exception as e:
        import traceback

        print(f"CRITICAL error in send_weekly_finance_summary: {e}", flush=True)
        traceback.print_exc()


async def reset_budget_alerts(application, pool) -> None:
    """Resets budget alert flags on the 1st of every month."""
    print("Resetting budget alert flags for the new month...", flush=True)
    await finance_queries.reset_all_budget_alerts(pool)
    print("Budget alert flags reset successfully.", flush=True)


async def check_event_reminders(application, pool):
    """Checks for upcoming events and sends reminders ~30 min before."""
    try:
        from telegram.constants import ParseMode
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton

        events = await event_queries.get_events_needing_reminder(
            pool, minutes_before=30
        )

        for e in events:
            event_type = e.get("event_type", "event")
            is_reminder = event_type == "reminder"

            if is_reminder:
                msg = f"🔔 *Reminder:* {escape_md(e['title'])}"
            else:
                remind_min = e.get("remind_before_minutes", 30)
                time_str = (
                    e["event_time"].strftime("%H:%M")
                    if e.get("event_time")
                    else "toată ziua"
                )
                msg = f"🔔 *{escape_md(e['title'])}* în {remind_min} minute\n⏰ {time_str}"
                if e.get("description"):
                    msg += f"\n📝 {escape_md(e['description'])}"

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "👍 Ok",
                            callback_data=make_callback_data(
                                "event", "reminder", "ack", e["id"]
                            ),
                        ),
                        InlineKeyboardButton(
                            "📝 Note",
                            callback_data=make_callback_data("event", "note", e["id"]),
                        ),
                    ]
                ]
            )

            try:
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=msg,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=keyboard,
                )
            except Exception as e:
                print(
                    f"Event reminder MarkdownV2 failed, falling back: {e}", flush=True
                )
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=msg,
                    reply_markup=keyboard,
                )

            await event_queries.mark_event_reminded(pool, e["id"])
            print(f"Event reminder sent for: {e['title']}", flush=True)

    except Exception as e:
        print(f"Error in check_event_reminders: {e}", flush=True)


async def check_event_day_reminders(application, pool):
    """Checks for events tomorrow and sends 1-day reminders at 20:00."""
    try:
        from telegram.constants import ParseMode
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        from datetime import timedelta

        tomorrow = (datetime.now().date()) + timedelta(days=1)
        events = await event_queries.get_events_for_day_reminder(pool, tomorrow)

        for e in events:
            time_str = (
                e["event_time"].strftime("%H:%M")
                if e.get("event_time")
                else "toată ziua"
            )
            msg = f"📅 *Mâine:* {escape_md(e['title'])}\n⏰ {time_str}"
            if e.get("description"):
                msg += f"\n📝 {escape_md(e['description'])}"

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "👍 Ok",
                            callback_data=make_callback_data(
                                "event", "day", "ack", e["id"]
                            ),
                        ),
                    ]
                ]
            )

            try:
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=msg,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=keyboard,
                )
            except Exception as e:
                print(
                    f"Event reminder MarkdownV2 failed, falling back: {e}", flush=True
                )
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=msg,
                    reply_markup=keyboard,
                )

            await event_queries.mark_day_reminder_sent(pool, e["id"], tomorrow)
            print(f"Day reminder sent for: {e['title']}", flush=True)

        print(f"Day reminder sent for {len(events)} events tomorrow", flush=True)

    except Exception as e:
        print(f"Error in check_event_day_reminders: {e}", flush=True)
        import traceback

        traceback.print_exc()


async def check_habit_reminders(application, pool) -> None:
    """Checks habits due today that haven't been logged and sends reminders."""
    try:
        from telegram.constants import ParseMode

        today = datetime.now().weekday()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT h.id, h.name, h.streak_count
                FROM habits h
                WHERE h.is_active = TRUE
                  AND $1 = ANY(h.target_days)
                  AND NOT EXISTS (
                    SELECT 1 FROM habit_logs hl
                    WHERE hl.habit_id = h.id AND hl.log_date = CURRENT_DATE
                  )
                ORDER BY h.streak_count ASC, h.name ASC
                """,
                today,
            )

        if not rows:
            return

        habit_list = "\n".join(f"• {escape_md(h['name'])}" for h in rows)
        msg = (
            f"🔔 *Habite de făcut azi:*\n{habit_list}\n\n"
            f"Fă click pe ce ai realizat sau sări peste."
        )

        from telegram import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard_buttons = [
            [
                InlineKeyboardButton(
                    f"✅ {h['name'][:15]}",
                    callback_data=make_callback_data("habit", "done", h["id"]),
                )
            ]
            for h in rows[:5]
        ]

        if len(rows) > 5:
            keyboard_buttons.append(
                [
                    InlineKeyboardButton(
                        "📋 Vezi toate",
                        callback_data=make_callback_data("list", "habits"),
                    )
                ]
            )

        keyboard = InlineKeyboardMarkup(keyboard_buttons)

        await application.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=msg,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )

        print(f"Habit reminder sent for {len(rows)} habits", flush=True)

    except Exception as e:
        print(f"Error in check_habit_reminders: {e}", flush=True)
        import traceback

        traceback.print_exc()


async def check_task_deadline_reminders(application, pool) -> None:
    """Checks for tasks due today or overdue and sends reminders."""
    try:
        from telegram.constants import ParseMode

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT t.id, t.title, t.due_date, t.priority, p.name as project_name
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.status = 'pending' AND t.deleted_at IS NULL
                  AND t.due_date IS NOT NULL
                  AND t.due_date <= CURRENT_DATE + INTERVAL '1 day'
                ORDER BY 
                    CASE t.priority 
                        WHEN 'high' THEN 1 
                        WHEN 'medium' THEN 2 
                        ELSE 3 
                    END,
                    t.due_date ASC
                LIMIT 10
                """
            )

        if not rows:
            return

        overdue = [t for t in rows if t["due_date"] < datetime.now().date()]
        due_today = [t for t in rows if t["due_date"] == datetime.now().date()]

        from telegram import InlineKeyboardMarkup, InlineKeyboardButton

        if overdue:
            overdue_list = "\n".join(
                f"• [{p}] {escape_md(t['title'])}"
                for t, p in [
                    (t, t.get("project_name") or "fără proiect") for t in overdue
                ]
            )
            msg = f"🚨 *Task-uri peste termen ({len(overdue)}):*\n{overdue_list}\n"
        else:
            msg = ""

        if due_today:
            due_list = "\n".join(
                f"• [{p}] {escape_md(t['title'])}"
                for t, p in [
                    (t, t.get("project_name") or "fără proiect") for t in due_today
                ]
            )
            msg += f"📋 *Task-uri pentru azi ({len(due_today)}):*\n{due_list}"

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Mark done",
                        callback_data=make_callback_data("task", "reminder", "dismiss"),
                    ),
                    InlineKeyboardButton(
                        "📝 Note",
                        callback_data=make_callback_data("view", "pending", "tasks"),
                    ),
                ]
            ]
        )

        await application.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=msg,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )

        print(
            f"Task deadline reminder sent: {len(overdue)} overdue, {len(due_today)} due today",
            flush=True,
        )

    except Exception as e:
        print(f"Error in check_task_deadline_reminders: {e}", flush=True)
        import traceback

        traceback.print_exc()


async def check_budget_forecast(application, pool):
    """Weekly proactive budget check (Thursdays at 09:00)."""
    try:
        from db.queries.finance import get_budget_forecast
        from bot.formatter import escape_md

        forecasts = await get_budget_forecast(pool)
        if not forecasts:
            return

        alerts = []
        for f in forecasts:
            limit = float(f["monthly_limit"]) if f.get("monthly_limit") else None
            if not limit:
                continue

            projected = float(f["projected_total"] or 0)
            pct = (projected / limit) * 100

            if pct >= 85:
                icon = "🔴" if pct >= 100 else "🟡"
                alerts.append(
                    f"• {escape_md(f['category'])}: proiectat {int(projected)}/{int(limit)} RON ({int(pct)}%) {icon}"
                )

        if alerts:
            message = "📈 *La ritmul actual:*\n" + "\n".join(alerts)
            await application.bot.send_message(
                chat_id=TELEGRAM_USER_ID, text=message, parse_mode=ParseMode.MARKDOWN_V2
            )
            print(f"Budget forecast alert sent with {len(alerts)} items.", flush=True)

    except Exception as e:
        print(f"Error in check_budget_forecast: {e}", flush=True)


async def check_proactive_insights(application, pool) -> None:
    try:
        from modules.insights import run_proactive_insights

        await run_proactive_insights(pool, application.bot)
    except Exception as e:
        import traceback

        print(f"CRITICAL error in check_proactive_insights: {e}", flush=True)
        traceback.print_exc()


def setup_scheduler(application, pool):
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    global _global_scheduler
    _global_scheduler = scheduler

    m_h, m_m = map(int, MORNING_BRIEFING_TIME.split(":"))
    e_h, e_m = map(int, EOD_REFLECTION_TIME.split(":"))

    # 1. Daily check at 05:00 to schedule briefing
    scheduler.add_job(
        check_wake_time_and_schedule,
        "cron",
        hour=5,
        minute=0,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    # 1b. Daily history cleanup at 04:00
    scheduler.add_job(
        cleanup_history_job,
        "cron",
        hour=4,
        minute=0,
        misfire_grace_time=3600,
        args=[pool],
    )

    # 1c. Weekly profile update on Monday at 06:00
    scheduler.add_job(
        update_profile_job,
        "cron",
        day_of_week="mon",
        hour=6,
        minute=0,
        misfire_grace_time=7200,
        args=[pool],
    )

    # 3. EOD Reflection - short daily summary at configured EOD time
    scheduler.add_job(
        send_eod_reflection,
        "cron",
        hour=e_h,
        minute=e_m,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    # 3c. EOD Timeout Check - 30 minutes after EOD reflection
    timeout_time = (
        datetime.combine(date.today(), time(e_h, e_m)) + timedelta(minutes=30)
    ).time()
    scheduler.add_job(
        check_eod_timeout,
        "cron",
        hour=timeout_time.hour,
        minute=timeout_time.minute,
        misfire_grace_time=3600,
        args=[application, pool],
    )



    # 4. Journal Night - Disabled (Consolidated into EOD Reflection)
    # j_h, j_m = map(int, JOURNAL_NIGHT_TIME.split(":"))
    # scheduler.add_job(
    #     send_journal_night,
    #     "cron",
    #     hour=j_h,
    #     minute=j_m,
    #     misfire_grace_time=3600,
    #     args=[application, pool],
    # )

    scheduler.add_job(
        send_weekly_review,
        "cron",
        day_of_week="sun",
        hour=e_h,
        minute=e_m,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    # Monthly Review - 1st of each month at 20:00
    scheduler.add_job(
        send_monthly_review,
        "cron",
        day=1,
        hour=20,
        minute=0,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    # Weekly Finance Summary: Monday, 5 mins before Morning Briefing
    f_h, f_m = m_h, (m_m - 5) % 60
    if m_m < 5:
        f_h = (m_h - 1) % 24

    scheduler.add_job(
        send_weekly_finance_summary,
        "cron",
        day_of_week="mon",
        hour=f_h,
        minute=f_m,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    scheduler.add_job(
        reset_budget_alerts,
        "cron",
        day=1,
        hour=0,
        minute=0,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    # University Attendace Warning (Insight) - Daily at 09:00
    scheduler.add_job(
        check_proactive_insights,
        "cron",
        hour=9,
        minute=0,
        misfire_grace_time=3600,
        args=[application, pool],
    )  # Re-using check_proactive_insights for this purpose

    # Class Reminders - Every 5 minutes
    scheduler.add_job(
        check_class_reminders,
        "interval",
        minutes=5,
        misfire_grace_time=60,
        args=[application, pool],
    )

    scheduler.add_job(
        check_event_reminders, "interval", minutes=5, args=[application, pool]
    )

    # Day reminder - Every day at 20:00
    scheduler.add_job(
        check_event_day_reminders,
        "cron",
        hour=20,
        minute=0,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    # Habit reminder - Daily at configured time (default 18:00)
    h_h, h_m = (
        map(int, HABIT_REMINDER_TIME.split(":"))
        if "HABIT_REMINDER_TIME" in dir()
        else (18, 0)
    )
    scheduler.add_job(
        check_habit_reminders,
        "cron",
        hour=h_h,
        minute=h_m,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    # Task deadline reminder - Daily at 09:00
    scheduler.add_job(
        check_task_deadline_reminders,
        "cron",
        hour=9,
        minute=0,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    scheduler.add_job(
        check_budget_forecast,
        "cron",
        day_of_week="thu",
        hour=9,
        minute=0,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    scheduler.add_job(
        check_proactive_insights,
        "cron",
        hour=9,
        minute=30,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    # Weekly Review - Sunday evening at 21:30
    scheduler.add_job(
        send_weekly_review,
        "cron",
        day_of_week="sun",
        hour=21,
        minute=30,
        misfire_grace_time=7200,
        args=[application, pool],
    )

    # Contextual Nudges - Hourly 10:00 - 20:00
    scheduler.add_job(
        check_contextual_nudges,
        "cron",
        hour="10-20",
        minute=0,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    # ━━━ CALENDAR SYNC ━━━
    from core.config import CALENDAR_SYNC_INTERVAL

    scheduler.add_job(
        sync_calendar_job,
        "interval",
        minutes=CALENDAR_SYNC_INTERVAL,
        args=[pool],
    )

    # ━━━ SHOPPING CLEANUP ━━━
    scheduler.add_job(
        daily_shopping_cleanup,
        "cron",
        hour=0,
        minute=0,
        misfire_grace_time=3600,
        args=[pool],
    )

    # Behavioral Profile Update - Weekly (Monday at 04:00)
    scheduler.add_job(
        update_profile_job,
        "cron",
        day_of_week="mon",
        hour=4,
        minute=0,
        misfire_grace_time=3600,
        args=[pool],
    )

    # Weather alert - every 3 hours
    scheduler.add_job(
        check_weather_alerts_job,
        "interval",
        hours=3,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    scheduler.start()
    print("Scheduler started with misfire grace periods.")
    return scheduler


async def check_weather_alerts_job(application, pool):
    """Periodic check for severe weather based on user location."""
    try:
        from modules.weather import check_weather_for_alerts
        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if not profile:
            return
        lat = profile.get("latitude")
        lon = profile.get("longitude")

        if lat and lon:
            alert_msg = await check_weather_for_alerts(float(lat), float(lon))
            if alert_msg:
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=alert_msg,
                    parse_mode="Markdown"
                )
                print(f"🌦️ Weather alert sent: {alert_msg}")
    except Exception as e:
        print(f"Error in check_weather_alerts_job: {e}")

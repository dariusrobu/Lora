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
    try:
        user_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(user_tz)
        today = now.date()

        # 1. Idempotency check
        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if profile.get('last_briefing_date') == today:
            return

        print(f"Starting morning briefing for {today}...", flush=True)

        # 2. Gather data in PARALLEL
        from modules.weather import get_weather_summary
        from db.queries.shopping import list_shopping_items
        from modules.news import fetch_tech_news
        import asyncio

        tasks_gathering = [
            task_queries.list_tasks(pool),
            event_queries.list_events(pool, today, today),
            habit_queries.list_habits(pool),
            get_weather_summary(),
            list_shopping_items(pool),
            fetch_tech_news(limit=5)
        ]
        
        results = await asyncio.gather(*tasks_gathering)
        
        all_tasks = results[0]
        events = results[1]
        habits = results[2]
        weather_info = results[3] or "Vremea nu este disponibilă acum."
        shopping_items = results[4]
        tech_news = results[5]

        overdue = [t for t in all_tasks if t['due_date'] and t['due_date'] < today]
        due_today = [t for t in all_tasks if t['due_date'] == today]
        
        # 3. Format data for Gemini
        data_summary = f"""
USER: {profile.get('name', 'User')}
TONE: {profile.get('tone', 'warm')}
DATE: {today.strftime('%A, %Y-%m-%d')}
WEATHER: {weather_info}

SHOPPING LIST:
{chr(10).join([f"  • {i['item']}" for i in shopping_items[:5]]) if shopping_items else "Empty"}

TECH & LOCAL NEWS:
{tech_news}

TASKS:
{chr(10).join([f"  • {t['title']} (OVERDUE)" for t in overdue]) if overdue else ""}
{chr(10).join([f"  • {t['title']}" for t in due_today]) if due_today else "No tasks due today."}

EVENTS:
{chr(10).join([f"  • {e['title']} at {e['event_time'].strftime('%H:%M') if e['event_time'] else 'All Day'}" for e in events]) if events else "No events scheduled today."}

HABITS:
{chr(10).join([f"  • {h['name']}" for h in habits]) if habits else "No active habits."}

MOTIVATION: Provide a short, fresh motivational quote or tip in Romanian tailored for {profile.get('name', 'User')}.
"""

        # 4. Call Gemini for synthesis
        from core.gemini import get_proactive_response
        system_instruction = f"""
You are Lora, a warm personal assistant. You are giving {profile.get('name', 'User')} their daily morning brief.
Style: {profile.get('tone', 'warm')}. 
Linguistic Style: Use a natural blend of Romanian and English ("Romglish"). Keep the base in Romanian but use English terms for tech, tasks, and modern concepts (e.g., "morning briefing", "deadline", "setup", "tasks", "catch up").

GOAL: Provide a substantial, engaging, and high-value summary of the user's day.

STRUCTURE:
1. Warm Greeting: Personal and energetic. Mention the day of the week.
2. Context: Weather and how the day looks from a high-level perspective.
3. The Game Plan: Connect tasks and events into a logical flow. Use words like "focus", "priority", "deep work".
4. Shopping: Quick nudge if anything is on the list.
5. Tech & Local News: Deep dive into the provided headlines. Summarize the most interesting bits and add a bit of your perspective.
6. Daily Motivation: A fresh quote or a small productivity tip in the same Romglish style.

Do NOT just list items. Write a cohesive, flowing narrative that feels like a friendly conversation.
Always use Telegram MarkdownV2 (bold *text*, code `text`).
"""
        from bot.formatter import safe_markdown, split_message
        raw_brief = await get_proactive_response(system_instruction, data_summary)
        print(f"DEBUG raw_brief len: {len(raw_brief) if raw_brief else 0}", flush=True)
        
        ai_brief = ""
        if raw_brief:
            ai_brief = safe_markdown(raw_brief)
        
        # Fallback to static if AI fails
        if not ai_brief:
            lines = [f"Bună dimineața, {escape_md(profile.get('name', 'User'))}! ☀️\n"]
            lines.append(f"Astăzi este {today.strftime('%A')}\\. Ai {len(due_today)} task\\-uri și {len(events)} evenimente astăzi\\.")
            ai_brief = "\n".join(lines)

        # 5. Send text message IMMEDIATELY
        chunks = split_message(ai_brief)
        for chunk in chunks:
            try:
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=chunk,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            except Exception as e:
                print(f"Morning brief MarkdownV2 failed, falling back to plain: {e}", flush=True)
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=chunk
                )

        # 6. Generate and send "podcast" (voice) in background-like manner
        # Actually, since it's an async function, we can just continue.
        # But we send the text first so the user is not waiting for TTS.
        try:
            from bot.tts import text_to_speech
            import os
            
            # Clean markdown for TTS
            tts_text = (raw_brief or ai_brief)
            # Remove MarkdownV2 escapes and formatting markers
            tts_text = tts_text.replace("*", "").replace("`", "").replace("\\.", ".").replace("\\!", "!").replace("\\-", "-").replace("\\+", "+").replace("\\_", "_")
            
            voice_file = await text_to_speech(tts_text)
            
            with open(voice_file, 'rb') as f:
                await application.bot.send_voice(
                    chat_id=TELEGRAM_USER_ID,
                    voice=f,
                    caption="🎙️ *Lora Podcast: Morning Briefing*" if ai_brief else None,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            
            os.remove(voice_file)
        except Exception as e:
            print(f"Morning TTS error: {e}", flush=True)

        # 7. Update last_briefing_date
        await profile_queries.update_user_profile(pool, TELEGRAM_USER_ID, last_briefing_date=today)
        print(f"Morning briefing sent and logged for {today}.")

    except Exception as e:
        print(f"CRITICAL error in send_morning_briefing: {e}", flush=True)
        import traceback
        traceback.print_exc()

async def send_eod_reflection(application, pool):
    """Checks in with the user at the end of the day."""
    profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
    today = datetime.now(pytz.timezone(TIMEZONE)).date()
    
    if profile.get('last_eod_date') == today:
        return

    # 1. Gather achievements
    from db.queries.tasks import get_completed_tasks_today
    from db.queries.habits import get_habits_completed_today
    
    v_tasks = await get_completed_tasks_today(pool)
    v_habits = await get_habits_completed_today(pool)

    # 2. Format data for Gemini
    data_summary = f"""
USER: {profile.get('name', 'User')}
TONE: {profile.get('tone', 'warm')}
DATE: {today.strftime('%A, %Y-%m-%d')}

ACHIEVEMENTS TODAY:
- Completed Tasks: {len(v_tasks)}
{chr(10).join([f"  • {t}" for t in v_tasks]) if v_tasks else "  • No tasks completed today"}

- Habits Logged: {len(v_habits)}
{chr(10).join([f"  • {h}" for h in v_habits]) if v_habits else "  • No habits logged today"}
"""

    # 3. Call Gemini for synthesis
    from core.gemini import get_proactive_response
    system_instruction = f"""
You are Lora, a warm personal assistant. You are checking in with {profile.get('name', 'User')} for an EOD reflection.
Style: {profile.get('tone', 'warm')}. 
Linguistic Style: Natural "Romglish" (Romanian mixed with modern English terms like "achievements", "recap", "vibes", "tomorrow", "off").

GOAL: Synthesize today's achievements into a warm, celebratory, or reflective summary.
- Be encouraging. 
- Ask how the day felt overall.
- Suggest a way to wind down.
Always use Telegram MarkdownV2 (bold *text*, code `text`).
"""
    from bot.formatter import safe_markdown
    ai_reflection = await get_proactive_response(system_instruction, data_summary)
    if ai_reflection:
        ai_reflection = safe_markdown(ai_reflection)

    # Fallback
    if not ai_reflection:
        ai_reflection = f"Hey {escape_md(profile.get('name', 'User'))}, end of day 🌙\n\nHow did today go?"

    from bot.keyboards import mood_keyboard
    print(f"DEBUG ai_reflection: {ai_reflection}", flush=True)
    await application.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text=ai_reflection,
        reply_markup=mood_keyboard(),
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    # Generate and send voice reflection
    try:
        from bot.tts import text_to_speech
        import os
        
        # Clean markdown for TTS
        tts_text = ai_reflection.replace("*", "").replace("`", "").replace("\\.", ".").replace("\\!", "!").replace("\\-", "-")
        
        voice_file = await text_to_speech(tts_text)
        
        with open(voice_file, 'rb') as f:
            await application.bot.send_voice(
                chat_id=TELEGRAM_USER_ID,
                voice=f,
                caption="🎙️ *Lora Podcast: EOD Reflection*",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        
        os.remove(voice_file)
    except Exception as e:
        print(f"EOD TTS error: {e}", flush=True)
    
    await profile_queries.update_user_profile(pool, TELEGRAM_USER_ID, last_eod_date=today)

async def send_habit_reminder(application, pool):
    """Sends a friendly nudge about pending habits."""
    profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
    today = datetime.now(pytz.timezone(TIMEZONE)).date()
    
    # 1. Find pending habits
    habits = await habit_queries.list_habits(pool)
    done_ids = await habit_queries.get_today_logs(pool)
    pending = [h for h in habits if h['id'] not in done_ids]
    
    if not pending:
        return

    # 2. Format data for Gemini
    data_summary = f"""
USER: {profile.get('name', 'User')}
TONE: {profile.get('tone', 'warm')}
PENDING HABITS:
{chr(10).join([f"  • {h['name']}" for h in pending])}
"""

    # 3. Call Gemini for nudge
    from core.gemini import get_proactive_response
    system_instruction = f"""
You are Lora, a warm personal assistant. You are giving {profile.get('name', 'User')} a gentle nudge about their pending habits in Romanian.
Style: {profile.get('tone', 'warm')}.
Synthesize the list of pending habits into a warm, encouraging whisper. 
Remind them why they are doing this (for their future self).
Always use Telegram MarkdownV2 (bold *text*, code `text`).
"""
    ai_nudge = await get_proactive_response(system_instruction, data_summary)
    
    if not ai_nudge:
        ai_nudge = f"Hei {escape_md(profile.get('name', 'User'))}, nu uita de habit-urile tale de azi! ✨"

    await application.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text=ai_nudge,
        parse_mode=ParseMode.MARKDOWN_V2
    )

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
    from core.config import MORNING_BRIEFING_TIME, EOD_REFLECTION_TIME, HABIT_REMINDER_TIME
    m_h, m_m = map(int, MORNING_BRIEFING_TIME.split(':'))
    e_h, e_m = map(int, EOD_REFLECTION_TIME.split(':'))
    h_h, h_m = map(int, HABIT_REMINDER_TIME.split(':'))

    # Added misfire_grace_time=3600 (1 hour) so if bot restarts late, it still sends
    scheduler.add_job(send_morning_briefing, 'cron', hour=m_h, minute=m_m, 
                      misfire_grace_time=3600, args=[application, pool])
    
    scheduler.add_job(send_habit_reminder, 'cron', hour=h_h, minute=h_m, 
                      misfire_grace_time=3600, args=[application, pool])
    
    scheduler.add_job(send_eod_reflection, 'cron', hour=e_h, minute=e_m, 
                      misfire_grace_time=3600, args=[application, pool])
    
    scheduler.add_job(missed_habit_nudge, 'cron', hour=(m_h + 1) % 24, minute=m_m, 
                      misfire_grace_time=3600, args=[application, pool])
    
    scheduler.add_job(check_event_reminders, 'interval', minutes=15, args=[application, pool])
    
    scheduler.start()
    print("Scheduler started with misfire grace periods.")
    return scheduler

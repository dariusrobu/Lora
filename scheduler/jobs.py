from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pytz
from core.config import TELEGRAM_USER_ID, TIMEZONE
from bot.formatter import escape_md
from telegram.constants import ParseMode
import db.queries.profile as profile_queries
import db.queries.tasks as task_queries
import db.queries.habits as habit_queries
import db.queries.events as event_queries
import db.queries.finance as finance_queries
import db.queries.notes as note_queries
import db.queries.health as health_queries

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
        import asyncio
        import os
        from core.gemini import get_proactive_response
        from bot.formatter import safe_markdown, split_message

        (
            all_tasks,
            events,
            habits,
            today_logged_ids,
            weather_info,
            shopping_items,
        ) = await asyncio.gather(
            task_queries.list_tasks(pool),
            event_queries.list_events(pool, today, today),
            habit_queries.list_habits(pool),
            habit_queries.get_today_logs(pool),
            get_weather_summary(),
            list_shopping_items(pool),
        )

        weather_info = weather_info or "Vremea nu este disponibilă acum."
        overdue: list = [t for t in all_tasks if t['due_date'] and t['due_date'] < today]
        due_today: list = [t for t in all_tasks if t['due_date'] == today]
        priority_tasks: list = (overdue + due_today)[:5]
        pending_habits: list = [h for h in habits if h['id'] not in today_logged_ids]

        
        # 3. Build shared context strings for Gemini calls
        name: str = profile.get('name', 'User')
        tone: str = profile.get('tone', 'warm')

        task_text = "\n".join(
            f"{'OVERDUE: ' if t in overdue else ''}{t['title']}"
            + (f" (prioritate: {t['priority']})" if t.get('priority') else "")
            + (f" [{t['project_name']}]" if t.get('project_name') else "")
            for t in priority_tasks
        ) or "Niciun task prioritar."

        event_text = "\n".join(
            f"{e['title']} la {e['event_time'].strftime('%H:%M') if e['event_time'] else 'toată ziua'}"
            for e in events
        ) or "Niciun eveniment."

        habit_text = "\n".join(h['name'] for h in pending_habits) or "Toate bifate."

        gemini_context = f"""USER: {name}
DATE: {today.strftime('%A, %d %B %Y')}
ORA: {now.strftime('%H:%M')}
TONE: {tone}

TASKS PRIORITARE:
{task_text}

EVENIMENTE AZI:
{event_text}

HABITS PENDING:
{habit_text}
"""

        # 4. Two parallel Gemini calls — itinerary + focus
        itinerary_instruction = f"""Ești Lora, asistenta lui {name}.
Generezi secțiunea 'Planul zilei' pentru morning briefing-ul de Telegram.
Creează un itinerar realist pe ore combinând tasks + events + habits.
- Sugerează ore aproximative, ex: '9:00 — focus pe X', '11:00 — meeting Y'
- Dacă sunt puține date, sugerează blocuri de focus time generice
- Maxim 5-6 rânduri, fiecare pe linie separată
- Fiecare rând: `HH:MM` — descriere (Telegram MarkdownV2, caractere RAW)
- Ton: {'concis și la obiect' if tone == 'direct' else 'cald și practic'}, Romglish
- FĂRĂ introduceri, FĂRĂ 'Iată planul:', începe direct cu primul rând de oră"""

        focus_instruction = f"""Ești Lora, asistenta lui {name}.
Pe baza tasks-urilor și evenimentelor de azi, identifică UN SINGUR lucru cel mai important.
- O SINGURĂ propoziție scurtă (max 15 cuvinte)
- Ton: {'direct, fără ornamente' if tone == 'direct' else 'motivant și cald'}, Romglish
- FĂRĂ introduceri, FĂRĂ ghilimele, scrie direct propoziția"""

        itinerary_raw, focus_raw = await asyncio.gather(
            get_proactive_response(itinerary_instruction, gemini_context),
            get_proactive_response(focus_instruction, gemini_context),
        )

        # 5. Build deterministic 6-section Telegram message
        day_ro: dict[str, str] = {
            "Monday": "Luni", "Tuesday": "Marți", "Wednesday": "Miercuri",
            "Thursday": "Joi", "Friday": "Vineri", "Saturday": "Sâmbătă", "Sunday": "Duminică",
        }
        day_name = day_ro.get(today.strftime("%A"), today.strftime("%A"))
        date_str = escape_md(f"{day_name}, {today.strftime('%d %B %Y')}")

        lines: list[str] = [
            "━━━━━━━━━━━━━━━",
            f"☀️ *Bună dimineața, {escape_md(name)}\\!*",
            f"_{date_str}_",
            "━━━━━━━━━━━━━━━",
            "",
            f"🌤 *Vremea* — {escape_md(weather_info)}",
            "",
            "📋 *Tasks de azi*",
        ]
        if priority_tasks:
            for t in priority_tasks:
                prefix = "⚠️ " if t in overdue else "• "
                proj = f" _\\[{escape_md(t['project_name'])}\\]_" if t.get('project_name') else ""
                prio = " 🔥" if t.get('priority') == 'high' else ""
                lines.append(f"{prefix}{escape_md(t['title'])}{prio}{proj}")
        else:
            lines.append("Niciun task pending azi 🎉")

        lines += ["", "📅 *Evenimente*"]
        if events:
            for e in events:
                time_str = e['event_time'].strftime('%H:%M') if e['event_time'] else "toată ziua"
                lines.append(f"• `{time_str}` — {escape_md(e['title'])}")
        else:
            lines.append("Nimic în calendar azi\\.")

        lines += ["", "🔁 *Habits pending*"]
        if pending_habits:
            for h in pending_habits:
                streak = f" \\(streak: {h['streak_count']} 🔥\\)" if h.get('streak_count', 0) > 0 else ""
                lines.append(f"• {escape_md(h['name'])}{streak}")
        else:
            lines.append("Toate habit\\-urile bifate ✅")

        lines += ["", "🗺 *Planul zilei*"]
        if itinerary_raw and itinerary_raw.strip():
            lines.append(safe_markdown(itinerary_raw.strip()))
        else:
            lines.append("Organizează\\-ți ziua după energie și prioritate\\.")

        lines += ["", "💡 *Focus*"]
        if focus_raw and focus_raw.strip():
            lines.append(safe_markdown(focus_raw.strip()))
        elif priority_tasks:
            lines.append(escape_md(priority_tasks[0]['title']))
        else:
            lines.append("O zi la un moment dat\\.")

        briefing_text = "\n".join(lines)

        # 5b. Send Telegram text message
        chunks = split_message(briefing_text)
        for chunk in chunks:
            try:
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=chunk,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            except Exception as e:
                print(f"Morning brief MarkdownV2 failed, falling back to plain: {e}", flush=True)
                await application.bot.send_message(chat_id=TELEGRAM_USER_ID, text=chunk)

        # 6. Generate and send "podcast" (voice) in background-like manner
        try:
            from bot.tts import text_to_speech
            import os

            print("🎙️ Starting TTS generation for Morning Briefing...", flush=True)
            podcast_data = f"""USER: {name}
TONE: {tone}
DATE: {today.strftime('%A, %d %B %Y')}
WEATHER: {weather_info}

TOP 3 TASKS:
{task_text}

EVENIMENTE AZI:
{event_text}

HABITS PENDING AZI:
{habit_text}
"""
            podcast_instruction = f"""Ești Lora, asistenta personală a lui {name}.
 Generezi un podcast vocal de dimineață. Scrie să sune natural când e citit cu voce.
 Generează textul podcastului EXCLUSIV în limba română (MAXIM 250 cuvinte).
 Sunt permise DOAR aceste cuvinte în engleză: task, habit, meeting, gym, chess.
 INTERZIS COMPLET: the game plan, all clear, catch up, deep work, worry, talk of the town, fun, highlights, insights și orice altă expresie idiomatică în engleză.
 Structură: salut + oră → vreme → top tasks ca plan, nu liste → evenimente + habits → gând scurt motivațional.
 Ton: cald și direct. EVITĂ superlativele și entuziasmul exagerat (ex: super, fascinant, minunat, amazing, extraordinar, wow). Nu repeta 'zâmbete', 'energie', 'bucurie'.
 Vorbește ca un asistent de încredere, nu ca un hype-man. Fără bullet points, fără titluri de secțiuni.
 Formatare: Telegram MarkdownV2 raw (fără backslash escape în JSON)."""
            raw_brief = await get_proactive_response(podcast_instruction, podcast_data)
            tts_text: str = raw_brief or briefing_text
            print(f"🎙️ TTS input length: {len(tts_text)} characters", flush=True)
            voice_file = await text_to_speech(tts_text, podcast_mode=True)
            print(f"🎙️ TTS file generated: {voice_file} (size: {os.path.getsize(voice_file)} bytes)", flush=True)

            with open(voice_file, 'rb') as f:
                await application.bot.send_voice(
                    chat_id=TELEGRAM_USER_ID,
                    voice=f,
                    caption="🎙️ *Lora Podcast: Morning Briefing*",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
                print("🎙️ Voice message sent successfully!", flush=True)

            if os.path.exists(voice_file):
                os.remove(voice_file)

        except Exception as e:
            import traceback
            print(f"❌ Podcast generation error: {e}", flush=True)
            traceback.print_exc()
            try:
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=f"❌ *Podcast error:* `{escape_md(str(e))}`",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            except Exception:
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=f"❌ Podcast error: {str(e)}",
                )

        # ── 7. Mark as sent (after all sends succeed) ──────────────────────
        await profile_queries.update_user_profile(pool, TELEGRAM_USER_ID, last_briefing_date=today)
        print(f"Morning briefing sent and logged for {today}.", flush=True)

        # ── 8. Interactive Day Plan Flow ──────────────────────────────────
        from core.state import set_state
        await application.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text="Cum vrei să-ți arate ziua azi? Spune-mi vocal sau în scris 🗓"
        )
        await set_state(pool, "awaiting_day_plan_input", "day_plans", "generate", None)
        print("Awaiting day plan input state set.", flush=True)

    except Exception as e:
        import traceback
        print(f"CRITICAL error in send_morning_briefing: {e}", flush=True)
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
DATE: {today.strftime('%A, %Y-%m-%d')}

TASK-URI COMPLETATE AZI: {len(v_tasks)}
{chr(10).join([f"  • {t['title']}{' [' + t['project_name'] + ']' if t.get('project_name') else ''}" for t in v_tasks]) if v_tasks else "  • Niciun task completat"}

HABITS BIFATE AZI: {len(v_habits)}
{chr(10).join([f"  • {h}" for h in v_habits]) if v_habits else "  • Niciun habit bifat"}
"""

    # 3. Call Gemini for synthesis
    from core.gemini import get_proactive_response
    system_instruction = f"""
Ești Lora, asistenta personală a lui {profile.get('name', 'User')}. Trimiți mesajul EOD de seară.

LIMBĂ: Mesajul se scrie EXCLUSIV în română.
Sunt permise DOAR: task, habit, meeting, gym, chess.
INTERZIS: vibes, achievements, wins, chill, off, have a great evening, bravo, recap.
Folosește echivalente românești (ex: "bine făcut" în loc de "bravo").

TON: Calm, sincer, reflectiv.
NU folosi: "super", "solide", "major", "wow", "meriti din plin", "extraordinar", "fascinant".
Maxim 2 emoji per mesaj. INTERZIS: 💖 sau orice emoji romantic.
NU adăuga sugestii nesolicitate despre ce să facă userul seara (plimbare, serial, muzică) dacă nu au fost menționate.

STRUCTURĂ (maxim 100 de cuvinte):
1. Ce ai făcut azi (2-3 propoziții, bazat pe task-uri completate + habits bifate)
2. O singură întrebare de reflecție (scurtă, directă)
3. Urare de seară (1 propoziție, max 1 emoji)

Formatare: Telegram MarkdownV2 raw.
"""
    from bot.formatter import safe_markdown
    raw_ai_reflection: str = await get_proactive_response(system_instruction, data_summary)
    ai_reflection: str = ""
    if raw_ai_reflection:
        ai_reflection = safe_markdown(raw_ai_reflection)

    # Fallback
    if not ai_reflection:
        raw_ai_reflection = ""
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

        print("🎙️ Starting TTS generation for EOD Reflection...", flush=True)
        # Pass raw text — prepare_podcast_text() inside tts.py does full cleanup
        tts_text: str = raw_ai_reflection or ai_reflection
        print(f"🎙️ TTS input length: {len(tts_text)} characters", flush=True)
        voice_file = await text_to_speech(tts_text, podcast_mode=True)
        print(f"🎙️ TTS file generated: {voice_file} (size: {os.path.getsize(voice_file) if os.path.exists(voice_file) else 'NOT FOUND'} bytes)", flush=True)

        with open(voice_file, 'rb') as f:
            print(f"🎙️ Sending voice to Telegram (chat_id: {TELEGRAM_USER_ID})...", flush=True)
            await application.bot.send_voice(
                chat_id=TELEGRAM_USER_ID,
                voice=f,
                caption="🎙️ *Lora Podcast: EOD Reflection*",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            print("🎙️ Voice message sent successfully!", flush=True)

        os.remove(voice_file)
        print(f"🎙️ Temporary voice file removed: {voice_file}", flush=True)
    except Exception as e:
        error_msg = f"❌ *EOD TTS error:* `{escape_md(str(e))}`"
        print(f"❌ {error_msg}", flush=True)
        import traceback
        traceback.print_exc()
        try:
            await application.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=error_msg,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except:
            await application.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=f"❌ EOD TTS error: {str(e)}"
            )
    
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

async def send_journal_night(application, pool) -> None:
    """Sends the evening journal prompt and sets state to await user's reflection."""
    try:
        user_tz = pytz.timezone(TIMEZONE)
        today = datetime.now(user_tz).date()

        # 1. Idempotency check
        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if profile.get('last_journal_date') == today:
            print(f"Journal night already prompted for {today} — skipping.", flush=True)
            return

        name: str = profile.get('name', 'User')
        print(f"Starting journal night prompt for {today}...", flush=True)

        # 2. Build deterministic prompt message
        prompt_text = (
            f"━━━━━━━━━━━━━━━\n"
            f"🌙 *Reflecție de seară, {escape_md(name)}*\n"
            f"━━━━━━━━━━━━━━━\n\n"
            "Ia 2 minute pentru tine\\. Trei întrebări scurte:\n\n"
            "*1\\.* Ce a mers bine azi?\n"
            "*2\\.* Ce ai vrea să faci diferit?\n"
            "*3\\.* Care e un lucru important pentru mâine?\n\n"
            "_Răspunde liber, cu câte cuvinte vrei \u2014 eu mă ocup de rest\\_"
        )

        # Health reminder check
        health_today = await health_queries.get_health_log(pool, today)
        if not health_today:
            prompt_text += "\n\nLoghează și somnul când te culci\\."

        # 3. Send text message
        try:
            await application.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=prompt_text,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as e:
            print(f"Journal night MarkdownV2 failed, falling back: {e}", flush=True)
            plain = (
                f"🌙 Reflecție de seară, {name}\n\n"
                f"1. Ce a mers bine azi?\n"
                f"2. Ce ai vrea să faci diferit?\n"
                f"3. Care e un lucru important pentru mâine?\n\n"
                f"Răspunde liber."
            )
            await application.bot.send_message(chat_id=TELEGRAM_USER_ID, text=plain)

        # 4. Send voice version
        try:
            from bot.tts import text_to_speech
            import os
            tts_raw = (
                f"Bună seara, {name}. Hai să ne gândim puțin la ziua de azi. "
                f"Înti ce a mers bine, ce ai schimba, şi care e un lucru important pentru mâine. "
                "Răspunde liber, eu mă ocup de rest."
            )
            voice_file = await text_to_speech(tts_raw, podcast_mode=True)
            with open(voice_file, 'rb') as f:
                await application.bot.send_voice(
                    chat_id=TELEGRAM_USER_ID,
                    voice=f,
                    caption="🎙️ *Lora: Reflecție de seară*",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            if os.path.exists(voice_file):
                os.remove(voice_file)
        except Exception as e:
            print(f"Journal night TTS failed (non-critical): {e}", flush=True)

        # 5. Set state + mark as prompted (idempotency for tomorrow's job)
        from core.state import set_state
        await set_state(pool, 'awaiting_journal_response', 'journal', 'save', None)
        await profile_queries.update_user_profile(pool, TELEGRAM_USER_ID, last_journal_date=today)
        print(f"Journal night prompt sent. Awaiting response for {today}.", flush=True)

    except Exception as e:
        import traceback
        print(f"CRITICAL error in send_journal_night: {e}", flush=True)
        traceback.print_exc()


async def send_weekly_review(application, pool) -> None:
    """Aggregates weekly data and sends a reflective review on Sunday evening."""
    from datetime import timedelta, datetime
    import pytz
    from core.config import TIMEZONE, TELEGRAM_USER_ID
    from bot.formatter import safe_markdown
    from telegram.constants import ParseMode
    
    try:
        user_tz = pytz.timezone(TIMEZONE)
        today = datetime.now(user_tz).date()
        
        # 1. Idempotency Check
        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if profile.get('last_weekly_review_date') == today:
            print(f"Weekly review already sent for {today} — skipping.", flush=True)
            return

        print(f"Starting weekly review for {today}...", flush=True)

        # 2. Date Range (Monday to Sunday)
        start_date = today - timedelta(days=6)
        end_date = today

        # 3. Aggregated Data Collection
        task_stats = await task_queries.get_weekly_task_stats(pool, start_date, end_date)
        habit_stats = await habit_queries.get_weekly_habit_stats(pool, start_date, end_date)
        events = await event_queries.list_events(pool, start_date, end_date)
        
        # Concise Finance Section for Sunday Review
        finance_summary = await finance_queries.get_weekly_finance_summary(pool, start_date, end_date)
        finance_ctx = f"Cheltuieli totale săptămâna asta: {int(finance_summary['total'])} RON"
        finance_footer = "" # Not needed here

        # Enhanced Mood Section
        import db.queries.mood as mood_queries
        weekly_moods = await mood_queries.get_weekly_mood_summary(pool, start_date, end_date)
        mood_total = sum(weekly_moods.values())
        mood_summary = ""
        if mood_total > 0:
            mood_labels = {
                "great": "super", "good": "bine", "neutral": "ok", 
                "okay": "ok", "bad": "slab", "terrible": "rău", "awful": "rău"
            }
            # Combine duplicates (neutral/okay, terrible/awful)
            combined_moods = {}
            for m, count in weekly_moods.items():
                label = mood_labels.get(m.lower(), "ok")
                combined_moods[label] = combined_moods.get(label, 0) + count
            
            mood_parts = [f"{count} zile {label}" for label, count in combined_moods.items()]
            mood_summary = f"😊 Mood săptămâna asta: {', '.join(mood_parts)}"

        # 3.5 Automated Insights Patterns
        from modules.insights import generate_insights
        patterns = await generate_insights(pool)
        # Omit if not enough data
        patterns_section = ""
        if "nu am suficiente date" not in patterns.lower():
            patterns_section = f"\n🧠 *Patterns observate*\n{patterns}\n"

        journals = await note_queries.get_weekly_journals(pool, start_date, end_date)

        # 3.7 Health & Mood Correlations Data
        health_week = await health_queries.get_health_history(pool, 7)
        mood_week = await note_queries.get_weekly_mood_data(pool, start_date, end_date)
        tasks_per_day = await task_queries.get_completed_tasks_per_day(pool, start_date, end_date)
        
        # Restore Formatting for Context
        habit_ctx = []
        for h in habit_stats[:5]:
            habit_ctx.append(f"{h['name']}: {h['completion_days']}/7 zile, streak {h['streak_count']}")
        
        event_ctx = [e['title'] for e in events]
        
        health_ctx = ""
        if health_week:
            health_lines = []
            for h in health_week:
                health_lines.append(f"{h['log_date']}: Sleep {h['sleep_hours']}h, Water {h['water_ml']}ml, Nutrition {h['nutrition']}")
            health_ctx = "\n".join(health_lines)
            
        mood_map = {"great": 5, "good": 4, "neutral": 3, "bad": 2, "terrible": 1}
        mood_ctx = "\n".join([f"{m['date']}: {mood_map.get(m['mood'].lower(), 3)}" for m in mood_week])
        tasks_ctx = "\n".join([f"{t['date']}: {t['count']} tasks" for t in tasks_per_day])

        # Format journals for context
        journal_moods = [j['mood'] for j in journals if j.get('mood')]
        
        data_summary = f"""
SĂPTĂMÂNA: {start_date} — {end_date}
TASKS: {task_stats['completed']} completate din {task_stats['added']} adăugate săptămâna asta.
HABITS: {", ".join(habit_ctx)}
FINANCE BREAKDOWN:
{finance_ctx}
MOOD SUMMARY: {mood_summary}
PATTERNS: {patterns_section}
EVENTS: {", ".join(event_ctx)}
JOURNALS (MOODS): {", ".join(journal_moods)}

--- HEALTH CORRELATION DATA ---
Date health săptămână:
{health_ctx}
Date mood săptămână:
{mood_ctx}
Tasks completate pe zi:
{tasks_ctx}
"""

        # 4. Gemini Review Generation
        from core.gemini import get_proactive_response
        system_instruction = f"""
Ești Lora, asistenta personală a lui {profile.get('name', 'User')}. 
Generează un weekly review structurat în română.
Tone: reflectiv, direct, calm, fără hype. 
Interzis: bravos, vibes, wins, achievements.

Structură FIXĂ (MarkdownV2):
📊 *Săptămâna {start_date.strftime('%d.%m')} — {end_date.strftime('%d.%m')}*

✅ *Tasks*: {task_stats['completed']} completate din {task_stats['added']}
🔁 *Habits*: [top 3 habits relevanți cu streak]

💰 *Finanțe*
{finance_ctx}

{mood_summary}
{patterns_section}

📈 *Highlight*: [cel mai important lucru realizat — ales de tine din date]

🔍 *Pattern observat*: [Dacă există corelații health semnificative conform instrucțiunilor de mai jos]

INSTRUCȚIUNI PATTERN:
Verifică corelații și adaugă secțiunea "🔍 *Pattern observat*" DOAR dacă:
- somn mediu < 6.5h → menționează impactul pe tasks completate
- zile cu apă < 1.5L → corelează cu mood dacă pattern clar
- nutriție "bad"/"terrible" în 3+ zile → menționează
- corelație somn-productivitate semnificativă (diferență > 30% tasks în zile bune vs proaste)

Dacă nu există pattern semnificativ sau date health: OMITĂ complet secțiunea.
MAX 2 propoziții, ton factual, fără laudă.

Maxim 200 cuvinte.
DOAR textul review-ului, fără introducere/concluzie extra.
"""
        review_text = await get_proactive_response(system_instruction, data_summary)
        
        if not review_text:
            review_text = f"📊 *Săptămâna {start_date} — {end_date}*\n\nReview-ul tău nu a putut fi generat, dar ai completat {task_stats['completed']} task-uri! 🚀"

        # 5. Send Text Message
        await application.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=safe_markdown(review_text),
            parse_mode=ParseMode.MARKDOWN_V2
        )

        # 6. Send Voice Version (TTS)
        try:
            from bot.tts import text_to_speech
            import os
            # Clean text for TTS
            tts_clean = review_text.replace('*', '').replace('📊', '').replace('✅', '').replace('🔁', '').replace('💰', '').replace('📈', '').replace('🔍', '').strip()
            voice_file = await text_to_speech(tts_clean, podcast_mode=True)
            with open(voice_file, 'rb') as f:
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
        await profile_queries.update_user_profile(pool, TELEGRAM_USER_ID, last_weekly_review_date=today)
        print(f"Weekly review sent and logged for {today}.", flush=True)

    except Exception as e:
        import traceback
        print(f"CRITICAL error in send_weekly_review: {e}", flush=True)
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
        if profile.get('last_finance_summary_date') == today:
            print(f"Finance summary already sent for {today} — skipping.", flush=True)
            return

        print(f"Starting weekly finance summary for {today}...", flush=True)

        # 2. Date Range (Previous Monday to Sunday)
        start_date = today - timedelta(days=7)
        end_date = today - timedelta(days=1)

        # 3. Aggregated Data Collection
        finance_summary = await finance_queries.get_weekly_finance_summary(pool, start_date, end_date)
        
        async with pool.acquire() as conn:
            weekly_breakdown = await conn.fetch(
                """
                SELECT category, SUM(amount) as total 
                FROM finances 
                WHERE type = 'expense' AND tx_date BETWEEN $1 AND $2 
                GROUP BY category 
                ORDER BY total DESC
                """,
                start_date, end_date
            )
        
        # Calculate monthly budget remaining
        now = datetime.now(user_tz)
        monthly_stats = await finance_queries.get_monthly_summary(pool, now.month, now.year)
        async with pool.acquire() as conn:
            total_limit = await conn.fetchval("SELECT SUM(monthly_limit) FROM budget_limits")
        
        budget_remaining = (float(total_limit) - float(monthly_stats['expense'])) if total_limit else 0
        
        finance_lines = []
        for b in weekly_breakdown[:5]:
            finance_lines.append(f"• {escape_md(b['category'])}: `{int(b['total'])} RON`")
        
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
            chat_id=TELEGRAM_USER_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN_V2
        )

        # 6. Update Idempotency
        await profile_queries.update_user_profile(pool, TELEGRAM_USER_ID, last_finance_summary_date=today)
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
    """Checks for upcoming events and sends reminders."""
    # Simplified logic for now: query all events and check time diffs
    # This will be refined in Phase 8
    pass

def setup_scheduler(application, pool):
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    from core.config import MORNING_BRIEFING_TIME, EOD_REFLECTION_TIME, HABIT_REMINDER_TIME, JOURNAL_NIGHT_TIME
    m_h, m_m = map(int, MORNING_BRIEFING_TIME.split(':'))
    e_h, e_m = map(int, EOD_REFLECTION_TIME.split(':'))
    h_h, h_m = map(int, HABIT_REMINDER_TIME.split(':'))
    j_h, j_m = map(int, JOURNAL_NIGHT_TIME.split(':'))

    # Added misfire_grace_time=3600 (1 hour) so if bot restarts late, it still sends
    scheduler.add_job(send_morning_briefing, 'cron', hour=m_h, minute=m_m,
                      misfire_grace_time=3600, args=[application, pool])

    scheduler.add_job(send_habit_reminder, 'cron', hour=h_h, minute=h_m,
                      misfire_grace_time=3600, args=[application, pool])

    scheduler.add_job(send_eod_reflection, 'cron', hour=e_h, minute=e_m,
                      misfire_grace_time=3600, args=[application, pool])

    scheduler.add_job(send_journal_night, 'cron', hour=j_h, minute=j_m,
                      misfire_grace_time=3600, args=[application, pool])

    scheduler.add_job(send_weekly_review, 'cron', day_of_week='sun', hour=e_h, minute=e_m,
                      misfire_grace_time=3600, args=[application, pool])

    # Weekly Finance Summary: Monday, 5 mins before Morning Briefing
    f_h, f_m = m_h, (m_m - 5) % 60
    if m_m < 5: f_h = (m_h - 1) % 24
    
    scheduler.add_job(send_weekly_finance_summary, 'cron', day_of_week='mon', hour=f_h, minute=f_m,
                      misfire_grace_time=3600, args=[application, pool])

    scheduler.add_job(reset_budget_alerts, 'cron', day=1, hour=0, minute=0,
                      misfire_grace_time=3600, args=[application, pool])

    scheduler.add_job(missed_habit_nudge, 'cron', hour=(m_h + 1) % 24, minute=m_m,
                      misfire_grace_time=3600, args=[application, pool])

    scheduler.add_job(check_event_reminders, 'interval', minutes=15, args=[application, pool])

    scheduler.start()
    print("Scheduler started with misfire grace periods.")
    return scheduler

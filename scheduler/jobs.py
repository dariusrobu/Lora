from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz
from core.config import (
    TELEGRAM_USER_ID,
    TIMEZONE,
    MORNING_BRIEFING_TIME,
    EOD_REFLECTION_TIME,
    HABIT_REMINDER_TIME,
    JOURNAL_NIGHT_TIME,
)
from bot.formatter import escape_md, safe_markdown
from telegram.constants import ParseMode
import db.queries.profile as profile_queries
import db.queries.tasks as task_queries
import db.queries.skills as skill_queries
import db.queries.events as event_queries
import db.queries.finance as finance_queries
import db.queries.notes as note_queries
import db.queries.health as health_queries
import db.queries.journal as journal_queries

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


async def send_morning_briefing(application, pool):
    """Sends a daily summary of tasks, events, skills, and health."""
    try:
        user_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(user_tz)
        today = now.date()

        # 1. Idempotency check
        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if profile.get("last_briefing_date") == today:
            return

        print(f"Starting morning briefing for {today}...", flush=True)

        # 2. Gather data in PARALLEL
        from modules.weather import get_weather_summary
        from db.queries.shopping import list_shopping_items
        from db.queries import workout as workout_queries
        import asyncio
        import os
        from core.gemini import get_proactive_response
        from bot.formatter import safe_markdown, split_message

        (
            all_tasks,
            events,
            reminders,
            skills,
            weather_info,
            shopping_items,
            health_log,
            workouts_yesterday,
        ) = await asyncio.gather(
            task_queries.list_tasks(pool),
            event_queries.list_events(pool, today, today),
            event_queries.list_reminders(pool),
            skill_queries.get_all_skills(pool),
            get_weather_summary(),
            list_shopping_items(pool),
            health_queries.get_health_log(pool, today),
            workout_queries.get_recent_workouts(pool, days=1),
        )

        weather_info = weather_info or "Vremea nu este disponibilă acum."
        overdue: list = [
            t for t in all_tasks if t["due_date"] and t["due_date"] < today
        ]
        due_today: list = [t for t in all_tasks if t["due_date"] == today]
        priority_tasks: list = (overdue + due_today)[:5]
        pending_skills = [s for s in skills if s.get("last_log_date") != today]

        # 3. Build shared context strings for Gemini calls
        name: str = profile.get("name", "User")
        tone: str = profile.get("tone", "warm")

        # If priority_tasks is empty, use all pending tasks
        if priority_tasks:
            tasks_to_show = priority_tasks
        else:
            tasks_to_show = all_tasks

        # If more than 5 tasks, show summary by project
        if len(tasks_to_show) > 5:
            from collections import Counter

            project_counts = Counter(
                t.get("project_name") or "Fără proiect" for t in tasks_to_show
            )
            task_text = " • ".join(
                f"{proj}: {count} task-uri" for proj, count in project_counts.items()
            )
        else:
            task_text = (
                "\n".join(
                    f"{'OVERDUE: ' if t in overdue else ''}{t['title']}"
                    + (f" (prioritate: {t['priority']})" if t.get("priority") else "")
                    + (f" [{t['project_name']}]" if t.get("project_name") else "")
                    for t in tasks_to_show
                )
                or "Niciun task."
            )

        event_text = (
            "\n".join(
                f"{e['title']} la {e['event_time'].strftime('%H:%M') if e['event_time'] else 'toată ziua'}"
                for e in events
            )
            or "Niciun eveniment."
        )

        reminder_text = (
            "\n".join(
                f"{r['title']} ({r['event_date'].strftime('%d %b')})"
                for r in reminders[:5]
            )
            or "Niciun reminder."
        )

        skill_text = "\n".join(s["name"] for s in pending_skills) or "Totul e la zi."

        gemini_context = f"""USER: {name}
DATE: {today.strftime("%A, %d %B %Y")}
ORA: {now.strftime("%H:%M")}
TONE: {tone}

TASKS PRIORITARE:
{task_text}

EVENIMENTE AZI:
{event_text}

REMINDERE URMĂTOARE:
{reminder_text}

SKILLS PENDING AZI:
{skill_text}
"""

        # 4. Gemini calls — itinerary + focus + automated time block
        itinerary_instruction = f"""Ești Lora, asistenta lui {name}.
Generezi secțiunea 'Planul zilei' pentru morning briefing-ul de Telegram.
Creează un itinerar realist pe ore combinând tasks + events + skills.

IMPORTANT: Userul îți va menționa ce a făcut deja azi. 
NU include în plan activități menționate ca deja făcute. 
Planul trebuie să înceapă de la momentul curent și să meargă în viitor. 
Dacă userul zice 'am făcut X și Y', începe planul cu următoarea activitate logică conform orei.

- Sugerează ore aproximative, ex: '9:00 — focus pe X', '11:00 — meeting Y'
- Dacă sunt puține date, sugerează blocuri de focus time generice
- Maxim 5-6 rânduri, fiecare pe linie separată
- Fiecare rând: `HH:MM` — descriere (Telegram MarkdownV2, caractere RAW)
- Ton: {"concis și la obiect" if tone == "direct" else "cald și practic"}, Romglish
- FĂRĂ introduceri, FĂRĂ 'Iată planul:', începe direct cu primul rând de oră"""

        focus_instruction = f"""Ești Lora, asistenta lui {name}.
Pe baza tasks-urilor și evenimentelor de azi, identifică UN SINGUR lucru cel mai important.
- O SINGURĂ propoziție scurtă (max 15 cuvinte)
- Ton: {"direct, fără ornamente" if tone == "direct" else "motivant și cald"}, Romglish
- FĂRĂ introduceri, FĂRĂ ghilimele, scrie direct propoziția"""

        from modules.planner import generate_time_block

        results = await asyncio.gather(
            get_proactive_response(itinerary_instruction, gemini_context),
            get_proactive_response(focus_instruction, gemini_context),
            generate_time_block(pool),
        )

        itinerary_raw = results[0]
        focus_raw = results[1]
        time_block_text, _ = results[2]

        # Fallback to legacy itinerary if time_block fails
        if "Nu am putut genera" in time_block_text:
            final_itinerary = itinerary_raw
        else:
            # generate_time_block returns valid MarkdownV2 with title, we use it directly
            final_itinerary = time_block_text

        # 5. Build deterministic 6-section Telegram message
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

        lines: list[str] = [
            "━━━━━━━━━━━━━━━",
            f"☀️ *Bună dimineața, {escape_md(name)}!*",
            f"_{date_str}_",
            "━━━━━━━━━━━━━━━",
            "",
            f"🌤 *Vremea* — {escape_md(weather_info)}",
        ]

        # 📚 UNIVERSITATE
        from db.queries.schedule import (
            get_today_schedule,
            get_current_week_type,
            get_active_vacation,
        )

        week_type = await get_current_week_type(pool)
        week_label = "impară" if week_type == "odd" else "pară"

        study_year = profile.get("study_year") or "?"
        specialization = profile.get("specialization") or "?"
        university = profile.get("university_name") or "UBB"

        lines += [
            "",
            f"📚 *{escape_md(university)} · Anul {study_year} · {escape_md(specialization)} · Săptămâna {week_label}*",
        ]

        vacation = await get_active_vacation(pool)
        if vacation:
            return_date = (vacation["end_date"] + timedelta(days=1)).strftime("%d %B")
            lines.append(
                f"🌴 *{escape_md(vacation['name'])}* — revii pe {escape_md(return_date)}"
            )

        today_classes = await get_today_schedule(pool)
        if today_classes:
            lines.append(
                f"🎓 *{len(today_classes)} {'curs' if len(today_classes) == 1 else 'cursuri'} azi:*"
            )
            for c in today_classes:
                start = c["start_time"].strftime("%H:%M")
                room = f" · sala {escape_md(c['room'])}" if c.get("room") else ""
                lines.append(f"• `{start}` — {escape_md(c['subject_name'])}{room}")
        else:
            if not vacation:
                lines.append("📭 Nicio activitate didactică azi.")

        # Group tasks by project
        from collections import defaultdict

        project_groups = defaultdict(lambda: {"tasks": [], "has_overdue": False})

        for t in priority_tasks:
            proj = t.get("project_name") or "Fără proiect"
            project_groups[proj]["tasks"].append(t)
            if t in overdue:
                project_groups[proj]["has_overdue"] = True

        if project_groups:
            sorted_projects = sorted(
                project_groups.items(),
                key=lambda x: (
                    -x[1]["has_overdue"],
                    -sum(1 for t in x[1]["tasks"] if t.get("priority") == "high"),
                    x[0],
                ),
            )

            total_tasks = sum(len(g["tasks"]) for g in project_groups.values())
            lines.append(
                f"📋 *Tasks de azi* — {total_tasks} taskuri în {len(project_groups)} proiecte\n"
            )

            for proj_name, data in sorted_projects:
                count = len(data["tasks"])
                overdue_count = sum(1 for t in data["tasks"] if t in overdue)
                has_high = any(t.get("priority") == "high" for t in data["tasks"])

                overdue_str = f" ({overdue_count} overdue)" if overdue_count > 0 else ""
                prio_str = " 🔥" if has_high else ""
                prefix = "⚠️ " if data["has_overdue"] else "📁 "

                lines.append(
                    f"{prefix}{escape_md(proj_name)} ({count}){overdue_str}{prio_str}"
                )
        else:
            lines.append("📋 *Tasks de azi*\nNiciun task pending azi 🎉")

        lines += ["", "📅 *Evenimente*"]
        if events:
            for e in events:
                time_str = (
                    e["event_time"].strftime("%H:%M")
                    if e["event_time"]
                    else "toată ziua"
                )
                lines.append(f"• `{time_str}` — {escape_md(e['title'])}")
        else:
            lines.append("Nimic în calendar azi\\.")

        from db.queries.university import get_upcoming_exams

        exams_soon = await get_upcoming_exams(pool, days=7)
        if exams_soon:
            lines += ["", "🎓 *Examene în 7 zile*"]
            for e in exams_soon:
                date_str = escape_md(e["exam_date"].strftime("%d %b"))
                subject = escape_md(e["subject_name"])
                type_str = escape_md(e["exam_type"])
                lines.append(f"• *{date_str}* — {subject} \\({type_str}\\)")

        lines += ["", "🧠 *Skills de lucrat azi*"]
        if pending_skills:
            for s in pending_skills:
                streak = await skill_queries.get_skill_streak(pool, s["id"])
                streak_str = f" \\(streak: {streak} 🔥\\)" if streak > 0 else ""
                lines.append(f"• {escape_md(s['name'])}{streak_str}")
        else:
            lines.append("Toate skill\\-urile sunt la zi ✅")

        # We don't add the section title if we use generate_time_block directly
        # because it already includes "🗓 *Time Block*"
        if "Nu am putut genera" in time_block_text:
            lines += ["", "🗺 *Planul zilei*"]
            if final_itinerary and final_itinerary.strip():
                lines.append(safe_markdown(final_itinerary.strip()))
            else:
                lines.append("Organizează\\-ți ziua după energie și prioritate\\.")
        else:
            lines += ["", final_itinerary]

        lines += ["", "💡 *Focus*"]
        if focus_raw and focus_raw.strip():
            lines.append(safe_markdown(focus_raw.strip()))
        elif priority_tasks:
            lines.append(escape_md(priority_tasks[0]["title"]))
        else:
            lines.append("O zi la un moment dat\.")

        # Health nudges (subtle, only if needed)
        if health_log:
            nudges = []
            sleep = health_log.get("sleep_hours")
            water = health_log.get("water_ml")
            if sleep and sleep < 6:
                nudges.append(f"Ai dormit doar {sleep:.0f}h\.")
            if water and water < 1500:
                nudges.append(f"Apa e la {int(water / 1000 * 10) / 10:.1f}L\.")
            if nudges:
                lines += ["", "⚠️ " + " ".join(nudges)]

        # 🏋️ Antrenament ieri
        if workouts_yesterday:
            workout_lines = ["", "🏋️ *Antrenament ieri*"]
            for w in workouts_yesterday:
                icon = w.get("icon", "🏋️")
                sport_name = escape_md(w.get("type", "Sport"))
                duration = w.get("duration_min", "?")
                workout_lines.append(f"• {icon} {sport_name}: {duration} min")
            lines += workout_lines

        # 📊 Corelații - predicții bazate pe date
        try:
            from core.correlations import compute_correlations

            recent = await compute_correlations(pool)
            if recent:
                strong = [c for c in recent if c.get("strength") == "puternică"]
                if strong:
                    corr = strong[0]
                    if corr.get("recommendation"):
                        lines += [
                            "",
                            f"📊 *Din date:* {escape_md(corr['recommendation'])}",
                        ]
        except Exception:
            pass

        # 🏛️ Executive Summary from Council
        try:
            from core.council import get_strategy_summary

            strategy_summary = await get_strategy_summary()
            if strategy_summary:
                lines += ["", "🏛️ *Consiliu — Strategic:*", strategy_summary]
        except Exception:
            pass

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
                print(
                    f"Morning brief MarkdownV2 failed, falling back to plain: {e}",
                    flush=True,
                )
                await application.bot.send_message(chat_id=TELEGRAM_USER_ID, text=chunk)

        # 6. Generate and send "podcast" (voice) in background-like manner
        try:
            from bot.tts import text_to_speech
            import os

            print("🎙️ Starting TTS generation for Morning Briefing...", flush=True)
            podcast_data = f"""USER: {name}
TONE: {tone}
DATE: {today.strftime("%A, %d %B %Y")}
WEATHER: {weather_info}

TOP 3 TASKS:
{task_text}

EVENIMENTE AZI:
{event_text}

SKILLS PENDING AZI:
{skill_text}
"""
            podcast_instruction = f"""Ești Lora, asistenta personală a lui {name}.
 Generezi un podcast vocal de dimineață. Scrie să sune natural când e citit cu voce.
 Generează textul podcastului EXCLUSIV în limba română (MAXIM 250 cuvinte).
  Sunt permise DOAR aceste cuvinte în engleză: task, meeting, gym, chess, duolingo.
 INTERZIS COMPLET: the game plan, all clear, catch up, deep work, worry, talk of the town, fun, highlights, insights și orice altă expresie idiomatică în engleză.
  Structură: salut + oră → vreme → top tasks ca plan, nu liste → evenimente + skills → gând scurt motivațional.
 Ton: cald și direct. EVITĂ superlativele și entuziasmul exagerat (ex: super, fascinant, minunat, amazing, extraordinar, wow). Nu repeta 'zâmbete', 'energie', 'bucurie'.
 Vorbește ca un asistent de încredere, nu ca un hype-man. Fără bullet points, fără titluri de secțiuni.
 Formatare: Telegram MarkdownV2 raw (fără backslash escape în JSON)."""
            raw_brief = await get_proactive_response(podcast_instruction, podcast_data)
            tts_text: str = raw_brief or briefing_text
            print(f"🎙️ TTS input length: {len(tts_text)} characters", flush=True)
            voice_file = await text_to_speech(tts_text, podcast_mode=True)
            print(
                f"🎙️ TTS file generated: {voice_file} (size: {os.path.getsize(voice_file)} bytes)",
                flush=True,
            )

            with open(voice_file, "rb") as f:
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
        await profile_queries.update_user_profile(
            pool, TELEGRAM_USER_ID, last_briefing_date=today
        )
        print(f"Morning briefing sent and logged for {today}.", flush=True)

        # ── 8. Interactive Day Plan Flow ──────────────────────────────────
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
            if "application" in dir() and hasattr(application, "bot"):
                await application.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=f"❌ Eroare la briefing: {str(e)[:200]}",
                )
        except Exception as notify_error:
            print(f"Could not notify user of error: {notify_error}", flush=True)


async def send_eod_reflection(application, pool):
    """EOD Reflection: Short daily summary + one reflective question. No state."""
    try:
        user_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(user_tz)
        today = now.date()

        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if profile.get("last_eod_date") == today:
            print(f"EOD reflection already sent for {today} — skipping.", flush=True)
            return

        name = profile.get("name", "User")
        print(f"Starting EOD reflection for {today}...", flush=True)

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
            "_Ce a mers bine azi?_\n\n"
            "Seară liniștită\\. 🌙"
        )

        await application.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=safe_markdown(message),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        try:
            from bot.tts import text_to_speech
            import os

            tts_text = f"Bună seara, {name}. {task_status}. Seară liniștită."
            voice_file = await text_to_speech(tts_text)
            with open(voice_file, "rb") as f:
                await application.bot.send_voice(
                    chat_id=TELEGRAM_USER_ID,
                    voice=f,
                    caption="🎙️ *Lora: Bună seara*",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            if os.path.exists(voice_file):
                os.remove(voice_file)
        except Exception as e:
            print(f"EOD TTS failed: {e}", flush=True)

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

        await application.bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=safe_markdown(message),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

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
                            "✅ Prezent", callback_data=f"attendance:present:{c['id']}"
                        ),
                        InlineKeyboardButton(
                            "❌ Absent", callback_data=f"attendance:absent:{c['id']}"
                        ),
                    ]
                ]
            )

            # 2. Trimite mesaj
            await application.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=msg,
                parse_mode=ParseMode.MARKDOWN_V2,
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


async def send_weekly_review(application, pool) -> None:
    """Aggregates weekly data and sends a reflective review on Sunday evening."""
    from datetime import timedelta, datetime
    import pytz
    from core.config import TIMEZONE, TELEGRAM_USER_ID
    from telegram.constants import ParseMode

    try:
        user_tz = pytz.timezone(TIMEZONE)
        today = datetime.now(user_tz).date()

        # 1. Idempotency Check
        profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
        if profile.get("last_weekly_review_date") == today:
            print(f"Weekly review already sent for {today} — skipping.", flush=True)
            return

        print(f"Starting weekly review for {today}...", flush=True)

        # 2. Date Range (Monday to Sunday)
        start_date = today - timedelta(days=6)
        end_date = today

        # 3. Aggregated Data Collection
        task_stats = await task_queries.get_weekly_task_stats(
            pool, start_date, end_date
        )
        events = await event_queries.list_events(pool, start_date, end_date)

        # Concise Finance Section for Sunday Review
        finance_summary = await finance_queries.get_weekly_finance_summary(
            pool, start_date, end_date
        )
        finance_ctx = (
            f"Cheltuieli totale săptămâna asta: {int(finance_summary['total'])} RON"
        )

        # Enhanced Mood Section
        import db.queries.mood as mood_queries

        weekly_moods = await mood_queries.get_weekly_mood_summary(
            pool, start_date, end_date
        )
        mood_total = sum(weekly_moods.values())
        mood_summary = ""
        if mood_total > 0:
            mood_labels = {
                "great": "super",
                "good": "bine",
                "neutral": "ok",
                "okay": "ok",
                "bad": "slab",
                "terrible": "rău",
                "awful": "rău",
            }
            # Combine duplicates (neutral/okay, terrible/awful)
            combined_moods = {}
            for m, count in weekly_moods.items():
                label = mood_labels.get(m.lower(), "ok")
                combined_moods[label] = combined_moods.get(label, 0) + count

            mood_parts = [
                f"{count} zile {label}" for label, count in combined_moods.items()
            ]
            mood_summary = f"😊 Mood săptămâna asta: {', '.join(mood_parts)}"

        # 3.5 Automated Insights Patterns (corelații)
        from modules.insights import generate_insights

        patterns = await generate_insights(pool)
        patterns_section = ""
        if patterns and "nu am suficiente date" not in patterns.lower():
            patterns_section = f"\n🧠 *Patterns observate*\n{patterns}\n"

        try:
            from core.correlations import compute_correlations

            raw_correlations = await compute_correlations(pool)
            if raw_correlations:
                corr_lines = ["", "🧬 *Corelații detectate:*"]
                for c in raw_correlations[:3]:
                    icon = "🔴" if c.get("strength") == "puternică" else "🟡"
                    corr_text = c.get("correlation", "")
                    rec = c.get("recommendation", "")
                    if corr_text and rec:
                        corr_lines.append(
                            f"{icon} *{escape_md(corr_text)}* → {escape_md(rec)}"
                        )
                if len(corr_lines) > 1:
                    patterns_section += "\n".join(corr_lines) + "\n"
        except Exception:
            pass

        journals = await journal_queries.get_recent_journal_entries(pool, limit=7)

        # 3.8 Nutrition Weekly Stats
        async with pool.acquire() as conn:
            nutrition_stats = await conn.fetchrow(
                """
                SELECT 
                    AVG(total_calories) as avg_cal,
                    AVG(total_protein) as avg_prot,
                    COUNT(id) FILTER (WHERE total_protein < (SELECT protein_g * 0.8 FROM nutrition_targets LIMIT 1)) as low_prot_days
                FROM (
                    SELECT meal_date, SUM(total_calories) as total_calories, SUM(total_protein) as total_protein
                    FROM meals WHERE meal_date BETWEEN $1 AND $2
                    GROUP BY meal_date
                ) daily
            """,
                start_date,
                end_date,
            )
            await conn.fetchrow("SELECT * FROM nutrition_targets LIMIT 1")

        nutrition_ctx = ""
        if nutrition_stats and nutrition_stats["avg_cal"]:
            nutrition_ctx = f"Media calorii: {int(nutrition_stats['avg_cal'])} kcal, Media proteină: {int(nutrition_stats['avg_prot'])}g."
            if nutrition_stats["low_prot_days"] >= 3:
                nutrition_ctx += f" Atenție: {nutrition_stats['low_prot_days']} zile sub targetul de proteină."

        # 3.7 Health & Mood Correlations Data
        health_week = await health_queries.get_health_history(pool, 7)
        mood_week = await note_queries.get_weekly_mood_data(pool, start_date, end_date)
        tasks_per_day = await task_queries.get_completed_tasks_per_day(
            pool, start_date, end_date
        )

        # Restore Formatting for Context

        event_ctx = [e["title"] for e in events]

        health_ctx = ""
        if health_week:
            health_lines = []
            for h in health_week:
                health_lines.append(
                    f"{h['log_date']}: Sleep {h['sleep_hours']}h, Water {h['water_ml']}ml, Nutrition {h['nutrition']}"
                )
            health_ctx = "\n".join(health_lines)

        mood_map = {"great": 5, "good": 4, "neutral": 3, "bad": 2, "terrible": 1}
        mood_ctx = "\n".join(
            [f"{m['date']}: {mood_map.get(m['mood'].lower(), 3)}" for m in mood_week]
        )
        tasks_ctx = "\n".join(
            [f"{t['date']}: {t['count']} tasks" for t in tasks_per_day]
        )

        # Format journals for context
        journal_moods = [j["mood"] for j in journals if j.get("mood")]

        data_summary = f"""
SĂPTĂMÂNA: {start_date} — {end_date}
TASKS: {task_stats["completed"]} completate din {task_stats["added"]} adăugate săptămâna asta.
FINANCE BREAKDOWN:
{finance_ctx}
MOOD SUMMARY: {mood_summary}
PATTERNS: {patterns_section}
EVENTS: {", ".join(event_ctx)}
JOURNALS (MOODS): {", ".join(journal_moods)}
NUTRITION STATS: {nutrition_ctx}

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
Ești Lora, asistenta personală a lui {profile.get("name", "User")}. 
Generează un weekly review structurat în română.
Tone: reflectiv, direct, calm, fără hype. 
Interzis: bravos, vibes, wins, achievements.

Structură FIXĂ (MarkdownV2):
📊 *Săptămâna {start_date.strftime("%d.%m")} — {end_date.strftime("%d.%m")}*

✅ *Tasks*: {task_stats["completed"]} completate din {task_stats["added"]}

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
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        # 6. Send Voice Version (TTS)
        try:
            from bot.tts import text_to_speech
            import os

            # Clean text for TTS
            tts_clean = (
                review_text.replace("*", "")
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
                            "👍 Ok", callback_data=f"event_reminder_ack:{e['id']}"
                        ),
                        InlineKeyboardButton(
                            "📝 Note", callback_data=f"event_note:{e['id']}"
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
                            "👍 Ok", callback_data=f"event_day_ack:{e['id']}"
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
                    callback_data=f"habit_done:{h['id']}",
                )
            ]
            for h in rows[:5]
        ]

        if len(rows) > 5:
            keyboard_buttons.append(
                [InlineKeyboardButton("📋 Vezi toate", callback_data="list_habits")]
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
                WHERE t.status = 'pending'
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
                        "✅ Mark done", callback_data="task_reminder_dismiss"
                    ),
                    InlineKeyboardButton("📝 Note", callback_data="view_pending_tasks"),
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

    # 3. EOD Reflection - short daily summary at configured EOD time
    scheduler.add_job(
        send_eod_reflection,
        "cron",
        hour=e_h,
        minute=e_m,
        misfire_grace_time=3600,
        args=[application, pool],
    )

    # 4. Journal Night - 3 reflection questions at 22:00
    j_h, j_m = map(int, JOURNAL_NIGHT_TIME.split(":"))
    scheduler.add_job(
        send_journal_night,
        "cron",
        hour=j_h,
        minute=j_m,
        misfire_grace_time=3600,
        args=[application, pool],
    )

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

    scheduler.start()
    print("Scheduler started with misfire grace periods.")
    return scheduler

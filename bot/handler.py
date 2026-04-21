import traceback
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes
from core.config import TELEGRAM_USER_ID
from bot.onboarding import (
    start_onboarding,
    handle_onboarding,
)
from db.queries.profile import is_onboarding_complete, get_user_profile
from bot.formatter import escape_md, safe_markdown, split_message

from core.context import build_context
from core.gemini import get_gemini_response
from core.router import route_intent


async def security_check(update: Update) -> bool:
    """Rejects non-whitelisted user IDs silently."""
    if not update.effective_user:
        return False

    is_authorized = update.effective_user.id == TELEGRAM_USER_ID
    if not is_authorized:
        print(
            f"❌ UNAUTHORIZED: Access attempt by ID {update.effective_user.id} (Expected {TELEGRAM_USER_ID})"
        )
    else:
        print(f"✅ AUTHORIZED: User ID {update.effective_user.id}")
    return is_authorized


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    """Handles incoming voice messages, transcribes them, and follows the text flow."""
    if not await security_check(update):
        return

    try:
        from bot.voice import transcribe_voice

        try:
            text = await transcribe_voice(update, context)
            if not text:
                raise ValueError("Buit-in check failed")
        except ValueError as e:
            # Romanian error responses as requested
            await update.message.reply_text(str(e))
            return
        except Exception as e:
            print(f"Transcription error: {e}")
            await update.message.reply_text(
                "Nu am putut înțelege mesajul vocal — încearcă din nou 🎙"
            )
            return

        # Pass transcribed text to the existing message handler logic
        print(f"🎙 VOICE TRANSCRIBED: {repr(text)}")
        return await message_handler(update, context, pool, text=text)

    except Exception as e:
        print(f"ERROR in voice_handler: {e}")
        traceback.print_exc()


async def focus_command(update, context):
    pool = context.bot_data.get("pool")
    text = update.message.text

    parts = text.split()
    duration = 25
    if len(parts) > 1 and parts[1].isdigit():
        duration = int(parts[1])

    from modules.focus import handle_focus_intent

    reply, markup = await handle_focus_intent(
        pool, "focus_start", {"duration_min": duration}, bot=context.bot
    )
    await update.message.reply_text(reply, parse_mode="MarkdownV2")


async def stopfocus_command(update, context):
    pool = context.bot_data.get("pool")
    from modules.focus import handle_focus_intent

    reply, markup = await handle_focus_intent(pool, "focus_stop", {}, bot=context.bot)
    await update.message.reply_text(reply, parse_mode="MarkdownV2")


async def timeblock_command(update, context):
    pool = context.bot_data.get("pool")
    await update.message.reply_text("🗓 Generez time block-ul tău... un moment!")
    from modules.planner import generate_time_block

    reply, markup = await generate_time_block(pool)
    await update.message.reply_text(reply, parse_mode="MarkdownV2")


async def uni_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /uni command — opens academic dashboard."""
    pool = context.bot_data.get("pool")
    if not pool:
        await update.message.reply_text("Database pool error.")
        return
    await show_uni_dashboard(update.message, pool, send_new=True)


async def workout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /workout command — opens workout dashboard."""
    pool = context.bot_data.get("pool")
    if not pool:
        await update.message.reply_text("Database pool error.")
        return
    from modules.workout import get_workout_dashboard

    text, markup = await get_workout_dashboard(pool)
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates and sends the .ics calendar file."""
    pool = context.application.bot_data.get("pool")
    if not pool:
        await update.message.reply_text("Database pool not found.")
        return

    from core.ical import generate_user_calendar
    from core.config import TELEGRAM_BOT_TOKEN
    import io
    import os

    try:
        await update.message.reply_chat_action("upload_document")

        # Link for automatic synchronization (HTTPS/WebCal)
        token = TELEGRAM_BOT_TOKEN.split(":")[0]
        domain = (
            os.environ.get("WEB_DOMAIN", "lora-bot.onrender.com")
            .replace("https://", "")
            .replace("http://", "")
            .rstrip("/")
        )
        webcal_url = f"https://{domain}/calendar/{token}"

        ics_bytes = await generate_user_calendar(pool)

        bio = io.BytesIO(ics_bytes)
        bio.name = "lora_calendar.ics"

        text = (
            "✨ *Sincronizare Calendar Lora* ✨\n\n"
            "Pentru a vedea evenimentele pe iPhone/Mac:\n"
            "1️⃣ Copiază link-ul: `" + webcal_url + "`\n"
            "2️⃣ În aplicația *Calendar* mergi la *Add Subscription Calendar*\n"
            "3️⃣ Lipeste link-ul și salvează\\.\n\n"
            "🔄 _Sincronizarea este automată la orice modificare!_"
        )

        await update.message.reply_document(
            document=bio,
            filename="lora_calendar.ics",
            caption=text,
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        await update.message.reply_text(f"Eroare la generarea calendarului: {e}")
        import traceback

        traceback.print_exc()


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    """Handles incoming photos, sending them to the Vision Module."""
    if not await security_check(update):
        return

    try:
        from core.vision import analyze_image, process_vision_result
        from core.gemini import client

        # Send loading message
        loading_msg = await update.message.reply_text("Analizând imaginea... 👁️")

        # Get highest resolution photo
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        caption = update.message.caption

        # Analyze using Vision Module
        result = await analyze_image(client, bytes(photo_bytes), caption)

        if result.get("type") == "error":
            await loading_msg.edit_text(
                result.get("reply", "Eroare la procesarea imaginii.")
            )
            return

        profile = await get_user_profile(pool, TELEGRAM_USER_ID)

        # Process result and get formatting
        reply_text, keyboard = await process_vision_result(
            pool, result, profile, client
        )

        # Edit loading message with real reply
        try:
            await loading_msg.edit_text(
                reply_text, parse_mode="MarkdownV2", reply_markup=keyboard
            )
        except Exception as edit_err:
            print(f"Error editing loading msg with MarkdownV2: {edit_err}")
            await loading_msg.edit_text(reply_text, reply_markup=keyboard)

    except Exception as e:
        import traceback

        print(f"Error handling photo: {e}")
        traceback.print_exc()
        try:
            await update.message.reply_text("A apărut o eroare la procesarea pozei.")
        except Exception:
            pass


async def message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pool, text=None
):
    # Log EVERYTHING first
    print(f"DEBUG: message_handler triggered for update {update.update_id}", flush=True)

    # Log EVERY message before the security check
    user_id = update.effective_user.id if update.effective_user else "Unknown"

    # Use provided text or fallback to message text
    if text is None and update.message:
        text = update.message.text

    # Fix common STT (speech-to-text) typos before processing
    if text:
        original_text = text
        low_text = text.lower()

        # Fix typos in lowercase version
        low_text = low_text.replace("adamga", "adauga")
        low_text = low_text.replace("adamg", "adaug")
        low_text = low_text.replace("adăuga", "adauga")
        low_text = low_text.replace("adaugă", "adaug")
        low_text = low_text.replace("cărții", "carti")
        low_text = low_text.replace("cărţi", "carti")
        low_text = low_text.replace("şt", "st")
        low_text = low_text.replace("ţ", "t")

        # Handle duplicate text from STT (e.g., "text.text")
        if low_text.count(".") > 1:
            parts = low_text.split(".")
            # Keep first non-empty part
            low_text = next((p.strip() for p in parts if p.strip()), parts[0])
            # For STT consistency, we update text too if it was likely a duplicate voice result
            text = low_text

        if low_text != original_text.lower():
            print(f"🔧 STT FIX: '{original_text}' -> '{low_text}'")

    print(
        f"📥 RECEIVED: Update ID {update.update_id} from user_id {user_id} - Text: {repr(text)}"
    )

    if not await security_check(update):
        return

    # --- COMANDĂ CALENDAR (DETECTION) ---
    if text:
        clean_text = text.strip().lower()
        if clean_text.startswith("/test_calendar"):
            from core.calendar import test_connection
            res = await test_connection()
            status = "✅" if res["success"] else "❌"
            msg = f"{status} *iCloud Status*\n\n{escape_md(res['message'])}\n\n"
            if res.get("calendars"):
                msg += "Calendare găsite:\n" + "\n".join(f"• {escape_md(c)}" for c in res["calendars"])
            await update.message.reply_text(msg, parse_mode="MarkdownV2")
            return

        if clean_text.startswith("/sync_calendar"):
            from modules.calendar_module import handle_calendar_intent
            reply, _ = await handle_calendar_intent(pool, "calendar_sync", {})
            await update.message.reply_text(reply, parse_mode="MarkdownV2")
            return

    # ── GROUP ROUTING ──
    # If in a group, only respond if explicitly mentioned
    if update.effective_chat and update.effective_chat.type in ("group", "supergroup"):
        # Lazy-get bot username
        bot_username = context.application.bot_data.get("bot_username")
        if not bot_username:
            me = await context.bot.get_me()
            bot_username = me.username
            context.application.bot_data["bot_username"] = bot_username

        # Check for mention in entities or text
        is_mentioned = False
        if update.message and update.message.entities:
            for ent in update.message.entities:
                if ent.type == "mention":
                    mentioned_text = update.message.text[
                        ent.offset : ent.offset + ent.length
                    ].lower()
                    if f"@{bot_username.lower()}" == mentioned_text:
                        is_mentioned = True
                        break

        if not is_mentioned and f"@{bot_username.lower()}" not in (text or "").lower():
            print(
                f"🔇 LORA SILENT: Message in group {update.effective_chat.id} doesn't mention @{bot_username}"
            )
            return

    try:
        telegram_id = update.effective_user.id

        # Non-text message handling
        if not update.message or (not text and not update.message.voice):
            if update.message and (
                update.message.photo or update.message.video or update.message.sticker
            ):
                await update.message.reply_text(
                    "I can only read text for now — what would you like to do?"
                )
            return

        # Handle /tasks command
        if text.startswith("/tasks"):
            from modules.tasks import get_tasks_dashboard

            text_out, markup = await get_tasks_dashboard(pool)
            await update.message.reply_text(
                text_out, parse_mode="MarkdownV2", reply_markup=markup
            )
            return

        # Handle /reload command
        if text == "/reload":
            await update.message.reply_text(
                "🔄 Reloading Lora... I'll be back in a second!"
            )
            import os
            import sys
            from db.connection import close_pool

            await close_pool()
            os.execl(sys.executable, sys.executable, *sys.argv)
            return

        # Handle /podcast command
        if text == "/podcast":
            from scheduler.jobs import send_morning_briefing

            await update.message.reply_text(
                "🎙️ Generăm podcast-ul tău personal... un moment!"
            )

            from db.queries.profile import update_user_profile
            from core.config import TELEGRAM_USER_ID

            try:
                await update_user_profile(
                    pool, TELEGRAM_USER_ID, last_briefing_date=date.today()
                )
                await send_morning_briefing(context.application, pool)
            except Exception as e:
                print(f"Podcast manual trigger error: {e}", flush=True)
                await update.message.reply_text(
                    f"❌ Scuze, a apărut o eroare la generarea podcast-ului: {e}"
                )
            return

        # Handle /weeklyreview command
        if text == "/weeklyreview":
            from scheduler.jobs import send_weekly_review

            await update.message.reply_text(
                "📊 Generăm review-ul tău săptămânal... un moment!"
            )

            try:
                await send_weekly_review(context.application, pool)
            except Exception as e:
                print(f"Weekly review manual trigger error: {e}", flush=True)
                await update.message.reply_text(
                    f"❌ Eroare la generarea review-ului: {e}"
                )
            return

        # Handle /monthlyreview command
        if text == "/monthlyreview":
            from scheduler.jobs import send_monthly_review
            from db.queries.profile import update_user_profile

            await update.message.reply_text(
                "📊 Generăm review-ul tău lunar... un moment!"
            )

            try:
                # Reset last_monthly_review_date to None to allow manual trigger
                await update_user_profile(
                    pool, TELEGRAM_USER_ID, last_monthly_review_date=None
                )
                await send_monthly_review(context.bot, pool)
            except Exception as e:
                print(f"Monthly review manual trigger error: {e}", flush=True)
                await update.message.reply_text(
                    f"❌ Eroare la generarea review-ului lunar: {e}"
                )
            return

        # Handle /habitstreaks command

        # Handle /journal and /eod commands
        if text == "/journal":
            from db.queries.profile import update_user_profile
            from core.config import TELEGRAM_USER_ID as TG_UID
            from scheduler.jobs import send_journal_night

            try:
                await update_user_profile(pool, TG_UID, last_journal_date=None)
                await send_journal_night(context.application, pool)
            except Exception as e:
                print(f"Journal night manual trigger error: {e}", flush=True)
                await update.message.reply_text(
                    f"❌ Eroare la inițierea journal-ului: {e}"
                )
            return

        if text == "/eod":
            from db.queries.profile import update_user_profile
            from core.config import TELEGRAM_USER_ID as TG_UID
            from scheduler.jobs import send_eod_reflection

            try:
                await update_user_profile(pool, TG_UID, last_eod_date=None)
                await send_eod_reflection(context.application, pool)
            except Exception as e:
                print(f"EOD reflection manual trigger error: {e}", flush=True)
                await update.message.reply_text(
                    f"❌ Eroare la inițierea EOD reflection: {e}"
                )
            return
        # Handle /plan command
        if text == "/plan":
            from db.queries.profile import update_user_profile
            from core.config import TELEGRAM_USER_ID as TG_UID
            from core.state import set_state
            from modules.planner import get_day_preview

            try:
                await update_user_profile(pool, TG_UID, last_plan_date=None)
                preview = await get_day_preview(pool)
                await update.message.reply_text(preview, parse_mode="MarkdownV2")
                await set_state(
                    pool, "awaiting_day_plan_input", "day_plans", "generate", None
                )
            except Exception as e:
                print(f"Plan manual trigger error: {e}", flush=True)
                await update.message.reply_text(f"❌ Eroare la inițierea planului: {e}")
            return

        # 3.8 Health Chart Direct Bypass (to avoid Gemini misinterpretation)
        health_chart_triggers = [
            "grafic health",
            "grafic somn",
            "grafic apă",
            "grafic apa",
            "grafic greutate",
            "cum am dormit",
        ]
        low_text = text.lower()
        if any(trigger in low_text for trigger in health_chart_triggers):
            intent_response = {
                "intent": "health_chart",
                "module": "health",
                "data": {"_original_reply": "Generăm graficul tău... 📊"},
                "reply": "Generăm graficul tău... 📊",
            }
            final_reply, reply_markup = await route_intent(
                pool, intent_response, bot=context.bot
            )
            if final_reply:
                # Save assistant reply to conversations
                async with pool.acquire() as conn:
                    await conn.execute(
                        "INSERT INTO conversations (role, content) VALUES ($1, $2)",
                        "assistant",
                        final_reply,
                    )
                await update.message.reply_text(
                    final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup
                )
            return

        # Check onboarding status
        onboarding_done = await is_onboarding_complete(pool, telegram_id)
        onboarding_step = context.user_data.get("onboarding_step")

        if not onboarding_done or onboarding_step:
            if text == "/start":
                await start_onboarding(update, context, pool)
            else:
                await handle_onboarding(update, context, pool)
            return

        # Phase 3: Gemini Brain integration
        async with pool.acquire() as conn:
            # 1. Get history (last 10 turns, BOTH roles) BEFORE saving current message
            history_rows = await conn.fetch(
                "SELECT role, content FROM conversations ORDER BY created_at DESC LIMIT 10"
            )
            # Reverse to get chronological order
            history = [
                {"role": r["role"], "content": r["content"]}
                for r in reversed(history_rows)
            ]

            # 2. Save current user message to conversations
            await conn.execute(
                "INSERT INTO conversations (role, content) VALUES ($1, $2)",
                "user",
                text,
            )

        # Phase 8: State Check (Confirmations / Edits)
        from core.state import get_state, clear_state

        state = await get_state(pool)

        # Skills State Handling
        if state and state["state_type"].startswith("skills_"):
            from modules.skills import handle_skills_message

            if await handle_skills_message(update, context, pool, state):
                return

        # Reading State Handling
        if state and state["state_type"].startswith("reading_"):
            from modules.reading import handle_reading_message

            if await handle_reading_message(update, pool, state):
                return

        if state:
            print(
                f"🔄 STATE ACTIVE: {state['state_type']} for {state['module']}:{state['action']}",
                flush=True,
            )
            if state["state_type"] == "awaiting_confirmation":
                low_text = text.lower()
                if any(
                    word in low_text
                    for word in ["yes", "yeah", "do it", "confirm", "sure", "da"]
                ):
                    data = {"id": state["item_id"], "confirmed": True}
                    intent = f"{state['action']}_confirmed"
                    intent_response = {
                        "intent": intent,
                        "module": state["module"],
                        "data": data,
                        "reply": "Confirmed. Working on it...",
                        "needs_confirmation": False,
                    }
                    await clear_state(pool)
                    final_reply, reply_markup = await route_intent(
                        pool, intent_response, bot=context.bot
                    )
                    await update.message.reply_text(
                        final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup
                    )
                    return
                elif any(
                    word in low_text for word in ["no", "stop", "cancel", "don't", "nu"]
                ):
                    await clear_state(pool)
                    await update.message.reply_text("Cancelled\\.")
                    return
                else:
                    await clear_state(pool)

            elif state["state_type"] == "awaiting_focus_result":
                session_id = state.get("item_id")
                import db.queries.focus as focus_queries

                if session_id:
                    await focus_queries.complete_session(pool, session_id, text)
                await clear_state(pool)
                await update.message.reply_text(
                    "Notat\\. Sesiune salvată\\. 💪", parse_mode="MarkdownV2"
                )
                return

            elif state["state_type"] == "awaiting_uni_input":
                action = state.get("action")
                if action == "add_subject":
                    from db.queries.university import add_subject

                    await add_subject(pool, text)
                    await clear_state(pool)
                    await update.message.reply_text(
                        f"✅ *{escape_md(text)}* adăugată\\.", parse_mode="MarkdownV2"
                    )
                    return

                elif action == "add_schedule":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        days_map = {
                            "luni": 0,
                            "marți": 1,
                            "miercuri": 2,
                            "joi": 3,
                            "vineri": 4,
                        }
                        day = days_map.get(parts[0].lower(), 0)
                        times = parts[1].split("-")
                        start_time = times[0].strip()
                        end_time = times[1].strip()
                        subject = parts[2].strip()
                        class_type = parts[3].strip().lower()
                        room = parts[4].strip() if len(parts) > 4 else None
                        week_type = (
                            parts[5].strip().lower() if len(parts) > 5 else "both"
                        )
                        await pool.execute(
                            """
                            INSERT INTO schedule (day_of_week, start_time, end_time, subject_name, class_type, room, week_type)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                            day,
                            start_time,
                            end_time,
                            subject,
                            class_type,
                            room,
                            week_type,
                        )
                        await clear_state(pool)
                        await update.message.reply_text(
                            "✅ Oră adăugată în orar\\.", parse_mode="MarkdownV2"
                        )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\. Încearcă: `Luni, 08:00\\-09:30, MRU, seminar, 208, odd`",
                            parse_mode="MarkdownV2",
                        )
                    return

                elif action == "add_exam":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        from db.queries.university import get_subject_by_name, add_exam
                        from datetime import datetime

                        subject = await get_subject_by_name(pool, parts[0])
                        exam_date = datetime.strptime(
                            parts[1].strip(), "%Y-%m-%d"
                        ).date()
                        exam_type = parts[2].strip() if len(parts) > 2 else "examen"
                        location = parts[3].strip() if len(parts) > 3 else None
                        if subject:
                            await add_exam(
                                pool, subject["id"], exam_date, exam_type, location
                            )
                            await clear_state(pool)
                            await update.message.reply_text(
                                "✅ Examen adăugat\\.", parse_mode="MarkdownV2"
                            )
                        else:
                            await clear_state(pool)
                            await update.message.reply_text(
                                f"❌ Materia *{escape_md(parts[0])}* nu e în listă\\.",
                                parse_mode="MarkdownV2",
                            )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\.", parse_mode="MarkdownV2"
                        )
                    return

                elif action == "add_grade":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        from db.queries.university import get_subject_by_name, add_grade

                        subject = await get_subject_by_name(pool, parts[0])
                        if subject:
                            grade_type = parts[2].strip() if len(parts) > 2 else "exam"
                            await add_grade(
                                pool, subject["id"], float(parts[1]), grade_type
                            )
                            await clear_state(pool)
                            await update.message.reply_text(
                                "✅ Notă adăugată\\.", parse_mode="MarkdownV2"
                            )
                        else:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Materia nu e în listă\\.", parse_mode="MarkdownV2"
                            )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\.", parse_mode="MarkdownV2"
                        )
                    return

                elif action == "add_attendance":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        from db.queries.university import (
                            get_subject_by_name,
                            log_attendance,
                        )
                        from datetime import datetime, date as _date

                        subject = await get_subject_by_name(pool, parts[0])
                        attended = parts[1].strip().lower() in [
                            "prezent",
                            "da",
                            "yes",
                            "true",
                        ]
                        att_date = (
                            datetime.strptime(parts[2].strip(), "%Y-%m-%d").date()
                            if len(parts) > 2
                            else _date.today()
                        )
                        if subject:
                            await log_attendance(
                                pool, subject["id"], attended, att_date
                            )
                            await clear_state(pool)
                            status = "prezent ✅" if attended else "absent ❌"
                            await update.message.reply_text(
                                f"{escape_md(subject['name'])} — {status} înregistrat\\.",
                                parse_mode="MarkdownV2",
                            )
                        else:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Materia nu e în listă\\.", parse_mode="MarkdownV2"
                            )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\.", parse_mode="MarkdownV2"
                        )
                    return

                elif action == "edit_attendance":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        from db.queries.university import get_subject_by_name
                        from datetime import datetime

                        subject = await get_subject_by_name(pool, parts[0])
                        att_date = datetime.strptime(
                            parts[1].strip(), "%Y-%m-%d"
                        ).date()
                        attended = parts[2].strip().lower() in [
                            "prezent",
                            "da",
                            "yes",
                            "true",
                        ]
                        if subject:
                            await pool.execute(
                                "UPDATE attendances SET attended = $1 WHERE subject_id = $2 AND class_date = $3",
                                attended,
                                subject["id"],
                                att_date,
                            )
                            await clear_state(pool)
                            status = "prezent ✅" if attended else "absent ❌"
                            await update.message.reply_text(
                                f"Prezența actualizată — {status}\\.",
                                parse_mode="MarkdownV2",
                            )
                        else:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Materia nu e în listă\\.", parse_mode="MarkdownV2"
                            )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\.", parse_mode="MarkdownV2"
                        )
                    return

                elif action == "delete_grade":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        from db.queries.university import get_subject_by_name

                        subject = await get_subject_by_name(pool, parts[0])
                        grade_type = parts[1].strip() if len(parts) > 1 else None
                        if subject:
                            if grade_type:
                                await pool.execute(
                                    "DELETE FROM grades WHERE subject_id = $1 AND grade_type = $2",
                                    subject["id"],
                                    grade_type,
                                )
                            else:
                                await pool.execute(
                                    "DELETE FROM grades WHERE subject_id = $1",
                                    subject["id"],
                                )
                            await clear_state(pool)
                            await update.message.reply_text(
                                "✅ Notă ștearsă\\.", parse_mode="MarkdownV2"
                            )
                        else:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Materia nu e în listă\\.", parse_mode="MarkdownV2"
                            )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\.", parse_mode="MarkdownV2"
                        )
                    return

                elif action == "import_schedule_photo":
                    if update.message.photo:
                        photo = update.message.photo[-1]
                        file = await context.bot.get_file(photo.file_id)

                        import tempfile
                        import os

                        with tempfile.NamedTemporaryFile(
                            suffix=".jpg", delete=False
                        ) as tmp:
                            await file.download_to_drive(tmp.name)
                            tmp_path = tmp.name

                        import base64

                        with open(tmp_path, "rb") as f:
                            image_data = base64.b64encode(f.read()).decode()
                        os.unlink(tmp_path)

                        from google import genai
                        from google.genai import types
                        from core.config import GEMINI_API_KEY

                        client = genai.Client(api_key=GEMINI_API_KEY)
                        prompt = """
Analizează această imagine cu un orar universitar.
Extrage TOATE cursurile și seminarele vizibile.
Returnează EXCLUSIV JSON valid, fără markdown:
{
  "classes": [
    {
      "day": "Luni|Marți|Miercuri|Joi|Vineri",
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "subject": "numele materiei",
      "type": "curs|seminar",
      "room": "sala sau null",
      "week_type": "both|odd|even"
    }
  ]
}
week_type: "odd" dacă e marcat SI, "even" dacă SP, "both" dacă apare în ambele sau nu e marcat.
"""
                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=[
                                types.Content(
                                    parts=[
                                        types.Part(
                                            inline_data=types.Blob(
                                                mime_type="image/jpeg", data=image_data
                                            )
                                        ),
                                        types.Part(text=prompt),
                                    ]
                                )
                            ],
                        )

                        import json

                        raw = response.text.strip()
                        if "```" in raw:
                            raw = (
                                raw.split("```")[1].lstrip("json").strip().rstrip("```")
                            )

                        try:
                            data_parsed = json.loads(raw)
                            classes = data_parsed.get("classes", [])

                            days_map = {
                                "luni": 0,
                                "marți": 1,
                                "miercuri": 2,
                                "joi": 3,
                                "vineri": 4,
                            }
                            imported = 0

                            for c in classes:
                                day = days_map.get(c["day"].lower(), -1)
                                if day == -1:
                                    continue
                                await pool.execute(
                                    """
                                    INSERT INTO schedule (day_of_week, start_time, end_time, 
                                        subject_name, class_type, room, week_type)
                                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                                    ON CONFLICT DO NOTHING
                                """,
                                    day,
                                    c["start_time"],
                                    c["end_time"],
                                    c["subject"],
                                    c.get("type", "curs"),
                                    c.get("room"),
                                    c.get("week_type", "both"),
                                )
                                imported += 1

                            await clear_state(pool)
                            await update.message.reply_text(
                                f"✅ *{imported} ore importate* din orar\\.\nVerifică cu `/uni` → Orar și ajustează unde este nevoie\\.",
                                parse_mode="MarkdownV2",
                            )
                        except Exception:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Nu am putut extrage orarul din imagine\\. Încearcă o poză mai clară sau adaugă manual\\.",
                                parse_mode="MarkdownV2",
                            )
                    else:
                        await update.message.reply_text(
                            "Trimite o poză \\(nu text\\) cu orarul tău\\.",
                            parse_mode="MarkdownV2",
                        )
                    return

                elif action == "import_structure_pdf":
                    if (
                        update.message.document
                        and update.message.document.mime_type == "application/pdf"
                    ):
                        file = await context.bot.get_file(
                            update.message.document.file_id
                        )

                        import tempfile
                        import os
                        import base64

                        with tempfile.NamedTemporaryFile(
                            suffix=".pdf", delete=False
                        ) as tmp:
                            await file.download_to_drive(tmp.name)
                            tmp_path = tmp.name

                        with open(tmp_path, "rb") as f:
                            pdf_data = base64.b64encode(f.read()).decode()
                        os.unlink(tmp_path)

                        from google import genai
                        from google.genai import types
                        from core.config import GEMINI_API_KEY

                        client = genai.Client(api_key=GEMINI_API_KEY)
                        prompt = """
Analizează acest document cu structura anului universitar.
Extrage TOATE perioadele importante.
Returnează EXCLUSIV JSON valid:
{
  "academic_year": "YYYY-YYYY",
  "semesters": [
    {
      "number": 1,
      "periods": [
        {
          "type": "activitate_didactica|vacanta|sesiune_examene|sesiune_restante",
          "start_date": "YYYY-MM-DD",
          "end_date": "YYYY-MM-DD",
          "description": "descriere scurtă opțională"
        }
      ]
    }
  ]
}
"""
                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=[
                                types.Content(
                                    parts=[
                                        types.Part(
                                            inline_data=types.Blob(
                                                mime_type="application/pdf",
                                                data=pdf_data,
                                            )
                                        ),
                                        types.Part(text=prompt),
                                    ]
                                )
                            ],
                        )

                        import json

                        raw = response.text.strip()
                        if "```" in raw:
                            raw = (
                                raw.split("```")[1].lstrip("json").strip().rstrip("```")
                            )

                        try:
                            data_parsed = json.loads(raw)

                            await pool.execute("""
                                CREATE TABLE IF NOT EXISTS academic_periods (
                                    id SERIAL PRIMARY KEY,
                                    academic_year VARCHAR(10),
                                    semester INTEGER,
                                    period_type VARCHAR(50),
                                    start_date DATE,
                                    end_date DATE,
                                    description TEXT,
                                    created_at TIMESTAMP DEFAULT NOW(),
                                    UNIQUE (academic_year, semester, period_type, start_date)
                                )
                            """)

                            imported = 0
                            for sem in data_parsed.get("semesters", []):
                                for period in sem.get("periods", []):
                                    from datetime import datetime

                                    await pool.execute(
                                        """
                                        INSERT INTO academic_periods 
                                            (academic_year, semester, period_type, start_date, end_date, description)
                                        VALUES ($1, $2, $3, $4, $5, $6)
                                        ON CONFLICT DO NOTHING
                                    """,
                                        data_parsed.get("academic_year", "2025-2026"),
                                        sem["number"],
                                        period["type"],
                                        datetime.strptime(
                                            period["start_date"], "%Y-%m-%d"
                                        ).date(),
                                        datetime.strptime(
                                            period["end_date"], "%Y-%m-%d"
                                        ).date(),
                                        period.get("description"),
                                    )
                                    imported += 1

                            await clear_state(pool)
                            await update.message.reply_text(
                                f"✅ *{imported} perioade importate* din structura academică\\.",
                                parse_mode="MarkdownV2",
                            )
                        except Exception:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Nu am putut extrage structura din PDF\\. Încearcă din nou\\.",
                                parse_mode="MarkdownV2",
                            )
                    else:
                        await update.message.reply_text(
                            "Trimite un fișier PDF \\(nu text\\)\\.",
                            parse_mode="MarkdownV2",
                        )
                    return

            elif state["state_type"] == "awaiting_edit_field":
                context_snapshot = await build_context(pool, text)
                profile = await get_user_profile(pool, telegram_id)
                edit_prompt = f"The user wants to edit an item. Module: {state['module']}, Item ID: {state['item_id']}. User input: {text}"

                intent_response = await get_gemini_response(
                    pool,
                    user_message=edit_prompt,
                    user_name=profile.get("name", "User"),
                    tone=profile.get("tone", "warm"),
                    context_snapshot=context_snapshot,
                    history=[],
                    personal_notes=f"ACTION: Extract the fields to change for item {state['item_id']} in module {state['module']}. Return intent='edit_{state['module'][:-1]}', data={{'id': {state['item_id']}, ...fields...}}",
                )

                await clear_state(pool)
                final_reply, reply_markup = await route_intent(
                    pool, intent_response, bot=context.bot
                )
                await update.message.reply_text(
                    final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup
                )
                return

            elif state["state_type"] == "awaiting_day_plan_input":
                # If command, clear state and proceed
                if text.startswith("/"):
                    await clear_state(pool)
                elif any(
                    w in text.lower()
                    for w in [
                        "remintește-mi",
                        "uită-mă",
                        "amintește-mi",
                        "reapă-mă",
                        "setează reminder",
                        "adu-mi aminte",
                        "adumă aminte",
                        "aminteste-mi",
                    ]
                ):
                    # It's a reminder intent - clear state and let normal flow handle it
                    await clear_state(pool)
                else:
                    try:
                        from db.queries.day_plans import save_day_plan
                        from core.gemini import get_proactive_response
                        from datetime import date as _date

                        today = _date.today()
                        profile = await get_user_profile(pool, telegram_id)
                        context_snapshot = await build_context(pool, text)

                        itinerary_instruction = """
Userul a descris cum vrea să-i arate ziua. Pe baza preferințelor lui și a tasks/events/habits din context, generează un itinerar structurat pe ore. 
Format:
🗺 *Planul tău de azi*

08:00 — [activitate]
10:00 — [activitate]
...

Reguli:
- Respectă preferințele userului ca prioritate maximă.
- Integrează events fixe la orele lor exacte din calendar.
- Distribuie tasks și habits în sloturile rămase.
- Fii realist cu timpii (nu supraaglomera).
- Dacă userul nu menționează o activitate din context, integreaz-o natural unde are sens.
- Maxim 8 slots orare.
- Limbă: română, același ton ca restul Lorei.
- Returnează DOAR itinerarul, fără text introductiv.
"""
                        itinerary = await get_proactive_response(
                            itinerary_instruction,
                            f"INPUT USER: {text}\n\nCONTEXT:\n{context_snapshot}",
                        )

                        if itinerary:
                            await save_day_plan(pool, today, text, itinerary)
                            await update.message.reply_text(
                                safe_markdown(itinerary), parse_mode="MarkdownV2"
                            )
                            await clear_state(pool)
                            # Mark plan as done for today
                            from db.queries.profile import update_user_profile

                            await update_user_profile(
                                pool, telegram_id, last_plan_date=today
                            )
                            return
                        else:
                            await update.message.reply_text(
                                "Nu am putut genera planul. Încearcă să-mi dai mai multe detalii."
                            )
                            await clear_state(pool)
                            return

                    except Exception as e:
                        print(f"Error handling day plan input: {e}")
                        traceback.print_exc()
                        err_msg = "Eroare la generarea planului"
                        await update.message.reply_text(err_msg)
                        await clear_state(pool)
                        return

            elif state["state_type"] == "awaiting_evening_response":
                import json as _json
                import textwrap
                from datetime import date as _date, timedelta
                from core.gemini import get_proactive_response
                from db.queries import journal as journal_queries
                from db.queries.day_plans import save_day_plan
                from db.queries.profile import update_user_profile
                from core.config import TELEGRAM_USER_ID as TG_UID

                profile = await get_user_profile(pool, telegram_id)
                today = _date.today()
                tomorrow = today + timedelta(days=1)

                # 1. Extract Reflection, Tomorrow Plan & Wake Time
                extraction_instruction = textwrap.dedent("""
                    Ești Lora, asistenta personală.
                    Userul a răspuns la întrebările de seară (ce a mers bine, ce vrea diferit, plan mâine, oră trezire).
                    Extrage:
                    - reflection_text: rezumat (ce a mers bine + ce ar face diferit) (max 3 propoziții)
                    - mood: great/good/neutral/bad/terrible (pe baza tonului)
                    - tomorrow_plan: ce a zis despre programul de mâine
                    - wake_time: ora de trezire menționată, format HH:MM (ex: "la 7" -> "07:00", "8 jumate" -> "08:30"). Dacă nu e menționată, returnează null.
                    Returnează EXCLUSIV JSON valid:
                    {"reflection_text": "...", "mood": "...", "tomorrow_plan": "...", "wake_time": "..."}
                """).strip()

                raw_extraction = await get_proactive_response(
                    extraction_instruction, text
                )

                try:
                    clean = raw_extraction.strip()
                    if clean.startswith("```"):
                        clean = (
                            clean.split("```")[1].lstrip("json").strip().rstrip("```")
                        )
                    extracted = _json.loads(clean)
                    reflection_text = extracted.get("reflection_text", text[:500])
                    mood = extracted.get("mood", "neutral")
                    tomorrow_plan = extracted.get("tomorrow_plan", "")
                    wake_time = extracted.get("wake_time")
                except Exception:
                    reflection_text = text[:500]
                    mood = "neutral"
                    tomorrow_plan = ""
                    wake_time = None

                # 2. Save Journal Entry
                await journal_queries.save_journal_entry(
                    pool, today, reflection_text, mood, tomorrow_plan
                )

                # 3. Generate Tomorrow's Itinerary
                context_snapshot = await build_context(pool, text)

                itinerary_instruction = """
                    Generează un itinerar structurat pe ore pentru MÂINE.
                    Bazează-te pe:
                    1. Planul menționat de user (tomorrow_plan).
                    2. Tasks pending și evenimente din calendar (vezi context).
                    3. Ora de trezire (wake_time).
                    
                    Format:
                    *Mâine:*
                    09:00 — [activitate]
                    11:00 — [activitate]
                    ...
                    
                    Reguli:
                    - Fii realist și echilibrat.
                    - Doar orele și activitățile, maxim 6 sloturi.
                    - Ton cald, Romglish permis.
                    - Returnează DOAR itinerarul.
                """

                itinerary = await get_proactive_response(
                    itinerary_instruction,
                    f" tomorrow_plan: {tomorrow_plan}\n wake_time: {wake_time}\n\nCONTEXT:\n{context_snapshot}",
                )

                if itinerary:
                    await save_day_plan(
                        pool, tomorrow, tomorrow_plan, itinerary, wake_time
                    )

                await clear_state(pool)
                await update_user_profile(pool, TG_UID, last_journal_date=today)

                reply = f"✅ Jurnal salvat\\.\n\n{safe_markdown(itinerary or 'Noapte bună!')}\n\nNoapte bună\\. 🌙"
                await update.message.reply_text(reply, parse_mode="MarkdownV2")
                return

            elif state["state_type"] == "awaiting_task_input":
                from modules.tasks import handle_task_intent
                from core.state import clear_state

                # Try to extract project_id from state extra
                project_id = state.get("extra")
                # We can call handle_task_intent with "add_task"
                # But we need Gemini to parse the description, or we just use the raw text.
                # Let's let it fall through to Gemini BUT with a hint.
                # Actually, the most robust way is to just clear state and let Gemini handle it naturally.
                # BUT if we have a project_id, we MUST pass it.
                if project_id:
                    # Forced add to project
                    data = {"title": text, "project_id": project_id}
                    reply, markup = await handle_task_intent(pool, "add_task", data)
                    await clear_state(pool)
                    await update.message.reply_text(
                        reply, parse_mode="MarkdownV2", reply_markup=markup
                    )
                    return
                await clear_state(pool)
                # Fall through to Gemini

            elif state["state_type"] == "awaiting_project_input":
                from db.queries.projects import add_project
                from core.state import clear_state
                from modules.tasks import get_projects_list_view

                # Check if text contains keywords for other modules - if so, clear state and let Gemini handle it
                lower_text = text.lower()
                other_module_keywords = [
                    "adauga carte",
                    "carte",
                    "book",
                    "reading",
                    "citit",
                    "adauga task",
                    "task",
                    "todo",
                    "workout",
                    "antrenament",
                    "exercitiu",
                    "habit",
                    "obicei",
                    "focus",
                    "pomodoro",
                    "goal",
                    "obiectiv",
                    "skill",
                    "abilitate",
                    "health",
                    "somn",
                    "apa",
                    "greutate",
                    "finance",
                    "cheltuiala",
                    "venit",
                    "mood",
                    "dispozitie",
                ]
                if any(kw in lower_text for kw in other_module_keywords):
                    await clear_state(pool)
                    print(
                        f"🔄 STATE CLEARED: detected other module keyword in '{text}'"
                    )
                    # Fall through to Gemini
                else:
                    # Simple parsing: first line name, rest description
                    lines = text.split("\n")
                    name = lines[0].strip()
                    desc = "\n".join(lines[1:]).strip() if len(lines) > 1 else None

                    await add_project(pool, name, desc)
                    await clear_state(pool)
                    await update.message.reply_text(
                        f"📂 Proiect creat: *{escape_md(name)}*",
                        parse_mode="MarkdownV2",
                    )
                    # Show projects list again
                    text_out, markup = await get_projects_list_view(pool)
                    await update.message.reply_text(
                        text_out, parse_mode="MarkdownV2", reply_markup=markup
                    )
                    return

            elif state["state_type"] == "awaiting_project_edit":
                from modules.tasks import get_project_tasks_view
                from db.queries.projects import update_project

                project_id = state.get("item_id")
                if not project_id:
                    await clear_state(pool)
                    await update.message.reply_text("Eroare: nu am găsit proiectul.")
                    return

                if text.lower() == "delete":
                    from db.queries.projects import delete_project

                    await delete_project(pool, project_id)
                    await clear_state(pool)
                    text_out, markup = await get_projects_list_view(pool)
                    await update.message.reply_text(
                        f"🗑️ Proiect șters\\.\n\n{text_out}",
                        parse_mode="MarkdownV2",
                        reply_markup=markup,
                    )
                    return

                await update_project(pool, project_id, description=text)
                await clear_state(pool)
                text_out, markup = await get_project_tasks_view(pool, project_id)
                await update.message.reply_text(
                    f"✅ Descriere actualizată\\.\n\n{text_out}",
                    parse_mode="MarkdownV2",
                    reply_markup=markup,
                )
                return

            elif state["state_type"] == "awaiting_event_note":
                from datetime import datetime

                event_id = state.get("item_id")
                if event_id and text:
                    await update.message.reply_text("Notă adăugată pentru eveniment 📝")
                await clear_state(pool)
                return

            elif state["state_type"] in [
                "awaiting_health_input",
                "awaiting_finance_input",
                "awaiting_workout_input",
            ]:
                if state["module"] == "health":
                    from modules.health import handle_health_message

                    await handle_health_message(update, pool, state, text)
                elif state["module"] == "finance":
                    from modules.finance import handle_finance_message

                    await handle_finance_message(update, pool, state, text)
                elif state["module"] == "workout":
                    from modules.workout import handle_workout_message
                    await handle_workout_message(update, pool, state, text)

                # Fall through to Gemini if not returned by handlers
                await clear_state(pool)


        # 4. Try regex parser first for simple add_task / add_event patterns
        intent_response = None
        low_text = text.lower()

        # Try task patterns
        if any(
            low_text.startswith(p) and "task" in low_text
            for p in ["adaug", "add", "create"]
        ):
            from modules.tasks import parse_add_task_text

            parsed = parse_add_task_text(text)
            if parsed and parsed.get("title"):
                intent_response = {
                    "intent": "add_task",
                    "module": "tasks",
                    "data": parsed,
                    "reply": "",
                    "needs_confirmation": False,
                }
                print(f"🔧 TASK REGEX: {parsed}")

        # Try event patterns
        elif any(
            (
                low_text.startswith(p)
                and ("event" in low_text or "eveniment" in low_text)
            )
            for p in ["adaug", "add", "create"]
        ):
            from modules.events import parse_add_event_text

            parsed = parse_add_event_text(text)
            if parsed and parsed.get("title"):
                intent_response = {
                    "intent": "add_event",
                    "module": "events",
                    "data": parsed,
                    "reply": "",
                    "needs_confirmation": False,
                }
                print(f"🔧 EVENT REGEX: {parsed}")

        # Try habit shortcut patterns (bifat X, done X, check X)
        elif any(
            low_text.startswith(p)
            for p in ["bifat ", "done ", "check ", "facut ", "făcut ", "gata "]
        ):
            from modules.skills import handle_skill_intent

            habit_name = None
            for prefix in [
                "bifat ",
                "bifat:",
                "done ",
                "done:",
                "check ",
                "check:",
                "facut ",
                "făcut ",
                "gata ",
            ]:
                if low_text.startswith(prefix):
                    habit_name = text[len(prefix) :].strip()
                    break

            if habit_name:
                reply, _ = await handle_skill_intent(
                    pool, "log_habit", {"name": habit_name, "value": 1}
                )
                await update.message.reply_text(reply, parse_mode="MarkdownV2")
                return

        # Try meal logging patterns
        elif any(
            w in low_text
            for w in [
                "mancat",
                "mâncat",
                "masa",
                "mic dejun",
                "pranz",
                "prânz",
                "cina",
                "cină",
                "gustare",
                "snack",
            ]
        ):
            from modules.nutrition import parse_meal_text

            parsed = parse_meal_text(text)
            if parsed and parsed.get("description"):
                intent_response = {
                    "intent": "meal_log",
                    "module": "nutrition",
                    "data": parsed,
                    "reply": "",
                    "needs_confirmation": False,
                }
                print(f"🔧 MEAL REGEX: {parsed}")

        # Try reminder patterns (remintește-mi, uită-mă, etc.)
        elif any(
            w in low_text
            for w in [
                "remintește-mi",
                "uită-mă",
                "uitamă",
                "amintește-mi",
                "reapă-mă",
                "reapămă",
                "să mă reapă",
                "setează reminder",
                "adu-mi aminte",
                "adumă aminte",
                "aminteste-mi",
            ]
        ):
            from modules.events import parse_reminder_text

            parsed = parse_reminder_text(text)
            if parsed and parsed.get("title"):
                intent_response = {
                    "intent": "add_reminder",
                    "module": "events",
                    "data": parsed,
                    "reply": "",
                    "needs_confirmation": False,
                }
                print(f"🔧 REMINDER REGEX: {parsed}")

            # escape special markdown chars in reply to avoid BadRequest
            # (moved to final handler)

        # Try finance logging patterns
        elif any(
            w in low_text
            for w in [
                "ron",
                "lei",
                "cheltuit",
                "am dat",
                "platit",
                "pe ",
                "expense",
                "ban",
            ]
        ):
            import re

            amount_match = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(",", "."))
            if amount_match:
                amount = float(amount_match.group(1).replace(",", "."))

                category = "altele"
                if any(
                    w in low_text
                    for w in ["mancare", "mâncare", "restaurant", "pizza", "shaorma"]
                ):
                    category = "mâncare"
                elif any(
                    w in low_text for w in ["uber", "taxi", "benzin", "metrou", "bus"]
                ):
                    category = "transport"
                elif any(
                    w in low_text
                    for w in ["chirie", "internet", "curent", "gaz", "utilitat"]
                ):
                    category = "utilități"
                elif any(w in low_text for w in ["medicament", "doctor", "farmacie"]):
                    category = "sănătate"
                elif any(w in low_text for w in ["haine", "magazin", "amazon"]):
                    category = "shopping"
                elif any(w in low_text for w in ["cinema", "bar", "concert"]):
                    category = "distracție"

                tx_type = (
                    "income"
                    if any(w in low_text for w in ["venit", "salariu", "am primit"])
                    else "expense"
                )

                intent_response = {
                    "intent": "finance_log",
                    "module": "finance",
                    "data": {
                        "amount": amount,
                        "category": category,
                        "type": tx_type,
                        "description": text,
                    },
                    "reply": "",
                    "needs_confirmation": False,
                }
                print(f"🔧 FINANCE REGEX: amount={amount}, category={category}")

        # 5. Fall back to Gemini if regex didn't match
        if not intent_response:
            print("⏳ BUILDING CONTEXT (Lazy Load)...", flush=True)
            context_snapshot = await build_context(pool, text)
            profile = await get_user_profile(pool, telegram_id)

            intent_response = await get_gemini_response(
                pool,
                user_message=text,
                user_name=profile.get("name", "User"),
                tone=profile.get("tone", "warm"),
                context_snapshot=context_snapshot,
                history=history,
                personal_notes=profile.get("personal_notes") or "",
            )
        else:
            # For regex matches, we might still need the profile for trigger_morning_briefing
            # but we can load it only if that specific intent is found later.
            # For now, let's keep it minimal.
            pass
        print(
            f"🧠 GEMINI: Intent={intent_response.get('intent')}, Module={intent_response.get('module')}, Data={intent_response.get('data')}"
        )

        # Special handling for morning briefing - call directly with application
        if intent_response.get("intent") == "trigger_morning_briefing":
            from scheduler.jobs import send_morning_briefing
            from core.config import TELEGRAM_USER_ID as TG_UID
            import db.queries.profile as profile_queries
            from datetime import date as _date

            today = _date.today()
            profile = await profile_queries.get_user_profile(pool, TG_UID)
            if profile.get("last_briefing_date") == today:
                await update.message.reply_text(
                    "Deja ți\\-am trimis briefing\\-ul de dimineață\\. O zi productivă\\! ☀️",
                    parse_mode="MarkdownV2",
                )
                return

            await update.message.reply_text(
                "Preg\\ătesc briefing\\-ul de dimineață\\. ☕", parse_mode="MarkdownV2"
            )
            try:
                await send_morning_briefing(context.application, pool)
            except Exception as e:
                import traceback

                print(f"ERROR in morning briefing: {e}", flush=True)
                traceback.print_exc()
                await update.message.reply_text(
                    f"❌ Eroare la briefing\\: {str(e)[:200]}", parse_mode="MarkdownV2"
                )
            return

        # 5. Route intent and get final reply + keyboard
        intent_response["_user_message"] = text
        final_reply, reply_markup = await route_intent(
            pool, intent_response, bot=context.bot
        )
        print(f"📡 ROUTER: Reply length={len(final_reply) if final_reply else 0}")

        if final_reply is None:
            return

        # 6. Save assistant reply to conversations
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO conversations (role, content) VALUES ($1, $2)",
                "assistant",
                final_reply,
            )

        # 7. Send to user
        chunks = split_message(final_reply)
        for i, chunk in enumerate(chunks):
            current_markup = reply_markup if i == len(chunks) - 1 else None
            try:
                print(f"📤 SENDING chunk {i+1}/{len(chunks)}: {repr(chunk[:50])}...", flush=True)
                await update.message.reply_text(
                    safe_markdown(chunk),
                    parse_mode="MarkdownV2",
                    reply_markup=current_markup,
                )

            except Exception as e:
                print(f"⚠️ MarkdownV2 FAILED for chunk {i+1}, falling back to plain text: {e}", flush=True)
                try:
                    await update.message.reply_text(chunk, reply_markup=current_markup)
                except Exception as e2:
                    print(f"🚨 Plain text fallback ALSO FAILED: {e2}", flush=True)
                    raise e2

    except Exception as e:
        import logging
        import traceback

        logger = logging.getLogger(__name__)
        logger.error(f"ERROR in message_handler: {e}\n{traceback.format_exc()}")
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ceva n-a mers. Încearcă din nou.",
            )
        except Exception:
            pass


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    if not await security_check(update):
        return

    try:
        query = update.callback_query
        data = query.data
        print(
            f"DEBUG: CALLBACK RECEIVED: data={data} from user={update.effective_user.id}",
            flush=True,
        )

        if data.startswith("memory:"):
            from modules.memory import handle_memory_callback

            await handle_memory_callback(query, pool, data)
            return

        if data.startswith("vision:"):
            from core.vision import handle_vision_callback

            await handle_vision_callback(query, pool, data)
            return

        if data.startswith("goals_"):
            from modules.goals import handle_goals_callback

            await handle_goals_callback(query, pool, data)
            return

        if data.startswith("skills_"):
            from modules.skills import handle_skills_callback

            await handle_skills_callback(update, context, pool)
            return

        if data.startswith("reading_"):
            from modules.reading import handle_reading_callback

            await handle_reading_callback(query, pool, data)
            return

        if data.startswith("workout_"):
            from modules.workout import handle_workout_callback

            await handle_workout_callback(query, pool, data)
            return

        if data.startswith("tasks:") or data.startswith("projects:"):
            from modules.tasks import handle_tasks_callback

            await handle_tasks_callback(query, pool, data)
            return

        if data.startswith("health:"):
            from modules.health import handle_health_callback

            await handle_health_callback(query, pool, data)
            return

        if data.startswith("finance_"):
            import io
            from modules.finance import handle_finance_intent

            if data == "finance_chart":
                result, _ = await handle_finance_intent(pool, "finance_chart", {})
                if isinstance(result, (bytes, io.BytesIO)):
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=result,
                        caption="Finance Trends 📉 (ultimele 30 zile)",
                    )
                    await query.answer()
                else:
                    await query.answer(result)
                    await query.message.reply_text(result)
                return

            elif data == "finance_summary":
                text, markup = await handle_finance_intent(pool, "finance_summary", {})
                await query.edit_message_text(
                    text, parse_mode="MarkdownV2", reply_markup=markup
                )
                await query.answer()
                return

            elif data == "finance_add_expense":
                from core.state import set_state

                await set_state(
                    pool,
                    "awaiting_finance_input",
                    "finance",
                    "finance_log",
                    None,
                    {"type": "expense"},
                )
                prompt = "💸 *Ce cheltuială ai făcut?*\n_\\(ex: 50 RON cafea, taxi 30lei, mâncare 100\\)_"
                await query.edit_message_text(prompt, parse_mode="MarkdownV2")
                await query.answer()
                return

            elif data == "finance_add_income":
                from core.state import set_state

                await set_state(
                    pool,
                    "awaiting_finance_input",
                    "finance",
                    "finance_log",
                    None,
                    {"type": "income"},
                )
                prompt = "💰 *Ce venit ai primit?*\n_\\(ex: salariu 5000, bonus 200, vânzare olx 50\\)_"
                await query.edit_message_text(prompt, parse_mode="MarkdownV2")
                await query.answer()
                return

            elif data == "finance_stats":
                await query.answer(
                    "Statisticile detaliate sunt în curs de implementare... 🚧"
                )
                return

            elif data == "finance_categories":
                text, markup = await handle_finance_intent(pool, "list_categories", {})
                await query.edit_message_text(
                    text, parse_mode="MarkdownV2", reply_markup=markup
                )
                await query.answer()
                return

            elif data == "finance_add_category":
                from core.state import set_state

                await set_state(
                    pool,
                    "awaiting_finance_input",
                    "finance",
                    "add_category",
                    None,
                )
                prompt = "💰 *Nume pentru categorie nouă:*\n_(ex: cafea, combustibil, abonamente)_"
                await query.edit_message_text(prompt, parse_mode="MarkdownV2")
                await query.answer()
                return

            return

        # Event Reminders
        if data.startswith("event_reminder:"):
            parts = data.split(":")
            if len(parts) >= 3:
                event_id = int(parts[1])
                minutes = int(parts[2])
                from db.queries.events import update_event_reminder

                await update_event_reminder(pool, event_id, minutes)

                if minutes == 0:
                    msg = "Reminder dezactivat 🔕"
                elif minutes == 1440:
                    msg = "Reminder setat la 1 zi 📅"
                else:
                    msg = f"Reminder setat la {minutes} minute 🔔"

                await query.answer(msg)
                await query.edit_message_text(msg)
            return

        if data.startswith("event_reminder_ack:"):
            event_id = data.split(":")[1]
            await query.answer("Ok 👍")
            await query.edit_message_text("Reminder confirmat 👍")
            return

        if data.startswith("event_note:"):
            event_id = data.split(":")[1]
            from core.state import set_state

            await set_state(
                pool, "awaiting_event_note", "events", "add_note", int(event_id)
            )
            await query.answer()
            await query.edit_message_text(
                "Ce note vrei să adaugi pentru acest eveniment?"
            )
            return

        if data == "event_day_ack":
            await query.answer("Ok 👍")
            await query.edit_message_text("Reminder 1 zi confirmat 👍")
            return

        # Tasks and projects are handled by handle_tasks_callback (set above)
        # Generic cancel action
        if data in ["cancel", "delete_cancelled"]:
            from core.state import clear_state

            await clear_state(pool)
            await query.answer("Cancelled.")
            await query.edit_message_text("Action cancelled\\.")

        await query.answer()
    except Exception as e:
        print(f"ERROR in callback_handler: {e}")
        traceback.print_exc()


async def show_uni_dashboard(message_or_query, pool, send_new: bool = False):
    """Renders the /uni academic dashboard."""
    from db.queries.schedule import get_current_week_type
    from db.queries.university import get_general_average, get_attendance_warnings
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from datetime import date

    week_type = await get_current_week_type(pool)
    week_label = "impară" if week_type == "odd" else "pară"

    config = await pool.fetchrow(
        "SELECT semester_start FROM semester_config ORDER BY id DESC LIMIT 1"
    )
    week_num = 1
    if config:
        delta = (date.today() - config["semester_start"]).days
        week_num = delta // 7 + 1

    avg = await get_general_average(pool)
    warnings = await get_attendance_warnings(pool)

    avg_str = f"*{avg}*" if avg else "—"
    warn_str = f"⚠️ {len(warnings)} materii sub minim" if warnings else "✅ Toate ok"

    text = (
        f"🎓 *Viața Academică*\n\n"
        f"📅 Semestrul II — săptămâna *{week_num}* \\({escape_md(week_label)}\\)\n"
        f"📊 Medie generală: {avg_str}\n"
        f"👁 Prezențe: {escape_md(warn_str)}\n"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📊 Overview", callback_data="uni:overview"),
                InlineKeyboardButton("📚 Materii", callback_data="uni:subjects"),
            ],
            [
                InlineKeyboardButton("📅 Orar", callback_data="uni:schedule"),
                InlineKeyboardButton("🎓 Examene", callback_data="uni:exams"),
            ],
            [InlineKeyboardButton("📝 Note & Prezențe", callback_data="uni:grades")],
            [
                InlineKeyboardButton("🔍 Analiză", callback_data="uni:analysis"),
                InlineKeyboardButton("📥 Import", callback_data="uni:import"),
            ],
        ]
    )

    if send_new:
        await message_or_query.reply_text(
            text, parse_mode="MarkdownV2", reply_markup=keyboard
        )
    else:
        await message_or_query.edit_message_text(
            text, parse_mode="MarkdownV2", reply_markup=keyboard
        )


async def handle_uni_callback(query, pool, data: str):
    """Routes all uni: callback queries."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    parts = data.split(":")
    section = parts[1] if len(parts) > 1 else ""
    action = parts[2] if len(parts) > 2 else ""
    item_id = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None

    await query.answer()

    back_btn = InlineKeyboardButton("← Înapoi", callback_data="uni:dashboard")

    # ━━━ DASHBOARD ━━━
    if section == "dashboard":
        await show_uni_dashboard(query, pool, send_new=False)
        return

    # ━━━ OVERVIEW ━━━
    elif section == "overview":
        from db.queries.schedule import get_today_schedule, get_current_week_type
        from db.queries.university import list_subjects, get_upcoming_exams
        from datetime import date

        week_type = await get_current_week_type(pool)
        week_label = "impară" if week_type == "odd" else "pară"
        config = await pool.fetchrow(
            "SELECT semester_start FROM semester_config ORDER BY id DESC LIMIT 1"
        )
        week_num = 1
        if config:
            delta = (date.today() - config["semester_start"]).days
            week_num = delta // 7 + 1

        classes_today = await get_today_schedule(pool)
        subjects = await list_subjects(pool)
        exams = await get_upcoming_exams(pool, days=14)

        lines = ["📊 *Overview Academic*\n"]
        lines.append(f"📅 Săptămâna *{week_num}* \\({escape_md(week_label)}\\)")
        lines.append(f"📚 Materii active: *{len(subjects)}*\n")

        if classes_today:
            lines.append("*Azi la facultate:*")
            for c in classes_today:
                start = c["start_time"].strftime("%H:%M")
                icon = "📖" if c["class_type"] == "curs" else "✏️"
                room = f" · {escape_md(c['room'])}" if c.get("room") else ""
                lines.append(f"{icon} `{start}` {escape_md(c['subject_name'])}{room}")
        else:
            lines.append("✅ Nu ai cursuri azi\\.")

        if exams:
            lines.append("\n*Examene în 14 zile:*")
            for e in exams[:3]:
                lines.append(
                    f"• {escape_md(e['exam_date'].strftime('%d %b'))} — {escape_md(e['subject_name'])}"
                )

        keyboard = InlineKeyboardMarkup([[back_btn]])
        await query.edit_message_text(
            "\n".join(lines), parse_mode="MarkdownV2", reply_markup=keyboard
        )

    # ━━━ MATERII ━━━
    elif section == "subjects":
        if not action:
            from db.queries.university import list_subjects

            subjects = await list_subjects(pool)

            lines = ["📚 *Materii*\n"]
            for s in subjects:
                name = escape_md(s["name"])
                attended = s.get("attended_count") or 0
                total = s.get("total_seminars") or s.get("total_logged") or 0
                avg = f" · medie *{s['avg_grade']}*" if s.get("avg_grade") else ""
                pres = f"Prezențe: {attended}/{total}" if total > 0 else "Prezențe: —"
                lines.append(f"• *{name}*{avg}\n  {escape_md(pres)}")

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "➕ Adaugă", callback_data="uni:subjects:add"
                        )
                    ],
                    [back_btn],
                ]
            )
            await query.edit_message_text(
                "\n".join(lines), parse_mode="MarkdownV2", reply_markup=keyboard
            )

        elif action == "add":
            from core.state import set_state

            await set_state(
                pool, "awaiting_uni_input", "university", "add_subject", None
            )
            keyboard = InlineKeyboardMarkup([[back_btn]])
            await query.edit_message_text(
                "📚 *Adaugă materie*\n\nScrie numele materiei:",
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )

        elif action == "delete" and item_id:
            subject = await pool.fetchrow(
                "SELECT * FROM subjects WHERE id = $1", item_id
            )
            if subject:
                await pool.execute(
                    "UPDATE subjects SET is_active = FALSE WHERE id = $1", item_id
                )
                await query.answer(f"{subject['name']} ștearsă.")
            await handle_uni_callback(query, pool, "uni:subjects")
            return

    # ━━━ ORAR ━━━
    elif section == "schedule":
        if not action:
            from db.queries.schedule import get_week_schedule, get_current_week_type

            week_schedule, days, week_type = await get_week_schedule(pool)
            week_label = "impară" if week_type == "odd" else "pară"

            lines = [f"📅 *Orar — săptămână {escape_md(week_label)}*\n"]
            for day_idx, day_name in days.items():
                classes = week_schedule.get(day_idx, [])
                if not classes:
                    continue
                lines.append(f"*{escape_md(day_name)}*")
                for c in classes:
                    start = c["start_time"].strftime("%H:%M")
                    icon = "📖" if c["class_type"] == "curs" else "✏️"
                    room = f" · {escape_md(c['room'])}" if c.get("room") else ""
                    lines.append(
                        f"  {icon} `{start}` {escape_md(c['subject_name'])}{room}"
                    )
                lines.append("")

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "➕ Adaugă oră", callback_data="uni:schedule:add"
                        )
                    ],
                    [back_btn],
                ]
            )
            await query.edit_message_text(
                "\n".join(lines), parse_mode="MarkdownV2", reply_markup=keyboard
            )

        elif action == "add":
            from core.state import set_state

            await set_state(
                pool, "awaiting_uni_input", "university", "add_schedule", None
            )
            keyboard = InlineKeyboardMarkup([[back_btn]])
            await query.edit_message_text(
                "📅 *Adaugă oră în orar*\n\n"
                "Scrie în format:\n"
                "`Zi, HH:MM\\-HH:MM, Materie, tip, sala, sapt`\n\n"
                "Exemplu: `Luni, 08:00\\-09:30, MRU, seminar, 208, odd`",
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )

    # ━━━ EXAMENE ━━━
    elif section == "exams":
        if not action:
            from db.queries.university import get_upcoming_exams

            exams = await get_upcoming_exams(pool, days=90)

            if not exams:
                text_msg = "🎓 *Examene*\n\nNiciun examen înregistrat\\."
            else:
                lines = ["🎓 *Examene upcoming*\n"]
                for e in exams:
                    date_str = escape_md(e["exam_date"].strftime("%d %b %Y"))
                    subject = escape_md(e["subject_name"])
                    type_str = escape_md(e.get("exam_type", "examen"))
                    loc = f" · {escape_md(e['location'])}" if e.get("location") else ""
                    lines.append(f"• *{date_str}* — {subject} \\({type_str}\\){loc}")
                text_msg = "\n".join(lines)

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "➕ Adaugă examen", callback_data="uni:exams:add"
                        )
                    ],
                    [back_btn],
                ]
            )
            await query.edit_message_text(
                text_msg, parse_mode="MarkdownV2", reply_markup=keyboard
            )

        elif action == "add":
            from core.state import set_state

            await set_state(pool, "awaiting_uni_input", "university", "add_exam", None)
            keyboard = InlineKeyboardMarkup([[back_btn]])
            await query.edit_message_text(
                "🎓 *Adaugă examen*\n\n"
                "Scrie în format:\n"
                "`Materie, YYYY\\-MM\\-DD, tip, sala`\n\n"
                "Exemplu: `Statistică, 2026\\-06\\-15, examen, A2`",
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )

    # ━━━ NOTE & PREZENȚE ━━━
    elif section == "grades":
        if not action:
            from db.queries.university import list_subjects

            subjects = await list_subjects(pool)

            lines = ["📝 *Note \\& Prezențe*\n"]
            for s in subjects:
                name = escape_md(s["name"])

                # Note: — (or grade)
                avg_val = s.get("avg_grade")
                avg_str = f"*{avg_val}*" if avg_val else "—"

                # Prezențe: 3/7 (or —)
                attended = s.get("attended_count") or 0
                total = s.get("total_seminars") or 0
                pres_str = f"{attended}/{total}" if total > 0 else "—"

                lines.append(
                    f"*{name}*\nNote: {avg_str}\nPrezențe: {escape_md(pres_str)}"
                )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "➕ Notă", callback_data="uni:grades:add_grade"
                        ),
                        InlineKeyboardButton(
                            "➕ Prezență", callback_data="uni:grades:add_attendance"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "✏️ Edit prezență",
                            callback_data="uni:grades:edit_attendance",
                        ),
                        InlineKeyboardButton(
                            "🗑 Șterge notă", callback_data="uni:grades:delete_grade"
                        ),
                    ],
                    [back_btn],
                ]
            )
            await query.edit_message_text(
                "\n".join(lines), parse_mode="MarkdownV2", reply_markup=keyboard
            )

        elif action == "add_grade":
            from core.state import set_state

            await set_state(pool, "awaiting_uni_input", "university", "add_grade", None)
            keyboard = InlineKeyboardMarkup([[back_btn]])
            await query.edit_message_text(
                "📝 *Adaugă notă*\n\nFormat: `Materie, notă, tip`\nExemplu: `Statistică, 8\\.5, partial`",
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )

        elif action == "add_attendance":
            from core.state import set_state

            await set_state(
                pool, "awaiting_uni_input", "university", "add_attendance", None
            )
            keyboard = InlineKeyboardMarkup([[back_btn]])
            await query.edit_message_text(
                "📝 *Adaugă prezență*\n\nFormat: `Materie, prezent/absent, YYYY\\-MM\\-DD`\nExemplu: `MRU, prezent, 2026\\-03\\-23`",
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )

        elif action == "edit_attendance":
            from core.state import set_state

            await set_state(
                pool, "awaiting_uni_input", "university", "edit_attendance", None
            )
            keyboard = InlineKeyboardMarkup([[back_btn]])
            await query.edit_message_text(
                "✏️ *Editează prezență*\n\nFormat: `Materie, YYYY\\-MM\\-DD, prezent/absent`\nExemplu: `MRU, 2026\\-03\\-23, absent`",
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )

        elif action == "delete_grade":
            from core.state import set_state

            await set_state(
                pool, "awaiting_uni_input", "university", "delete_grade", None
            )
            keyboard = InlineKeyboardMarkup([[back_btn]])
            await query.edit_message_text(
                "🗑 *Șterge notă*\n\nFormat: `Materie, tip`\nExemplu: `Statistică, partial`",
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )

    # ━━━ ANALIZĂ GEMINI ━━━
    elif section == "analysis":
        from db.queries.university import list_subjects, get_upcoming_exams
        from db.queries.schedule import get_current_week_type
        from datetime import date

        subjects = await list_subjects(pool)
        exams = await get_upcoming_exams(pool, days=60)
        config = await pool.fetchrow(
            "SELECT semester_start FROM semester_config ORDER BY id DESC LIMIT 1"
        )
        week_num = 1
        if config:
            delta = (date.today() - config["semester_start"]).days
            week_num = delta // 7 + 1

        data_ctx = f"""
Săptămâna curentă: {week_num}/14
Materii și situație:
{chr(10).join([f"- {s['name']}: medie {s['avg_grade'] or 'N/A'}, prezențe {s.get('attended_count', 0)}/{s.get('total_seminars', 0)}" for s in subjects])}

Examene upcoming:
{chr(10).join([f"- {e['subject_name']}: {e['exam_date']}" for e in exams]) or "Niciun examen înregistrat"}
"""

        from core.gemini import get_proactive_response

        instruction = """
Ești Lora. Analizează situația academică a lui Robu și oferă o analiză concisă.

Structură:
📊 *Analiză Academică*

*Situație generală:* [1-2 propoziții]
*Riscuri:* [materii cu prezențe scăzute sau fără note]
*Prioritate:* [ce trebuie să facă în săptămânile rămase]

MAX 150 cuvinte. Ton direct, fără laudă.
Dacă nu sunt suficiente date: spune direct.
"""

        result = await get_proactive_response(instruction, data_ctx)

        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔄 Regenerează", callback_data="uni:analysis")],
                [back_btn],
            ]
        )
        await query.edit_message_text(
            safe_markdown(result)
            if result
            else "Nu sunt suficiente date pentru analiză\\.",
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )

    # ━━━ IMPORT ━━━
    elif section == "import":
        if not action:
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📸 Import orar din poză",
                            callback_data="uni:import:schedule_photo",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📄 Structură din PDF",
                            callback_data="uni:import:structure_pdf",
                        )
                    ],
                    [back_btn],
                ]
            )
            await query.edit_message_text(
                "📥 *Import*\n\nAlege ce vrei să importezi:",
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )

        elif action == "schedule_photo":
            from core.state import set_state

            await set_state(
                pool, "awaiting_uni_input", "university", "import_schedule_photo", None
            )
            keyboard = InlineKeyboardMarkup([[back_btn]])
            await query.edit_message_text(
                "📸 *Import orar din poză*\n\nTrimite o poză cu orarul tău\\.\nLora va extrage automat cursurile și orele\\.",
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )

        elif action == "structure_pdf":
            from core.state import set_state

            await set_state(
                pool, "awaiting_uni_input", "university", "import_structure_pdf", None
            )
            keyboard = InlineKeyboardMarkup([[back_btn]])
            await query.edit_message_text(
                "📄 *Import structură academică*\n\nTrimite PDF\\-ul cu structura anului universitar\\.\nLora va extrage perioadele \\(activitate didactică, vacanță, sesiune\\)\\.",
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )


async def goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TELEGRAM_USER_ID:
        return
    pool = context.bot_data["pool"]
    try:
        from modules.goals import get_goals_dashboard

        msg, markup = await get_goals_dashboard(pool)
        await update.message.reply_text(
            msg, parse_mode="MarkdownV2", reply_markup=markup
        )
    except Exception as e:
        print(f"Error in goals_command: {e}")
        await update.message.reply_text("❌ Eroare la încărcarea dashboard-ului Goals.")


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /health command — opens health dashboard."""
    pool = context.bot_data.get("pool")
    if not await security_check(update):
        return

    from modules.health import handle_health_intent

    text, markup = await handle_health_intent(
        pool, "health_summary", {}, bot=context.bot
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def finance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /finance command — opens finance dashboard."""
    pool = context.bot_data.get("pool")
    if not await security_check(update):
        return

    from modules.finance import handle_finance_intent

    text, markup = await handle_finance_intent(pool, "finance_summary", {})
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /tasks command — opens tasks dashboard."""
    pool = context.bot_data.get("pool")
    if not await security_check(update):
        return

    from modules.tasks import get_tasks_dashboard

    text, markup = await get_tasks_dashboard(pool)
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /projects command — opens projects dashboard."""
    pool = context.bot_data.get("pool")
    if not await security_check(update):
        return

    from modules.projects import get_projects_dashboard

    text, markup = await get_projects_dashboard(pool)
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def reading_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /reading command — opens reading dashboard."""
    pool = context.bot_data.get("pool")
    if not await security_check(update):
        return

    from modules.reading import get_reading_dashboard

    text, markup = await get_reading_dashboard(pool)
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)

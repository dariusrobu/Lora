from telegram import Update
from telegram.ext import ContextTypes
from core.config import TELEGRAM_USER_ID
from bot.onboarding import start_onboarding, handle_onboarding, handle_onboarding_callback
from db.queries.profile import is_onboarding_complete, get_user_profile
from bot.formatter import escape_md, split_message
from core.context import build_context
from core.gemini import get_gemini_response
from core.router import route_intent
import traceback

async def security_check(update: Update) -> bool:
    """Rejects non-whitelisted user IDs silently."""
    if not update.effective_user:
        return False
    
    is_authorized = update.effective_user.id == TELEGRAM_USER_ID
    if not is_authorized:
        print(f"❌ UNAUTHORIZED: Access attempt by ID {update.effective_user.id} (Expected {TELEGRAM_USER_ID})")
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
            await update.message.reply_text("Nu am putut înțelege mesajul vocal — încearcă din nou 🎙")
            return

        # Pass transcribed text to the existing message handler logic
        print(f"🎙 VOICE TRANSCRIBED: {repr(text)}")
        return await message_handler(update, context, pool, text=text)

    except Exception as e:
        print(f"ERROR in voice_handler: {e}")
        traceback.print_exc()

async def habitstreaks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates and sends the visual habit streaks heatmap."""
    from modules.habits import generate_habit_heatmap
    pool = context.bot_data.get("pool")
    print(f"DEBUG habitstreaks: pool={pool}", flush=True)
    if not pool:
        await update.message.reply_text("Database pool error.")
        return

    await update.message.reply_text("📊 Generăm habit streaks... un moment!")
    try:
        result, _ = await generate_habit_heatmap(pool)
        print(f"DEBUG habitstreaks: result type={type(result)}", flush=True)
        if isinstance(result, bytes):
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=result,
                caption="Habit Streaks 🔥",
            )
        else:
            await update.message.reply_text(result)
    except Exception as e:
        print(f"Habit streaks command error: {e}", flush=True)
        await update.message.reply_text(f"❌ Eroare: {e}")

async def focus_command(update, context):
    pool = context.bot_data.get("pool")
    text = update.message.text
    
    parts = text.split()
    duration = 25
    if len(parts) > 1 and parts[1].isdigit():
        duration = int(parts[1])
    
    from modules.focus import handle_focus_intent
    reply, markup = await handle_focus_intent(
        pool, "focus_start", 
        {"duration_min": duration}, 
        bot=context.bot
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

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool, text=None):
    # Log EVERY message before the security check
    user_id = update.effective_user.id if update.effective_user else "Unknown"
    
    # Use provided text or fallback to message text
    if text is None and update.message:
        text = update.message.text
        
    print(f"📥 RECEIVED: Update ID {update.update_id} from user_id {user_id} - Text: {repr(text)}")
    
    if not await security_check(update):
        return

    try:
        telegram_id = update.effective_user.id
        
        # Non-text message handling
        if not update.message or (not text and not update.message.voice):
            if update.message and (update.message.photo or update.message.video or update.message.sticker):
                await update.message.reply_text("I can only read text for now — what would you like to do?")
            return
        
        # Handle /reload command
        if text == "/reload":
            await update.message.reply_text("🔄 Reloading Lora... I'll be back in a second!")
            import os
            import sys
            from db.connection import close_pool
            await close_pool()
            os.execl(sys.executable, sys.executable, *sys.argv)
            return

        # Handle /podcast command
        if text == "/podcast":
            from scheduler.jobs import send_morning_briefing
            await update.message.reply_text("🎙️ Generăm podcast-ul tău personal... un moment!")

            from db.queries.profile import update_user_profile
            from core.config import TELEGRAM_USER_ID

            try:
                await update_user_profile(pool, TELEGRAM_USER_ID, last_briefing_date=None)
                await send_morning_briefing(context.application, pool)
            except Exception as e:
                print(f"Podcast manual trigger error: {e}", flush=True)
                await update.message.reply_text(f"❌ Scuze, a apărut o eroare la generarea podcast-ului: {e}")
            return

        # Handle /weeklyreview command
        if text == "/weeklyreview":
            from scheduler.jobs import send_weekly_review
            await update.message.reply_text("📊 Generăm review-ul tău săptămânal... un moment!")

            try:
                await send_weekly_review(context.application, pool)
            except Exception as e:
                print(f"Weekly review manual trigger error: {e}", flush=True)
                await update.message.reply_text(f"❌ Eroare la generarea review-ului: {e}")
            return

        # Handle /monthlyreview command
        if text == "/monthlyreview":
            from scheduler.jobs import send_monthly_review
            from db.queries.profile import update_user_profile
            await update.message.reply_text("📊 Generăm review-ul tău lunar... un moment!")

            try:
                # Reset last_monthly_review_date to None to allow manual trigger
                await update_user_profile(pool, TELEGRAM_USER_ID, last_monthly_review_date=None)
                await send_monthly_review(context.bot, pool)
            except Exception as e:
                print(f"Monthly review manual trigger error: {e}", flush=True)
                await update.message.reply_text(f"❌ Eroare la generarea review-ului lunar: {e}")
            return

        # Handle /habitstreaks command
        cmd = text.split()[0].split('@')[0].lower() if text else ""
        if cmd == "/habitstreaks":
            await habitstreaks_command(update, context)
            return

        # Handle /journal command
            
        # Handle /plan command
        if text == "/plan":
            from db.queries.profile import update_user_profile
            from core.config import TELEGRAM_USER_ID as TG_UID
            from core.state import set_state
            
            try:
                await update_user_profile(pool, TG_UID, last_plan_date=None)
                await update.message.reply_text("Cum vrei să-ți arate ziua azi? Spune-mi vocal sau în scris 🗓")
                await set_state(pool, "awaiting_day_plan_input", "day_plans", "generate", None)
            except Exception as e:
                print(f"Plan manual trigger error: {e}", flush=True)
                await update.message.reply_text(f"❌ Eroare la inițierea planului: {e}")
            return

        # 3.8 Health Chart Direct Bypass (to avoid Gemini misinterpretation)
        health_chart_triggers = ["grafic health", "grafic somn", "grafic apă", "grafic apa", "grafic greutate", "cum am dormit"]
        low_text = text.lower()
        if any(trigger in low_text for trigger in health_chart_triggers):
            intent_response = {
                "intent": "health_chart",
                "module": "health",
                "data": {"_original_reply": "Generăm graficul tău... 📊"},
                "reply": "Generăm graficul tău... 📊"
            }
            final_reply, reply_markup = await route_intent(pool, intent_response, bot=context.bot)
            if final_reply:
                # Save assistant reply to conversations
                async with pool.acquire() as conn:
                    await conn.execute("INSERT INTO conversations (role, content) VALUES ($1, $2)", "assistant", final_reply)
                await update.message.reply_text(final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup)
            return

        # 3.9 Habit Heatmap Direct Bypass (to avoid Gemini misinterpretation)
        habit_heatmap_triggers = ["habit heatmap", "habit streaks vizual", "heatmap habit", "streak vizual", "grafic habit", "heat map habit", "heat map habits"]
        if any(trigger in low_text for trigger in habit_heatmap_triggers):
            intent_response = {
                "intent": "habit_heatmap",
                "module": "habits",
                "data": {"_original_reply": "Generăm heatmap-ul tău... 🔥"},
                "reply": "Generăm heatmap-ul tău... 🔥"
            }
            final_reply, reply_markup = await route_intent(pool, intent_response, bot=context.bot)
            if final_reply:
                # Save assistant reply to conversations
                async with pool.acquire() as conn:
                    await conn.execute("INSERT INTO conversations (role, content) VALUES ($1, $2)", "assistant", final_reply)
                await update.message.reply_text(final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup)
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
            # 1. Get history (last 10 turns) BEFORE saving current message
            history_rows = await conn.fetch("SELECT role, content FROM conversations ORDER BY created_at DESC LIMIT 10")
            history = [{"role": r["role"], "content": r["content"]} for r in reversed(history_rows)]
            
            # 2. Save current user message to conversations
            await conn.execute("INSERT INTO conversations (role, content) VALUES ($1, $2)", "user", text)

        # Phase 8: State Check (Confirmations / Edits)
        from core.state import get_state, clear_state
        state = await get_state(pool)
        if state:
            print(f"🔄 STATE ACTIVE: {state['state_type']} for {state['module']}:{state['action']}", flush=True)
            if state['state_type'] == 'awaiting_confirmation':
                low_text = text.lower()
                if any(word in low_text for word in ['yes', 'yeah', 'do it', 'confirm', 'sure', 'da']):
                    data = {"id": state['item_id'], "confirmed": True}
                    intent = f"{state['action']}_confirmed"
                    intent_response = {
                        "intent": intent,
                        "module": state['module'],
                        "data": data,
                        "reply": "Confirmed. Working on it...",
                        "needs_confirmation": False
                    }
                    await clear_state(pool)
                    final_reply, reply_markup = await route_intent(pool, intent_response, bot=context.bot)
                    await update.message.reply_text(final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup)
                    return
                elif any(word in low_text for word in ['no', 'stop', 'cancel', 'don\'t', 'nu']):
                    await clear_state(pool)
                    await update.message.reply_text("Cancelled\\.")
                    return
                else:
                    await clear_state(pool)
            
            elif state['state_type'] == 'awaiting_focus_result':
                session_id = state.get('item_id')
                import db.queries.focus as focus_queries
                if session_id:
                    await focus_queries.complete_session(pool, session_id, text)
                await clear_state(pool)
                await update.message.reply_text("Notat\\. Sesiune salvată\\. 💪", parse_mode="MarkdownV2")
                return

            elif state['state_type'] == 'awaiting_edit_field':
                context_snapshot = await build_context(pool)
                profile = await get_user_profile(pool, telegram_id)
                edit_prompt = f"The user wants to edit an item. Module: {state['module']}, Item ID: {state['item_id']}. User input: {text}"

                intent_response = await get_gemini_response(
                    user_message=edit_prompt,
                    user_name=profile.get("name", "User"),
                    tone=profile.get("tone", "warm"),
                    context_snapshot=context_snapshot,
                    history=[],
                    personal_notes=f"ACTION: Extract the fields to change for item {state['item_id']} in module {state['module']}. Return intent='edit_{state['module'][:-1]}', data={{'id': {state['item_id']}, ...fields...}}"
                )

                await clear_state(pool)
                final_reply, reply_markup = await route_intent(pool, intent_response, bot=context.bot)
                await update.message.reply_text(final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup)
                return

            elif state['state_type'] == 'awaiting_day_plan_input':
                # If command, clear state and proceed
                if text.startswith('/'):
                    await clear_state(pool)
                else:
                    try:
                        from db.queries.day_plans import save_day_plan
                        from core.gemini import get_proactive_response
                        from bot.formatter import escape_md
                        from datetime import date as _date
                        
                        today = _date.today()
                        profile = await get_user_profile(pool, telegram_id)
                        context_snapshot = await build_context(pool)
                        
                        itinerary_instruction = f"""
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
                        itinerary = await get_proactive_response(itinerary_instruction, f"INPUT USER: {text}\n\nCONTEXT:\n{context_snapshot}")
                        
                        if itinerary:
                            await save_day_plan(pool, today, text, itinerary)
                            # Safe markdown for Telegram
                            from bot.formatter import safe_markdown
                            await update.message.reply_text(safe_markdown(itinerary), parse_mode="MarkdownV2")
                            await clear_state(pool)
                            # Mark plan as done for today
                            from db.queries.profile import update_user_profile
                            await update_user_profile(pool, telegram_id, last_plan_date=today)
                            return
                        else:
                            await update.message.reply_text("Nu am putut genera planul. Încearcă să-mi dai mai multe detalii.")
                            await clear_state(pool)
                            return
                            
                    except Exception as e:
                        print(f"Error handling day plan input: {e}")
                        traceback.print_exc()
                        await update.message.reply_text(f"❌ Eroare la generarea planului: {e}")
                        await clear_state(pool)
                        return

            elif state['state_type'] == 'awaiting_journal_response':
                import json as _json
                import textwrap
                from datetime import date as _date
                from core.gemini import get_proactive_response
                from db.queries import journal as journal_queries
                from db.queries.profile import update_user_profile
                from core.config import TELEGRAM_USER_ID as TG_UID

                profile = await get_user_profile(pool, telegram_id)
                today = _date.today()

                extraction_instruction = textwrap.dedent("""
                    Ești Lora, asistenta personală.
                    Userul tocmai a răspuns la întrebările din jurnalul de seară.
                    Extrage din răspunsul lor liber:
                    - reflection_text: un rezumat scurt al reflecției (max 3 propoziții)
                    - mood: una din: great / good / neutral / bad / terrible (pe baza tonului general)
                    - tomorrow_focus: lucrul cel mai important menționat pentru mâine (1 propoziție)
                    Returnează EXCLUSIV JSON valid, fără markdown:
                    {"reflection_text": "...", "mood": "...", "tomorrow_focus": "..."}
                """).strip()

                raw_extraction = await get_proactive_response(extraction_instruction, text)
                await clear_state(pool)

                try:
                    # Strip possible markdown fences
                    clean = raw_extraction.strip()
                    if clean.startswith("```"):
                        clean = clean.split("```")[1].lstrip("json").strip()
                    extracted = _json.loads(clean)
                    reflection_text: str = extracted.get("reflection_text", text[:500])
                    mood: str = extracted.get("mood", "neutral")
                    tomorrow_focus: str = extracted.get("tomorrow_focus", "")
                except Exception:
                    reflection_text = text[:500]
                    mood = "neutral"
                    tomorrow_focus = ""

                await journal_queries.save_journal_entry(pool, today, reflection_text, mood, tomorrow_focus)
                await update_user_profile(pool, TG_UID, last_journal_date=today)

                mood_emoji = {
                    "great": "🌟", "good": "😊", "neutral": "😐",
                    "bad": "😔", "terrible": "😞",
                }.get(mood, "📝")

                name_esc = escape_md(profile.get('name', 'User'))
                focus_esc = escape_md(tomorrow_focus) if tomorrow_focus else "să fii prezent\\."  
                reply = (
                    f"{mood_emoji} Mulțumesc, {name_esc}\\. Am salvat reflecția de azi\\.\n\n"
                    f"*Mâine te concentrezi pe:* {focus_esc}\n\n"
                    f"Noapte bună\\! 🌙"
                )
                await update.message.reply_text(reply, parse_mode="MarkdownV2")
                return

        # 3. Build context snapshot
        context_snapshot = await build_context(pool)
        profile = await get_user_profile(pool, telegram_id)
        
        # 4. Call Gemini
        intent_response = await get_gemini_response(
            user_message=text,
            user_name=profile.get("name", "User"),
            tone=profile.get("tone", "warm"),
            context_snapshot=context_snapshot,
            history=history,
            personal_notes=profile.get("personal_notes") or ""
        )
        print(f"🧠 GEMINI: Intent={intent_response.get('intent')}, Module={intent_response.get('module')}, Data={intent_response.get('data')}")
        
        # 5. Route intent and get final reply + keyboard
        final_reply, reply_markup = await route_intent(pool, intent_response, bot=context.bot)
        print(f"📡 ROUTER: Reply length={len(final_reply) if final_reply else 0}")
        
        if final_reply is None:
            return

        # 6. Save assistant reply to conversations
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO conversations (role, content) VALUES ($1, $2)", "assistant", final_reply)

        # 7. Send to user
        chunks = split_message(final_reply)
        for i, chunk in enumerate(chunks):
            current_markup = reply_markup if i == len(chunks) - 1 else None
            try:
                print(f"📤 SENDING: {repr(chunk[:50])}...")
                await update.message.reply_text(chunk, parse_mode="MarkdownV2", reply_markup=current_markup)
            except Exception as e:
                print(f"⚠️ MarkdownV2 FAILED, falling back to plain text: {e}")
                await update.message.reply_text(chunk, reply_markup=current_markup)

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"ERROR in message_handler: {e}\n{traceback.format_exc()}")
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ceva n-a mers. Încearcă din nou."
            )
        except Exception:
            pass

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    if not await security_check(update):
        return

    try:
        query = update.callback_query
        data = query.data

        # Route onboarding callbacks
        if data.startswith("onboard:"):
            await handle_onboarding_callback(update, context, pool)
            return

        if data.startswith("attendance:"):
            parts = data.split(":")
            action = parts[1]    # "present" sau "absent"
            schedule_id = int(parts[2])
            
            from db.queries.schedule import get_schedule_by_id
            from db.queries.university import get_subject_by_name, log_attendance
            from datetime import date
            
            schedule_item = await get_schedule_by_id(pool, schedule_id)
            if not schedule_item:
                await query.answer("Eroare — cursul nu a fost găsit.")
                return
            
            subject = await get_subject_by_name(pool, schedule_item['subject_name'])
            if not subject:
                await query.answer("Materia nu e în listă.")
                return
            
            attended = action == "present"
            await log_attendance(pool, subject['id'], attended, date.today())
            
            status = "prezent ✅" if attended else "absent ❌"
            await query.answer(f"{schedule_item['subject_name']} — {status}")
            
            # Update message to show status
            msg_text = query.message.text
            await query.edit_message_reply_markup(reply_markup=None)
            await query.edit_message_text(
                f"{msg_text}\n\n_{status} înregistrat\\._",
                parse_mode="MarkdownV2"
            )
            return

        # Phase 4: Module callbacks (module:action:item_id)
        parts = data.split(":")
        if len(parts) >= 2:
            module, action = parts[0], parts[1]
            item_id = int(parts[2]) if len(parts) > 2 else None
            
            if module == "tasks":
                import db.queries.tasks as task_queries
                if action == "complete":
                    await task_queries.complete_task(pool, item_id)
                    await query.answer("Task completed! ✅")
                    if len(parts) > 3 and parts[3] == "list":
                        # Re-list to keep the UI snappy
                        import db.queries.tasks as task_queries
                        tasks = await task_queries.list_tasks(pool)
                        if not tasks:
                            await query.edit_message_text("All tasks done! 🎉")
                        else:
                            from modules.tasks import handle_task_intent
                            # We can just call the module's list logic or recreate it here
                            # To be safe and reuse formatting:
                            from bot.formatter import escape_md
                            from bot.keyboards import task_list_keyboard
                            lines = ["📋 *Your Pending Tasks:*"]
                            for t in tasks:
                                due = f" (due {t['due_date']})" if t['due_date'] else ""
                                priority = " 🔥" if t['priority'] == "high" else ""
                                lines.append(f"`{t['id']}` • {escape_md(t['title'])}{due}{priority}")
                            await query.edit_message_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=task_list_keyboard(tasks))
                    else:
                        await query.edit_message_text(f"Task marked as complete\\.")
                elif action == "delete":
                    task = await task_queries.get_task(pool, item_id)
                    from bot.keyboards import confirmation_keyboard
                    from core.state import set_state
                    await set_state(pool, "awaiting_confirmation", "tasks", "delete", item_id)
                    await query.edit_message_text(
                        f"Are you sure you want to delete *{escape_md(task['title'])}*?",
                        parse_mode="MarkdownV2",
                        reply_markup=confirmation_keyboard("tasks", "delete", item_id)
                    )
                elif action == "delete_confirmed":
                    await task_queries.delete_task(pool, item_id)
                    from core.state import clear_state
                    await clear_state(pool)
                    await query.answer("Deleted.")
                    await query.edit_message_text("Task deleted\\.")
                elif action == "edit":
                    task = await task_queries.get_task(pool, item_id)
                    from core.state import set_state
                    await set_state(pool, "awaiting_edit_field", "tasks", "edit", item_id)
                    await query.edit_message_text(
                        f"What would you like to change about *{escape_md(task['title'])}*?\\n\\n"
                        f"You can say things like:\\n"
                        f"• change title to 'Buy oat milk'\\n"
                        f"• set due date to Friday\\n"
                        f"• change priority to high",
                        parse_mode="MarkdownV2"
                    )
            elif module == "habits":
                import db.queries.habits as habit_queries
                from datetime import datetime
                if action in ["done", "skip"]:
                    status = "done" if action == "done" else "skipped"
                    await habit_queries.log_habit(pool, item_id, datetime.now().date(), status)
                    await query.answer(f"Habit {status}!")
                    
                    if len(parts) > 3 and parts[3] == "list":
                        # Re-list habits to show the checkmark
                        import db.queries.habits as habit_queries
                        habits = await habit_queries.list_habits(pool)
                        today_logged = await habit_queries.get_today_logs(pool)
                        from bot.formatter import escape_md
                        from bot.keyboards import habit_list_keyboard
                        
                        lines = ["✅ *Your Habits Today:*"]
                        for h in habits:
                            status_icon = "✅" if h['id'] in today_logged else "⬜"
                            streak = f" (streak: *{h['streak_count']}* 🔥)" if h['streak_count'] > 0 else ""
                            lines.append(f"{status_icon} {escape_md(h['name'])}{streak}")
                        
                        await query.edit_message_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=habit_list_keyboard(habits))
                    else:
                        await query.edit_message_text(f"Habit marked as {status}\\.")
                elif action == "delete":
                    habit = await habit_queries.get_habit(pool, item_id)
                    from bot.keyboards import confirmation_keyboard
                    from core.state import set_state
                    await set_state(pool, "awaiting_confirmation", "habits", "delete", item_id)
                    await query.edit_message_text(
                        f"Are you sure you want to delete the habit *{escape_md(habit['name'])}*?",
                        parse_mode="MarkdownV2",
                        reply_markup=confirmation_keyboard("habits", "delete", item_id)
                    )
                elif action == "delete_confirmed":
                    await habit_queries.delete_habit(pool, item_id)
                    from core.state import clear_state
                    await clear_state(pool)
                    await query.answer("Deleted.")
                    await query.edit_message_text("Habit deleted\\.")
            
            # Generic actions
            if action in ["cancel", "delete_cancelled"]:
                from core.state import clear_state
                await clear_state(pool)
                await query.answer("Cancelled.")
                await query.edit_message_text("Action cancelled\\.")

        await query.answer()
    except Exception as e:
        print(f"ERROR in callback_handler: {e}")
        traceback.print_exc()

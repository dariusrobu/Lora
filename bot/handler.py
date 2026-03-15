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
                    final_reply, reply_markup = await route_intent(pool, intent_response)
                    await update.message.reply_text(final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup)
                    return
                elif any(word in low_text for word in ['no', 'stop', 'cancel', 'don\'t', 'nu']):
                    await clear_state(pool)
                    await update.message.reply_text("Cancelled\\.")
                    return
                else:
                    await clear_state(pool)
            
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
                final_reply, reply_markup = await route_intent(pool, intent_response)
                await update.message.reply_text(final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup)
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
        final_reply, reply_markup = await route_intent(pool, intent_response)
        print(f"📡 ROUTER: Reply length={len(final_reply)}")
        
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
        print(f"ERROR in message_handler: {e}")
        traceback.print_exc()

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

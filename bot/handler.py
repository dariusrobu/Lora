from telegram import Update
from telegram.ext import ContextTypes
from core.config import TELEGRAM_USER_ID
from bot.onboarding import start_onboarding, handle_onboarding, handle_onboarding_callback
from db.queries.profile import is_onboarding_complete, get_user_profile
from bot.formatter import escape_md
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
        print(f"Unauthorized access attempt by ID: {update.effective_user.id}")
    return is_authorized

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    # Log EVERY message before the security check
    user_id = update.effective_user.id if update.effective_user else "Unknown"
    text = update.message.text if update.message else "[Non-text message]"
    print(f"DEBUG: Received signal from {user_id}: {text}")

    if not await security_check(update):
        return

    try:
        telegram_id = update.effective_user.id
        
        # Non-text message handling
        if not update.message or not update.message.text:
            if update.message and (update.message.photo or update.message.voice or update.message.video or update.message.sticker):
                await update.message.reply_text("I can only read text for now — what would you like to do?")
            return

        text = update.message.text
        
        # Check onboarding status
        onboarding_done = await is_onboarding_complete(pool, telegram_id)
        onboarding_step = context.user_data.get("onboarding_step")
        
        print(f"DEBUG: Onboarding status: done={onboarding_done}, step={onboarding_step}")
        
        if not onboarding_done or onboarding_step:
            if text == "/start":
                await start_onboarding(update, context, pool)
            else:
                await handle_onboarding(update, context, pool)
            return

        # Phase 3: Gemini Brain integration
        # 1. Save user message to conversations
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO conversations (role, content) VALUES ($1, $2)", "user", text)

            # 2. Get history (last 10 turns)
            history_rows = await conn.fetch("SELECT role, content FROM conversations ORDER BY created_at DESC LIMIT 10")
            history = [{"role": r["role"], "content": r["content"]} for r in reversed(history_rows)]

        # Phase 8: State Check (Confirmations / Edits)
        from core.state import get_state, clear_state
        state = await get_state(pool)

        if state and state['state_type'] == 'awaiting_confirmation':
            # Simple yes/no detection for confirmations
            low_text = text.lower()
            if any(word in low_text for word in ['yes', 'yeah', 'do it', 'confirm', 'sure', 'da']):
                # Trigger the confirmed action
                data = {"id": state['item_id'], "confirmed": True}
                intent = f"{state['action']}_confirmed" # e.g. delete_confirmed
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
                # If user sends unrelated message, clear state and proceed to Gemini
                await clear_state(pool)

        # 3. Build context snapshot

        context_snapshot = await build_context(pool)
        profile = await get_user_profile(pool, telegram_id)
        
        # 4. Call Gemini
        print("DEBUG: Calling Gemini...")
        intent_response = await get_gemini_response(
            user_message=text,
            user_name=profile.get("name", "User"),
            tone=profile.get("tone", "warm"),
            context_snapshot=context_snapshot,
            history=history,
            personal_notes=profile.get("personal_notes") or ""
        )
        print(f"DEBUG: Gemini response: {intent_response}")
        
        # 5. Route intent and get final reply + keyboard
        final_reply, reply_markup = await route_intent(pool, intent_response)
        
        # 6. Save assistant reply to conversations
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO conversations (role, content) VALUES ($1, $2)", "assistant", final_reply)

        # 7. Send to user
        from bot.formatter import split_message
        chunks = split_message(final_reply)
        
        for i, chunk in enumerate(chunks):
            # Only attach keyboard to the last chunk
            current_markup = reply_markup if i == len(chunks) - 1 else None
            try:
                await update.message.reply_text(chunk, parse_mode="MarkdownV2", reply_markup=current_markup)
            except Exception as e:
                print(f"DEBUG: MarkdownV2 failed, sending as plain text: {e}")
                await update.message.reply_text(chunk, reply_markup=current_markup)

    except Exception as e:
        print(f"ERROR in message_handler: {e}")
        traceback.print_exc()

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    user_id = update.effective_user.id if update.effective_user else "Unknown"
    print(f"DEBUG: Callback received from {user_id}: {update.callback_query.data}")

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
            elif module == "habits":
                import db.queries.habits as habit_queries
                from datetime import datetime
                if action in ["done", "skip"]:
                    status = "done" if action == "done" else "skipped"
                    await habit_queries.log_habit(pool, item_id, datetime.now().date(), status)
                    await query.answer(f"Habit {status}!")
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
            elif module == "projects":
                import db.queries.projects as project_queries
                if action == "delete":
                    project = await project_queries.get_project(pool, item_id)
                    from bot.keyboards import confirmation_keyboard
                    from core.state import set_state
                    await set_state(pool, "awaiting_confirmation", "projects", "delete", item_id)
                    await query.edit_message_text(
                        f"Are you sure you want to delete project *{escape_md(project['name'])}*?\\nTasks linked to it will NOT be deleted\\.",
                        parse_mode="MarkdownV2",
                        reply_markup=confirmation_keyboard("projects", "delete", item_id)
                    )
                elif action == "delete_confirmed":
                    await project_queries.delete_project(pool, item_id)
                    from core.state import clear_state
                    await clear_state(pool)
                    await query.answer("Deleted.")
                    await query.edit_message_text("Project deleted\\.")
            
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

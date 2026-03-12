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
    if not update.effective_user or update.effective_user.id != TELEGRAM_USER_ID:
        return False
    return True

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    if not await security_check(update):
        return

    try:
        telegram_id = update.effective_user.id
        text = update.message.text if update.message else ""
        print(f"Incoming message from {telegram_id}: {text}")
        
        # Check onboarding status
        onboarding_done = await is_onboarding_complete(pool, telegram_id)
        onboarding_step = context.user_data.get("onboarding_step")
        
        print(f"Onboarding status: done={onboarding_done}, step={onboarding_step}")
        
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

        # 3. Build context snapshot
        context_snapshot = await build_context(pool)
        profile = await get_user_profile(pool, telegram_id)
        
        # 4. Call Gemini
        print("Calling Gemini...")
        intent_response = await get_gemini_response(
            user_message=text,
            user_name=profile.get("name", "User"),
            tone=profile.get("tone", "warm"),
            context_snapshot=context_snapshot,
            history=history,
            personal_notes=profile.get("personal_notes") or ""
        )
        print(f"Gemini response: {intent_response}")
        
        # 5. Route intent and get final reply + keyboard
        final_reply, reply_markup = await route_intent(pool, intent_response)
        
        # 6. Save assistant reply to conversations
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO conversations (role, content) VALUES ($1, $2)", "assistant", final_reply)

        # 7. Send to user
        # Note: We use plain text if parse_mode=MarkdownV2 fails
        try:
            await update.message.reply_text(final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup)
        except Exception as e:
            print(f"MarkdownV2 failed, sending as plain text: {e}")
            await update.message.reply_text(final_reply, reply_markup=reply_markup)

    except Exception as e:
        print(f"Error in message_handler: {e}")
        traceback.print_exc()

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    if not await security_check(update):
        return

    try:
        query = update.callback_query
        data = query.data
        print(f"Callback received: {data}")

        # Route onboarding callbacks
        if data.startswith("onboard:"):
            await handle_onboarding_callback(update, context, pool)
            return

        # Normal callback flow (Phase 4+)
        await query.answer("Feature coming soon!")
    except Exception as e:
        print(f"Error in callback_handler: {e}")
        traceback.print_exc()

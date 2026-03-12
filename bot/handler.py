from telegram import Update
from telegram.ext import ContextTypes
from core.config import TELEGRAM_USER_ID
from bot.onboarding import start_onboarding, handle_onboarding, handle_onboarding_callback
from db.queries.profile import is_onboarding_complete

async def security_check(update: Update) -> bool:
    """Rejects non-whitelisted user IDs silently."""
    if not update.effective_user or update.effective_user.id != TELEGRAM_USER_ID:
        return False
    return True

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    if not await security_check(update):
        return

    telegram_id = update.effective_user.id
    
    # Check onboarding status
    onboarding_done = await is_onboarding_complete(pool, telegram_id)
    
    # If mid-onboarding or not started
    if not onboarding_done or context.user_data.get("onboarding_step"):
        if update.message.text == "/start" and not onboarding_done:
            await start_onboarding(update, context, pool)
        else:
            await handle_onboarding(update, context, pool)
        return

    # Normal message flow (Phase 3+)
    await update.message.reply_text("I heard you! (Phase 3 implementation coming soon)")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    if not await security_check(update):
        return

    query = update.callback_query
    data = query.data

    # Route onboarding callbacks
    if data.startswith("onboard:"):
        await handle_onboarding_callback(update, context, pool)
        return

    # Normal callback flow (Phase 4+)
    await query.answer("Feature coming soon!")

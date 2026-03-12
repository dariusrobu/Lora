from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db.queries.profile import update_user_profile, get_user_profile
from bot.formatter import escape_md
import pytz

async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    """Step 1 - Greeting"""
    reply = "Hi! I'm Lora, your personal assistant 👋\nBefore we start, what should I call you?"
    await update.message.reply_text(reply)
    # Use context.user_data to track onboarding step
    context.user_data["onboarding_step"] = "awaiting_name"

async def handle_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    step = context.user_data.get("onboarding_step")
    telegram_id = update.effective_user.id

    if step == "awaiting_name":
        name = update.message.text
        await update_user_profile(pool, telegram_id, name=name)
        
        profile = await get_user_profile(pool, telegram_id)
        timezone = profile.get("timezone", "Europe/Bucharest")
        
        keyboard = [
            [
                InlineKeyboardButton("Yes, that's right", callback_data="onboard:tz_ok"),
                InlineKeyboardButton("No, change it", callback_data="onboard:tz_change"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        reply = f"Nice to meet you, {escape_md(name)}!\nI've got your timezone set to `{escape_md(timezone)}` — is that right?"
        await update.message.reply_text(reply, reply_markup=reply_markup, parse_mode="MarkdownV2")
        context.user_data["onboarding_step"] = "awaiting_tz_confirm"

    elif step == "awaiting_tz_manual":
        tz_input = update.message.text
        if tz_input in pytz.all_timezones:
            await update_user_profile(pool, telegram_id, timezone=tz_input)
            await finish_onboarding(update, context, pool)
        else:
            await update.message.reply_text("Hmm, I don't recognize that timezone. Try something like `Europe/London` or `America/New_York`.")

async def handle_onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    data = query.data

    if data == "onboard:tz_ok":
        await finish_onboarding(update, context, pool)
    elif data == "onboard:tz_change":
        await query.edit_message_text("What's your timezone? (e.g. Europe/London, America/New_York)")
        context.user_data["onboarding_step"] = "awaiting_tz_manual"

async def finish_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    telegram_id = update.effective_user.id
    profile = await get_user_profile(pool, telegram_id)
    name = profile.get("name", "there")
    morning_time = profile.get("morning_time", "08:00")
    eod_time = profile.get("eod_time", "21:00")

    reply = (
        f"Perfect. Here's what I can help you with:\n"
        f"📋 *Tasks & Projects*\n"
        f"✅ *Habits*\n"
        f"📓 *Notes & Journal*\n"
        f"💰 *Finance*\n"
        f"📅 *Events*\n\n"
        f"Just talk to me naturally — no commands needed.\n"
        f"I'll send you a morning briefing every day at *{escape_md(morning_time)}*\n"
        f"and check in with you each evening at *{escape_md(eod_time)}*.\n\n"
        f"What would you like to start with?"
    )
    
    await update_user_profile(pool, telegram_id, onboarding_complete=True)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(reply, parse_mode="MarkdownV2")
    else:
        await update.message.reply_text(reply, parse_mode="MarkdownV2")
    
    context.user_data["onboarding_step"] = None

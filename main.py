import asyncio
import sys
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters
from core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_USER_ID, TIMEZONE, MORNING_BRIEFING_TIME, EOD_REFLECTION_TIME
from db.connection import get_pool, close_pool
from bot.handler import message_handler, callback_handler, voice_handler
from functools import partial

async def start_bot():
    print("Starting Lora initialization...", flush=True)
    
    # 1. Database Pool
    pool = await get_pool()
    print("Connected to database pool.")
    
    # 2. Ensure user_profile
    await pool.execute(
        """
        INSERT INTO user_profile (telegram_id, timezone, morning_time, eod_time)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (telegram_id) DO NOTHING
        """,
        TELEGRAM_USER_ID, TIMEZONE, MORNING_BRIEFING_TIME, EOD_REFLECTION_TIME
    )
    print(f"User profile ensured for ID: {TELEGRAM_USER_ID}")

    # 3. Build the Application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # 4. Initialize Scheduler
    from scheduler.jobs import setup_scheduler
    setup_scheduler(application, pool)
    
    # 5. Register handlers
    msg_handler_with_pool = partial(message_handler, pool=pool)
    cb_handler_with_pool = partial(callback_handler, pool=pool)
    voice_handler_with_pool = partial(voice_handler, pool=pool)
    
    application.add_handler(MessageHandler(filters.VOICE, voice_handler_with_pool))
    application.add_handler(MessageHandler(filters.ALL, msg_handler_with_pool))
    application.add_handler(CallbackQueryHandler(cb_handler_with_pool))
    
    print("Lora is ready. Starting polling... 🤖")
    
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        
        # Keep the bot running
        print("Polling active.")
        try:
            # Simple wait loop to keep the async function alive while polling
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("Stopping...")
        finally:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            await close_pool()
            print("Database pool closed. Shutdown complete.")

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        pass

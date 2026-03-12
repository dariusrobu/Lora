import asyncio
import sys
import signal
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters
from core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_USER_ID, TIMEZONE, MORNING_BRIEFING_TIME, EOD_REFLECTION_TIME
from db.connection import get_pool, close_pool
from bot.handler import message_handler, callback_handler
from functools import partial

async def main():
    print("Starting Lora...")
    
    # 2. Initialize asyncpg connection pool
    try:
        pool = await get_pool()
        print("Connected to database pool.")
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)
        
    try:
        # 3. Ensure user_profile row exists for TELEGRAM_USER_ID
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_profile (telegram_id, timezone, morning_time, eod_time)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (telegram_id) DO NOTHING
                """,
                TELEGRAM_USER_ID, TIMEZONE, MORNING_BRIEFING_TIME, EOD_REFLECTION_TIME
            )
            print(f"User profile ensured for ID: {TELEGRAM_USER_ID}")

        # 7. Build python-telegram-bot Application
        application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        
        # 8. Register handlers (using partial to pass the pool)
        msg_handler_with_pool = partial(message_handler, pool=pool)
        cb_handler_with_pool = partial(callback_handler, pool=pool)
        
        application.add_handler(MessageHandler(filters.ALL, msg_handler_with_pool))
        application.add_handler(CallbackQueryHandler(cb_handler_with_pool))
        
        # 10. Manual lifecycle management to avoid conflicts
        await application.initialize()
        print("Application initialized.")
        
        # Clear webhook
        await application.bot.delete_webhook(drop_pending_updates=True)
        print("Webhook cleared.")
        
        await application.start()
        print("Application started.")
        
        await application.updater.start_polling()
        print("Lora is running and polling for updates... 🤖")
        
        # Create a stop event to keep the loop running
        stop_event = asyncio.Event()
        
        # Handle stop signals
        def stop():
            stop_event.set()
            
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop)
            except NotImplementedError:
                # signal.add_signal_handler is not implemented on some platforms (e.g. Windows)
                pass

        # Wait until stop signal
        await stop_event.wait()
        
        # 11. Shutdown gracefully
        print("Stopping Lora...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

    except Exception as e:
        print(f"Error running Lora: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await close_pool()
        print("Database pool closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

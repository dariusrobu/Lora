import asyncio
import sys
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters
from core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_USER_ID, TIMEZONE, MORNING_BRIEFING_TIME, EOD_REFLECTION_TIME
from db.connection import get_pool, close_pool
from bot.handler import message_handler, callback_handler
from functools import partial

def main():
    print("Starting Lora...")
    
    # Create the event loop to initialize the database pool
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        pool = loop.run_until_complete(get_pool())
        print("Connected to database pool.")
        
        # Ensure user_profile row exists
        loop.run_until_complete(pool.execute(
            """
            INSERT INTO user_profile (telegram_id, timezone, morning_time, eod_time)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
            TELEGRAM_USER_ID, TIMEZONE, MORNING_BRIEFING_TIME, EOD_REFLECTION_TIME
        ))
        print(f"User profile ensured for ID: {TELEGRAM_USER_ID}")
    except Exception as e:
        print(f"Startup error: {e}")
        return

    # Build the Application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # 5. Initialize Scheduler
    from scheduler.jobs import setup_scheduler
    scheduler = setup_scheduler(application, pool)
    
    # Register handlers
    msg_handler_with_pool = partial(message_handler, pool=pool)
    cb_handler_with_pool = partial(callback_handler, pool=pool)
    
    application.add_handler(MessageHandler(filters.ALL, msg_handler_with_pool))
    application.add_handler(CallbackQueryHandler(cb_handler_with_pool))
    
    print("Lora is running and starting polling... 🤖")
    
    # run_polling is blocking and handles its own event loop and signal listeners
    application.run_polling(drop_pending_updates=True)
    
    # Once polling stops, close the pool
    loop.run_until_complete(close_pool())
    print("Database pool closed.")

if __name__ == "__main__":
    main()

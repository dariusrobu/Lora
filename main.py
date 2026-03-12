import asyncio
import sys
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
        # We use run_polling() which is the standard way to run the bot
        application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        
        # 8. Register handlers (using partial to pass the pool)
        msg_handler_with_pool = partial(message_handler, pool=pool)
        cb_handler_with_pool = partial(callback_handler, pool=pool)
        
        application.add_handler(MessageHandler(filters.ALL, msg_handler_with_pool))
        application.add_handler(CallbackQueryHandler(cb_handler_with_pool))
        
        print("Lora is running and starting polling... 🤖")
        
        # 10. Clear any existing webhooks and start polling
        async with application:
            await application.bot.delete_webhook(drop_pending_updates=True)
            await application.run_polling()

    except Exception as e:
        print(f"Error running Lora: {e}")
    finally:
        await close_pool()
        print("Database pool closed.")

if __name__ == "__main__":
    # Standard way to run async main in Python 3.7+
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping Lora...")

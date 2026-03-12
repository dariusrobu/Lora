import asyncio
import sys
from core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_USER_ID
from db.connection import get_pool, close_pool

async def main():
    print("Starting Lora...")
    
    # 1. Load + validate all env vars (already handled by core/config.py import)
    
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
                INSERT INTO user_profile (telegram_id)
                VALUES ($1)
                ON CONFLICT (telegram_id) DO NOTHING
                """,
                TELEGRAM_USER_ID
            )
            print(f"User profile ensured for ID: {TELEGRAM_USER_ID}")

        # Placeholder for remaining startup steps
        # 4. Initialize Gemini client (Phase 3)
        # 5. Initialize AsyncIOScheduler and register all jobs (Phase 6)
        # 6. Start scheduler
        # 7. Build python-telegram-bot Application (Phase 2)
        # 8. Register handlers (Phase 2)
        
        print("Lora is running 🤖")
        
        # Keep the application running (this will be replaced by bot.run_polling() in Phase 2)
        while True:
            await asyncio.sleep(3600)

    except KeyboardInterrupt:
        print("\nStopping Lora...")
    finally:
        await close_pool()
        print("Database pool closed.")

if __name__ == "__main__":
    asyncio.run(main())

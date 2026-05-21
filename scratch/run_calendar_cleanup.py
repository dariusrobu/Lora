import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from core.icloud import cleanup_calendar_orphans

load_dotenv()


async def run():
    database_url = os.getenv("DATABASE_URL")
    pool = await asyncpg.create_pool(database_url)
    try:
        print("Starting cleanup of calendar orphans...")
        stats = await cleanup_calendar_orphans(pool)
        print(f"Cleanup finished: {stats}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run())

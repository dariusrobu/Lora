import asyncio
import os
import asyncpg
from dotenv import load_dotenv
from core.icloud import sync_university_schedule_to_calendar

load_dotenv()

async def run():
    database_url = os.getenv('DATABASE_URL')
    pool = await asyncpg.create_pool(database_url)
    try:
        print("Starting fresh university schedule sync...")
        stats = await sync_university_schedule_to_calendar(pool)
        print(f"Sync complete: {stats}")
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(run())

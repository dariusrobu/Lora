import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def list_events_all():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows = await conn.fetch("SELECT title, event_date, event_time, event_type, created_at FROM events WHERE DATE(created_at) >= '2026-05-10' ORDER BY created_at DESC")
    print("Events since Sunday:")
    for r in rows:
        print(f"- {r['title']} | Date: {r['event_date']} | Type: {r['event_type']} | Created: {r['created_at']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(list_events_all())

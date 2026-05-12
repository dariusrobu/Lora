import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_events():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows = await conn.fetch("SELECT * FROM events WHERE event_type = 'reminder' AND event_date >= '2026-05-10' ORDER BY event_date ASC, event_time ASC")
    print("Reminders since Sunday:")
    for r in rows:
        print(f"- {r['title']} on {r['event_date']} at {r['event_time']} | Reminded At: {r['reminded_at']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_events())

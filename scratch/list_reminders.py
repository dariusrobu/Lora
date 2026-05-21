import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def list_all_reminders():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch(
        "SELECT title, event_date, created_at, reminded_at FROM events WHERE event_type = 'reminder' ORDER BY created_at DESC LIMIT 30"
    )
    print("Recent Reminders:")
    for r in rows:
        print(
            f"- {r['title']} | Date: {r['event_date']} | Created: {r['created_at']} | Reminded: {r['reminded_at']}"
        )
    await conn.close()


if __name__ == "__main__":
    asyncio.run(list_all_reminders())

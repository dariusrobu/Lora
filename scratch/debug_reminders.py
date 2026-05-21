import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def debug_reminders():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    # Reminders created on Sunday (May 10)
    rows = await conn.fetch("""
        SELECT * FROM events 
        WHERE event_type = 'reminder' 
        AND DATE(created_at) = '2026-05-10'
        ORDER BY created_at ASC
    """)
    print("Reminders created on Sunday:")
    for r in rows:
        print(
            f"- Title: {r['title']} | Date: {r['event_date']} | Time: {r['event_time']} | Reminded At: {r['reminded_at']}"
        )

    # Reminders set FOR Sunday
    rows = await conn.fetch("""
        SELECT * FROM events 
        WHERE event_type = 'reminder' 
        AND event_date = '2026-05-10'
        ORDER BY created_at ASC
    """)
    print("\nReminders set FOR Sunday:")
    for r in rows:
        print(
            f"- Title: {r['title']} | Date: {r['event_date']} | Time: {r['event_time']} | Reminded At: {r['reminded_at']} | Created At: {r['created_at']}"
        )

    await conn.close()


if __name__ == "__main__":
    asyncio.run(debug_reminders())

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def check_reminders():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    # Check table structure
    try:
        cols = await conn.fetch(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'reminders'"
        )
        print("Columns:", [(c["column_name"], c["data_type"]) for c in cols])

        rows = await conn.fetch(
            "SELECT * FROM reminders ORDER BY reminder_time DESC LIMIT 10"
        )
        print("\nRecent Reminders:")
        for r in rows:
            print(
                f"- {r['title']} at {r['reminder_time']} | Is Sent: {r.get('is_sent', 'N/A')} | Sent At: {r.get('sent_at', 'N/A')}"
            )
    except Exception as e:
        print(f"Error: {e}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(check_reminders())

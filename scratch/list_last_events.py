import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def list_last_events():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows = await conn.fetch("SELECT id, title, event_type, created_at FROM events ORDER BY id DESC LIMIT 10")
    print("Last 10 Events/Reminders:")
    for r in rows:
        print(f"- [{r['id']}] {r['title']} ({r['event_type']}) | Created: {r['created_at']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(list_last_events())

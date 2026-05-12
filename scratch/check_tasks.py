import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_tasks():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows = await conn.fetch("SELECT title, due_date, created_at, status FROM tasks WHERE DATE(created_at) >= '2026-05-10' ORDER BY created_at DESC")
    print("Recent Tasks:")
    for r in rows:
        print(f"- {r['title']} | Due: {r['due_date']} | Created: {r['created_at']} | Status: {r['status']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_tasks())

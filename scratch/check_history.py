import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_history():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows = await conn.fetch("SELECT role, content, created_at FROM message_history WHERE DATE(created_at) = '2026-05-10' ORDER BY created_at ASC")
    print("Conversation History for Sunday:")
    for r in rows:
        print(f"[{r['created_at']}] {r['role']}: {r['content']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_history())

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_logs():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows = await conn.fetch("SELECT * FROM execution_log WHERE DATE(created_at) = '2026-05-10' ORDER BY created_at DESC")
    print("Execution Logs for Sunday:")
    for r in rows:
        print(f"- Intent: {r['intent']} | Success: {r['success']} | Error: {r['error_message']} | Created: {r['created_at']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_logs())

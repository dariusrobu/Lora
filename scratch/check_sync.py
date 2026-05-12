import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_sync():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows = await conn.fetch("SELECT summary, synced_at, lora_type FROM calendar_sync ORDER BY synced_at DESC LIMIT 20")
    print("Recent Synced Items:")
    for r in rows:
        print(f"- {r['summary']} | Synced: {r['synced_at']} | Type: {r['lora_type']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_sync())

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def run():
    database_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(database_url)
    try:
        rows = await conn.fetch(
            "SELECT ical_uid, summary FROM calendar_sync WHERE lora_type = 'university_schedule'"
        )
        for r in rows:
            print(f"UID: {r['ical_uid']} | {r['summary']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())

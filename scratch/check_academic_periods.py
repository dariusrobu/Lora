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
            "SELECT * FROM academic_periods WHERE period_type = 'didactic'"
        )
        for r in rows:
            print(f"ID: {r['id']} | {r['name']} | {r['start_date']} -> {r['end_date']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())

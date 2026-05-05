import os
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def check():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch("SELECT * FROM memory_facts")
    for r in rows:
        print(dict(r))
    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())

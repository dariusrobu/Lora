import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def main():
    database_url = os.environ.get("DATABASE_URL")
    print(f"Connecting to: {database_url}")
    conn = await asyncpg.connect(database_url)
    try:
        print("\n--- RECENT TRANSACTIONS ---")
        rows = await conn.fetch("SELECT * FROM finances ORDER BY id DESC LIMIT 5")
        for r in rows:
            print(dict(r))

        print("\n--- RECENT MESSAGE HISTORY ---")
        rows = await conn.fetch("SELECT * FROM message_history ORDER BY id DESC LIMIT 10")
        for r in rows:
            print(dict(r))

        print("\n--- CATEGORIES ---")
        rows = await conn.fetch("SELECT * FROM finance_categories")
        for r in rows:
            print(dict(r))
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())

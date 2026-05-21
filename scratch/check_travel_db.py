import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def check_data():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    lists = await conn.fetch("SELECT DISTINCT list_name FROM travel_items")
    print("Lists:", [r["list_name"] for r in lists])
    items = await conn.fetch("SELECT * FROM travel_items")
    print("Items count:", len(items))
    for i in items:
        print(f"- {i['item']} in {i['list_name']}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(check_data())

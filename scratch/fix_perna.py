import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def fix_perna():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))

    # 1. Find and delete from shopping_list
    rows = await conn.fetch("SELECT id FROM shopping_list WHERE item ILIKE '%perna%'")
    if rows:
        for r in rows:
            await conn.execute("DELETE FROM shopping_list WHERE id = $1", r["id"])
        print(f"Deleted {len(rows)} perna from shopping_list")

    # 2. Add to travel_items
    await conn.execute(
        "INSERT INTO travel_items (item, list_name, trip_type) VALUES ($1, $2, $3)",
        "perna",
        "Cluj",
        "departure",
    )
    print("Added perna to travel_items for Cluj (departure)")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(fix_perna())

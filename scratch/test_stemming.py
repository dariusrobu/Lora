import os
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def check():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        # Check if romanian dict exists and works
        row = await conn.fetchrow(
            "SELECT to_tsvector('romanian', 'cafeaua puii orezul')"
        )
        print(f"Romanian tsvector: {row}")

        # Test match
        match = await conn.fetchval(
            "SELECT to_tsvector('romanian', 'Îmi place cafeaua fără zahăr') @@ to_tsquery('romanian', 'cafea')"
        )
        print(f"Match 'cafeaua' with 'cafea': {match}")
    except Exception as e:
        print(f"Error: {e}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())

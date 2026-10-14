import asyncio
from db.connection import get_pool, close_pool

async def main() -> None:
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("UPDATE subjects SET is_active = FALSE WHERE name ILIKE 'MOCK%'")
            print(result)
    finally:
        await close_pool()

if __name__ == '__main__':
    asyncio.run(main())

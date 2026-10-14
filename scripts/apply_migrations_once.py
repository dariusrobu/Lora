import asyncio
from db.connection import get_pool, apply_migrations, close_pool

async def main():
    pool = await get_pool()
    try:
        print(await apply_migrations(pool))
    finally:
        await close_pool()

asyncio.run(main())

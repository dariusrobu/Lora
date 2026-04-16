import asyncio
from db.connection import get_pool, close_pool
from core.state import clear_state

async def main():
    pool = await get_pool()
    await clear_state(pool)
    print("State cleared!")
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from db.connection import get_pool, close_pool
from db.queries.memory import list_all_memories

async def main():
    pool = await get_pool()
    mems = await list_all_memories(pool)
    print(f"Total memories: {len(mems)}")
    for m in mems:
        print(f"- [{m['category']}] {m['fact']}")
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())

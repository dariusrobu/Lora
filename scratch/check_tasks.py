import asyncio
from db.queries.tasks import list_tasks
from db.connection import get_pool, close_pool

async def check():
    pool = await get_pool()
    tasks = await list_tasks(pool)
    pending = [t for t in tasks if t['status'] == 'pending']
    print(f'PENDING_TASKS_COUNT={len(pending)}')
    await close_pool()

if __name__ == "__main__":
    asyncio.run(check())

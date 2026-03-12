import asyncpg
from core.config import DATABASE_URL

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=1,
                max_size=5,
                command_timeout=30,
                server_settings={"application_name": "lora"}
            )
        except Exception as e:
            print(f"Error creating connection pool: {e}")
            raise
    return _pool

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

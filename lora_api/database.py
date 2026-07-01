import asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    assert _pool is not None, "Database pool not initialized"
    return _pool


async def init_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

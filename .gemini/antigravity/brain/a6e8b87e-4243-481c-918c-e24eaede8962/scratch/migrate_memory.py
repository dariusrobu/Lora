import asyncio
from db.connection import get_pool, close_pool


async def run_migration():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("Running migration for memory_facts...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_facts (
                id SERIAL PRIMARY KEY,
                category VARCHAR(50) NOT NULL,
                fact TEXT NOT NULL,
                source VARCHAR(100),
                confidence NUMERIC(3,2) DEFAULT 1.0,
                last_seen TIMESTAMP DEFAULT NOW(),
                times_referenced INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_facts(category);
            CREATE INDEX IF NOT EXISTS idx_memory_fact_search ON memory_facts USING GIN(to_tsvector('english', fact));
        """)
        print("Migration complete!")
    await close_pool()


if __name__ == "__main__":
    asyncio.run(run_migration())

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def create_table():
    database_url = os.getenv('DATABASE_URL')
    conn = await asyncpg.connect(database_url)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS travel_items (
            id SERIAL PRIMARY KEY,
            item TEXT NOT NULL,
            list_name TEXT NOT NULL DEFAULT 'General',
            is_packed BOOLEAN DEFAULT FALSE,
            trip_type TEXT DEFAULT 'both',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    print("Table travel_items created/verified")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(create_table())

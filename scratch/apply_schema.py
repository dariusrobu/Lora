import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def apply_schema():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not found")
        return

    conn = await asyncpg.connect(database_url)
    try:
        # We only want to run the table creation if it doesn't exist
        # but db/schema.sql has 'CREATE TABLE IF NOT EXISTS' usually.
        # Let's check db/schema.sql content.
        with open('db/schema.sql', 'r') as f:
            sql = f.read()
            
        # Execute the SQL
        await conn.execute(sql)
        print("Schema applied successfully (including travel_items)")
    except Exception as e:
        print(f"Error applying schema: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_schema())

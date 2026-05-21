import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def run_migration():
    database_url = os.getenv("DATABASE_URL")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    print(f"Connecting to database...")
    conn = await asyncpg.connect(database_url)
    try:
        migration_file = "/Users/robudarius/Lora/db/migrations/021_project_progress_soft_delete.sql"
        print(f"Reading migration file {migration_file}...")
        with open(migration_file, "r") as f:
            sql = f.read()
        
        print("Executing migration...")
        await conn.execute(sql)
        print("Migration executed successfully! 🎉")
    except Exception as e:
        print(f"Error executing migration: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migration())

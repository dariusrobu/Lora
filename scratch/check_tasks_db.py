import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_tasks():
    dsn = os.getenv("DATABASE_URL")
    pool = await asyncpg.create_pool(dsn)
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, title, status, due_date FROM tasks WHERE status = 'pending' AND deleted_at IS NULL LIMIT 10")
        for r in rows:
            print(f"ID: {r['id']} | Title: {r['title']} | Status: {r['status']} | Due: {r['due_date']}")
        
        # Also check if they are already synced as reminders
        sync_records = await conn.fetch("SELECT lora_id FROM calendar_sync WHERE lora_type = 'task_reminder'")
        print(f"\nSynced as reminders: {[r['lora_id'] for r in sync_records]}")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(check_tasks())

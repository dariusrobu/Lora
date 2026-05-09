import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def run():
    database_url = os.getenv('DATABASE_URL')
    conn = await asyncpg.connect(database_url)
    try:
        # Find duplicates in calendar_sync
        rows = await conn.fetch("""
            SELECT summary, synced_at::date as date, COUNT(*) 
            FROM calendar_sync 
            GROUP BY summary, synced_at::date 
            HAVING COUNT(*) > 1
        """)
        
        if not rows:
            print("No obvious duplicates found in calendar_sync table.")
        else:
            print(f"Found {len(rows)} potential sync duplicates:")
            for r in rows:
                print(f" - {r['summary']} on {r['date']}: {r['count']} entries")
                
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run())

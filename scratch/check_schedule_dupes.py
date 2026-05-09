import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def run():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not set even after loading .env")
        return
        
    conn = await asyncpg.connect(database_url)
    try:
        # Find duplicates in schedule
        rows = await conn.fetch("""
            SELECT subject_name, day_of_week, start_time, room, class_type, COUNT(*) 
            FROM schedule 
            WHERE is_active = TRUE 
            GROUP BY subject_name, day_of_week, start_time, room, class_type 
            HAVING COUNT(*) > 1
        """)
        
        if not rows:
            print("No duplicates found in schedule table.")
        else:
            print(f"Found {len(rows)} duplicate groups:")
            for r in rows:
                print(f" - {r['subject_name']} ({r['class_type']}) on day {r['day_of_week']} at {r['start_time']} in {r['room']}: {r['count']} entries")
                
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run())

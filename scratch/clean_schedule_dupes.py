import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def run():
    database_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(database_url)
    try:
        # Find duplicates in schedule including week_type
        rows = await conn.fetch("""
            SELECT subject_name, day_of_week, start_time, room, class_type, week_type, COUNT(*) 
            FROM schedule 
            WHERE is_active = TRUE 
            GROUP BY subject_name, day_of_week, start_time, room, class_type, week_type
            HAVING COUNT(*) > 1
        """)

        if not rows:
            print("No duplicates found in schedule table with week_type.")
        else:
            print(f"Found {len(rows)} true duplicates (same week_type):")
            for r in rows:
                print(
                    f" - {r['subject_name']} ({r['class_type']}) on day {r['day_of_week']} at {r['start_time']} in {r['room']} [{r['week_type']}]: {r['count']} entries"
                )

            # Perform cleanup: keep the one with largest ID
            for r in rows:
                print(f"Cleaning up {r['subject_name']}...")
                await conn.execute(
                    """
                    DELETE FROM schedule 
                    WHERE id IN (
                        SELECT id FROM schedule 
                        WHERE subject_name = $1 
                          AND day_of_week = $2 
                          AND start_time = $3 
                          AND room = $4 
                          AND class_type = $5 
                          AND week_type = $6
                          AND is_active = TRUE
                        ORDER BY id DESC OFFSET 1
                    )
                """,
                    r["subject_name"],
                    r["day_of_week"],
                    r["start_time"],
                    r["room"],
                    r["class_type"],
                    r["week_type"],
                )

            print("Cleanup complete!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())

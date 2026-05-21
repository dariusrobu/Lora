import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from core.icloud import get_caldav_client, get_lora_calendar

load_dotenv()


async def run():
    database_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(database_url)
    try:
        # Find duplicates in calendar_sync
        rows = await conn.fetch("""
            SELECT summary, COUNT(*) 
            FROM calendar_sync 
            WHERE lora_type = 'university_schedule'
            GROUP BY summary
            HAVING COUNT(*) > 1
        """)

        if not rows:
            print("No duplicates found in calendar_sync.")
            return

        client = get_caldav_client()
        cal = get_lora_calendar(client)

        for r in rows:
            summary = r["summary"]
            print(f"Cleaning up duplicates for: {summary}")

            # Fetch all sync records for this summary
            records = await conn.fetch(
                """
                SELECT id, ical_uid FROM calendar_sync 
                WHERE summary = $1 AND lora_type = 'university_schedule'
                ORDER BY id DESC
            """,
                summary,
            )

            # Keep the first one, delete the rest
            to_keep = records[0]
            to_delete = records[1:]

            for rec in to_delete:
                uid = rec["ical_uid"]
                print(f"  Attempting to delete {uid}...")
                try:
                    # Try to delete from iCloud
                    try:
                        event = cal.event_by_uid(uid)
                        event.delete()
                        print(f"  ✅ Deleted {uid} from iCloud")
                    except Exception as e:
                        print(f"  ⚠️ Could not delete {uid} from iCloud: {e}")
                        # Try searching by summary as fallback if UID delete failed
                        matches = cal.search(summary=summary)
                        if len(matches) > 1:
                            # This is risky, but if we have multiple matches for same summary...
                            # We'll just delete one of them that matches our UID if possible
                            for m in matches:
                                if uid in m.data:
                                    m.delete()
                                    print(f"  ✅ Deleted {uid} via content search")
                                    break

                    # Remove from sync table
                    await conn.execute(
                        "DELETE FROM calendar_sync WHERE id = $1", rec["id"]
                    )
                    print(f"  🗑 Removed record {rec['id']} from DB")

                except Exception as e:
                    print(f"  ❌ Failed processing {uid}: {e}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())

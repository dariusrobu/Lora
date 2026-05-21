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
        # Get orphans from DB
        orphans = await conn.fetch("""
            SELECT cs.ical_uid, cs.summary FROM calendar_sync cs
            LEFT JOIN schedule s ON cs.lora_id = s.id AND cs.lora_type = 'university_schedule'
            WHERE cs.lora_type = 'university_schedule'
            AND s.id IS NULL
        """)

        print(f"Found {len(orphans)} orphans to delete from iCloud.")

        client = get_caldav_client()
        cal = get_lora_calendar(client)

        for o in orphans:
            uid = o["ical_uid"]
            print(f"Attempting to delete {uid} ({o['summary']})...")
            try:
                # Try to find by UID
                try:
                    event = cal.event_by_uid(uid)
                    event.delete()
                    print(f"✅ Deleted {uid}")
                except Exception as e:
                    if "404" in str(e) or "NotFoundError" in str(e):
                        print(f"ℹ️ {uid} not found in iCloud, skipping.")
                    elif "412" in str(e):
                        print(f"⚠️ 412 error for {uid}. Trying alternative search...")
                        # Search by UID as fallback
                        matches = cal.search(uid=uid)
                        if matches:
                            for m in matches:
                                m.delete()
                            print(f"✅ Deleted {uid} via search.")
                        else:
                            print(f"❌ {uid} still not found via search.")
                    else:
                        print(f"❌ Error deleting {uid}: {e}")

                # Regardless of success in iCloud, remove from sync table if it's an orphan
                await conn.execute("DELETE FROM calendar_sync WHERE ical_uid = $1", uid)
                print(f"🗑 Removed {uid} from sync table.")

            except Exception as e:
                print(f"CRITICAL error processing {uid}: {e}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())

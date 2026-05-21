import asyncio
import os
from dotenv import load_dotenv
from core.icloud import get_caldav_client, get_lora_calendar

load_dotenv()


async def run():
    client = get_caldav_client()
    cal = get_lora_calendar(client)

    print("Fetching all Lora schedule events from iCloud...")
    # Search by UID prefix if possible, or just scan all
    events = cal.search(uid="lora-schedule-")

    print(f"Found {len(events)} schedule events to delete.")

    count = 0
    for e in events:
        try:
            # Check UID just in case
            from icalendar import Calendar as iCal

            ical = iCal.from_ical(e.data)
            uid = str(ical.walk("vevent")[0].get("uid"))

            if "lora-schedule-" in uid:
                e.delete()
                count += 1
                if count % 10 == 0:
                    print(f"  Deleted {count}...")
        except Exception as ex:
            print(f"  Error deleting event: {ex}")

    print(f"Nuked {count} schedule events from iCloud.")

    # Now clean DB
    import asyncpg

    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        await conn.execute(
            "DELETE FROM calendar_sync WHERE lora_type = 'university_schedule'"
        )
        print("Cleaned calendar_sync table.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())

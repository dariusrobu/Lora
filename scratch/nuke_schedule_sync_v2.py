import asyncio
import os
from dotenv import load_dotenv
from core.icloud import get_caldav_client, get_lora_calendar

load_dotenv()


async def run():
    client = get_caldav_client()
    cal = get_lora_calendar(client)

    print("Fetching all events from Lora calendar using .events()...")
    events = cal.events()

    print(f"Found {len(events)} total events.")

    count = 0
    for e in events:
        try:
            from icalendar import Calendar as iCal

            ical = iCal.from_ical(e.data)
            uid = str(ical.walk("vevent")[0].get("uid"))

            if "lora-schedule-" in uid:
                print(f"Deleting {uid}...")
                e.delete()
                count += 1
        except Exception as ex:
            if "412" in str(ex):
                # If delete fails with 412, it might be an ETag issue.
                # In some cases, we might need to refresh the object.
                print(f"  412 error for {uid}. Skipping for now.")
            else:
                print(f"  Error: {ex}")

    print(f"Nuked {count} schedule events.")

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

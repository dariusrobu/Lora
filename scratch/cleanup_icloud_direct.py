import asyncio
from datetime import datetime
from dotenv import load_dotenv
from core.icloud import get_caldav_client, get_lora_calendar, LOCAL_TZ

load_dotenv()


async def run():
    client = get_caldav_client()
    cal = get_lora_calendar(client)

    print("Fetching all events from Lora calendar...")
    # Fetch a large range to be sure
    events = cal.date_search(
        start=datetime(2026, 1, 1, tzinfo=LOCAL_TZ),
        end=datetime(2026, 12, 31, tzinfo=LOCAL_TZ),
    )

    print(f"Found {len(events)} total events in iCloud.")

    seen = {}  # (summary, start_time) -> [event_objects]

    for e in events:
        try:
            # We need to parse the ical to get summary and start time
            from icalendar import Calendar as iCal

            ical = iCal.from_ical(e.data)
            vevent = ical.walk("vevent")[0]

            summary = str(vevent.get("summary"))
            start = vevent.get("dtstart").dt

            # Key by summary and start time (as string for consistency)
            key = (summary, str(start))

            if key not in seen:
                seen[key] = []
            seen[key].append(e)
        except Exception as ex:
            print(f"Error parsing event: {ex}")

    duplicates_count = 0
    for key, event_list in seen.items():
        if len(event_list) > 1:
            print(f"Found {len(event_list)} copies of '{key[0]}' at {key[1]}")
            # Keep the first one, delete the rest
            for extra in event_list[1:]:
                try:
                    extra.delete()
                    duplicates_count += 1
                    print("  ✅ Deleted extra copy.")
                except Exception as ex:
                    print(f"  ❌ Error deleting extra copy: {ex}")

    print(
        f"Cleanup finished. Removed {duplicates_count} duplicates directly from iCloud."
    )


if __name__ == "__main__":
    asyncio.run(run())

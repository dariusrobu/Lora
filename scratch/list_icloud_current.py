import asyncio
import os
import caldav
from datetime import datetime
from dotenv import load_dotenv
from core.icloud import get_caldav_client, get_lora_calendar, LOCAL_TZ
from icalendar import Calendar as iCal

load_dotenv()

async def run():
    client = get_caldav_client()
    cal = get_lora_calendar(client)
    
    print("Listing events for current week (May 4 - May 10)...")
    events = cal.date_search(
        start=datetime(2026, 5, 4, tzinfo=LOCAL_TZ),
        end=datetime(2026, 5, 10, tzinfo=LOCAL_TZ)
    )
    
    print(f"Found {len(events)} events in this range.")
    
    for e in events:
        try:
            ical = iCal.from_ical(e.data)
            for component in ical.walk("vevent"):
                summary = str(component.get("summary"))
                start = component.get("dtstart").dt
                uid = str(component.get("uid"))
                print(f"[{start}] {summary} | UID: {uid}")
        except Exception as ex:
            print(f"Error parsing event: {ex}")

if __name__ == "__main__":
    asyncio.run(run())

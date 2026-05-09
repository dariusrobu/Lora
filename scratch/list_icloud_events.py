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
    
    print("Listing all events to investigate remaining duplicates...")
    events = cal.date_search(
        start=datetime(2026, 2, 23, tzinfo=LOCAL_TZ), # Semester start range
        end=datetime(2026, 2, 28, tzinfo=LOCAL_TZ)
    )
    
    events_data = []
    for e in events:
        try:
            ical = iCal.from_ical(e.data)
            vevent = ical.walk("vevent")[0]
            summary = str(vevent.get("summary"))
            start = vevent.get("dtstart").dt
            uid = str(vevent.get("uid"))
            events_data.append({
                "summary": summary,
                "start": start,
                "uid": uid,
                "obj": e
            })
        except Exception as ex:
            print(f"Error parsing event: {ex}")
            
    # Sort for easier comparison
    events_data.sort(key=lambda x: (str(x["start"]), x["summary"]))
    
    for ed in events_data:
        print(f"[{ed['start']}] {ed['summary']} | UID: {ed['uid']}")

if __name__ == "__main__":
    asyncio.run(run())

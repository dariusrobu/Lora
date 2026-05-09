import asyncio
import os
import caldav
from datetime import datetime
from dotenv import load_dotenv
from core.icloud import get_caldav_client, LOCAL_TZ
from icalendar import Calendar as iCal

load_dotenv()

async def run():
    client = get_caldav_client()
    principal = client.principal()
    calendars = principal.calendars()
    
    print(f"Found {len(calendars)} calendars. Scanning all for '🎓' duplicates...")
    
    for cal in calendars:
        print(f"Scanning calendar: {cal.name}...")
        try:
            events = cal.date_search(
                start=datetime(2026, 5, 4, tzinfo=LOCAL_TZ),
                end=datetime(2026, 5, 10, tzinfo=LOCAL_TZ)
            )
            for e in events:
                ical = iCal.from_ical(e.data)
                for vevent in ical.walk("vevent"):
                    summary = str(vevent.get("summary"))
                    if "🎓" in summary:
                        start = vevent.get("dtstart").dt
                        print(f"  [{start}] {summary} | UID: {vevent.get('uid')}")
        except Exception as ex:
            print(f"  Error scanning {cal.name}: {ex}")

if __name__ == "__main__":
    asyncio.run(run())

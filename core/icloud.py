import caldav
import asyncio
from datetime import datetime, timedelta, date, time
from typing import List, Dict, Any, Optional
import pytz
from icalendar import Calendar as iCal, Event as iEvent, vText, vRecur
import recurring_ical_events
from core.config import (
    ICLOUD_USERNAME,
    ICLOUD_APP_PASSWORD,
    ICLOUD_CALENDAR_NAME,
    TIMEZONE,
)
import db.queries.calendar as calendar_queries

# Timezone constant
LOCAL_TZ = pytz.timezone(TIMEZONE)


def get_caldav_client() -> caldav.DAVClient:
    """Connects to iCloud CalDAV."""
    if not ICLOUD_USERNAME or not ICLOUD_APP_PASSWORD:
        raise ValueError("ICLOUD_USERNAME and ICLOUD_APP_PASSWORD must be set.")

    return caldav.DAVClient(
        url="https://caldav.icloud.com",
        username=ICLOUD_USERNAME,
        password=ICLOUD_APP_PASSWORD,
    )


def get_lora_calendar(client: caldav.DAVClient) -> caldav.Calendar:
    """Retrieves or creates the Lora-specific calendar."""
    principal = client.principal()
    calendars = principal.calendars()

    # Search for existing calendar
    for cal in calendars:
        if cal.name == ICLOUD_CALENDAR_NAME:
            return cal

    # Create if not found
    return principal.make_calendar(name=ICLOUD_CALENDAR_NAME)


async def test_connection() -> dict:
    """Tests the iCloud connection."""
    if not ICLOUD_USERNAME or not ICLOUD_APP_PASSWORD:
        return {
            "success": False,
            "calendars": [],
            "message": "Credențialele iCloud nu sunt configurate. Setează ICLOUD_USERNAME și ICLOUD_APP_PASSWORD în Render.",
        }
    try:
        client = get_caldav_client()
        principal = client.principal()
        calendars = principal.calendars()
        return {
            "success": True,
            "calendars": [c.name for c in calendars],
            "message": f"Conectat cu succes! Am găsit {len(calendars)} calendare.",
        }
    except Exception as e:
        return {"success": False, "calendars": [], "message": f"Eroare: {str(e)}"}


def _parse_ical_event(event: caldav.Event) -> dict:
    """Parses a CalDAV event object into a Lora-friendly dict."""
    ical = iCal.from_ical(event.data)
    vevent = ical.walk("vevent")[0]

    start = vevent.get("dtstart").dt
    end = vevent.get("dtend").dt if vevent.get("dtend") else start

    # Convert to datetime if it's a date (all-day)
    all_day = not isinstance(start, datetime)
    if all_day:
        start = datetime.combine(start, time.min).replace(tzinfo=LOCAL_TZ)
        end = datetime.combine(end, time.min).replace(tzinfo=LOCAL_TZ)
    else:
        # Ensure it has timezone info
        if start.tzinfo is None:
            start = LOCAL_TZ.localize(start)
        else:
            start = start.astimezone(LOCAL_TZ)

        if end.tzinfo is None:
            end = LOCAL_TZ.localize(end)
        else:
            end = end.astimezone(LOCAL_TZ)

    return {
        "uid": str(vevent.get("uid")),
        "summary": str(vevent.get("summary")),
        "start": start,
        "end": end,
        "description": str(vevent.get("description", "")),
        "location": str(vevent.get("location", "")),
        "all_day": all_day,
        "recurring": "RRULE" in vevent,
    }


async def fetch_events(days_ahead: int = 30) -> List[Dict[str, Any]]:
    """Fetches events from the Lora calendar."""
    try:
        client = get_caldav_client()
        cal = get_lora_calendar(client)

        now = datetime.now(LOCAL_TZ)
        future = now + timedelta(days=days_ahead)

        events = cal.date_search(start=now, end=future)
        return [_parse_ical_event(e) for e in events]
    except Exception as e:
        print(f"Error fetching calendar events: {e}")
        return []


async def fetch_all_calendars_events(days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Fetches events from ALL iCloud calendars for the morning briefing."""
    try:
        client = get_caldav_client()
        principal = client.principal()
        calendars = principal.calendars()

        now = datetime.now(LOCAL_TZ)
        future = now + timedelta(days=days_ahead)

        all_events = []
        for cal in calendars:
            try:
                events = cal.date_search(start=now, end=future)
                # Use recurring_ical_events to expand recurrences
                for e in events:
                    ical_obj = iCal.from_ical(e.data)
                    expanded = recurring_ical_events.of(ical_obj).between(now, future)
                    for expanded_event in expanded:
                        start = expanded_event.get("DTSTART").dt
                        if not isinstance(start, datetime):
                            start = LOCAL_TZ.localize(datetime.combine(start, time.min))
                        
                        all_events.append({
                            "summary": str(expanded_event.get("SUMMARY")),
                            "start": start,
                            "calendar": cal.name
                        })
            except Exception:
                continue
        
        # Sort by time
        all_events.sort(key=lambda x: x["start"])
        return all_events
    except Exception as e:
        print(f"Error fetching all calendars: {e}")
        return []


async def create_event(
    summary: str,
    start: datetime,
    end: Optional[datetime] = None,
    description: str = None,
    location: str = None,
    all_day: bool = False,
    uid: str = None,
    rrule: str = None,
) -> str:
    """Creates an event in the Lora calendar."""
    client = get_caldav_client()
    cal = get_lora_calendar(client)

    if end is None:
        end = start + timedelta(hours=1)

    # Create iCal object
    ical = iCal()
    event = iEvent()
    event.add("summary", summary)

    if all_day:
        event.add("dtstart", start.date())
        event.add("dtend", (end + timedelta(days=1)).date())
    else:
        event.add("dtstart", start)
        event.add("dtend", end)

    if description:
        event.add("description", description)
    if location:
        event.add("location", location)

    if uid:
        event.add("uid", uid)
    if rrule:
        # Example: "FREQ=WEEKLY;BYDAY=MO"
        event["rrule"] = vRecur.from_ical(rrule)

    ical.add_component(event)

    new_event = await asyncio.to_thread(cal.add_event, ical.to_ical())
    # Return UID
    return str(iCal.from_ical(new_event.data).walk("vevent")[0].get("uid"))


async def update_event(uid: str, **kwargs) -> bool:
    """Updates an existing event by UID."""
    try:
        client = get_caldav_client()
        cal = get_lora_calendar(client)
        event = cal.event_by_uid(uid)
        
        # We fetch current, modify, and save
        ical = iCal.from_ical(event.data)
        vevent = ical.walk("vevent")[0]
        
        if "summary" in kwargs:
            vevent["summary"] = vText(kwargs["summary"])
        if "description" in kwargs:
            vevent["description"] = vText(kwargs["description"])
        # ... add others if needed
        
        event.data = ical.to_ical()
        event.save()
        return True
    except Exception as e:
        print(f"Update error: {e}")
        return False


async def delete_event(uid: str) -> bool:
    """Deletes an event by UID."""
    try:
        client = get_caldav_client()
        cal = get_lora_calendar(client)
        event = cal.event_by_uid(uid)
        event.delete()
        return True
    except Exception:
        return False


# --- SYNC LOGIC ---

async def sync_university_schedule_to_calendar(pool) -> dict:
    """Syncs the schedule table to Apple Calendar as weekly recurring events."""
    stats = {"created": 0, "skipped": 0, "errors": 0}
    try:
        from db.queries.schedule import get_full_schedule
        classes = await get_full_schedule(pool)
        
        # We need the semester start to calculate the first occurrence
        async with pool.acquire() as conn:
            semester_start = await conn.fetchval("SELECT semester_start FROM semester_config LIMIT 1")
        
        if not semester_start:
            semester_start = date(2024, 2, 26) # Fallback

        day_map = {"luni": 0, "marți": 1, "miercuri": 2, "joi": 3, "vineri": 4, "sâmbătă": 5, "duminică": 6}
        day_codes = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

        for c in classes:
            lora_id = c["id"]
            lora_type = "schedule"
            
            # 1. Check if already synced
            existing = await calendar_queries.get_sync_record(pool, lora_type, lora_id)
            if existing:
                stats["skipped"] += 1
                continue

            # 2. Calculate first occurrence - handle both int and string day_of_week
            dow_val = c["day_of_week"]
            if isinstance(dow_val, int):
                target_dow = dow_val % 7  # Normalize to 0-6
            elif isinstance(dow_val, str):
                target_dow = day_map.get(dow_val.lower(), 0)
            else:
                target_dow = 0  # Fallback for any unexpected type
            
            # Find first date of this weekday after semester start
            days_diff = (target_dow - semester_start.weekday() + 7) % 7
            first_date = semester_start + timedelta(days=days_diff)
            
            start_dt = LOCAL_TZ.localize(datetime.combine(first_date, c["start_time"]))
            end_dt = LOCAL_TZ.localize(datetime.combine(first_date, c["end_time"]))
            
            uid = f"lora-schedule-{lora_id}@lora"
            class_type = c.get("class_type", "course")
            if isinstance(class_type, str):
                summary = f"🎓 {c['subject_name']} ({class_type.upper()})"
            else:
                summary = f"🎓 {c['subject_name']}"
            location = c.get("room", "")
            rrule = f"FREQ=WEEKLY;BYDAY={day_codes[target_dow]}"
            
            try:
                await create_event(
                    summary=summary,
                    start=start_dt,
                    end=end_dt,
                    location=location,
                    uid=uid,
                    rrule=rrule
                )
                await calendar_queries.save_sync_record(pool, lora_type, lora_id, uid, summary)
                stats["created"] += 1
            except Exception as e:
                print(f"Error syncing class {lora_id}: {e}")
                stats["errors"] += 1
                
        return stats
    except Exception as e:
        print(f"Sync schedule CRITICAL error: {e}")
        return stats


async def sync_events_table_to_calendar(pool) -> dict:
    """Syncs the events table to iCloud."""
    stats = {"created": 0, "skipped": 0, "errors": 0}
    try:
        async with pool.acquire() as conn:
            # Only sync non-reminders (events) for now
            rows = await conn.fetch("SELECT * FROM events WHERE event_type = 'event'")
            
        for r in rows:
            lora_id = r["id"]
            lora_type = "event"
            
            existing = await calendar_queries.get_sync_record(pool, lora_type, lora_id)
            if existing:
                stats["skipped"] += 1
                continue
                
            start_dt = datetime.combine(r["event_date"], r["event_time"] or time.min)
            start_dt = LOCAL_TZ.localize(start_dt)
            end_dt = start_dt + timedelta(hours=1)
            
            uid = f"lora-event-{lora_id}@lora"
            summary = f"📅 {r['title']}"
            
            try:
                await create_event(summary=summary, start=start_dt, end=end_dt, uid=uid, description=r.get("description"))
                await calendar_queries.save_sync_record(pool, lora_type, lora_id, uid, summary)
                stats["created"] += 1
            except Exception:
                stats["errors"] += 1
        return stats
    except Exception as e:
        print(f"Sync events error: {e}")
        return stats


async def sync_tasks_with_deadlines(pool) -> dict:
    """Syncs pending tasks with deadlines as all-day events."""
    stats = {"created": 0, "skipped": 0, "errors": 0}
    try:
        from db.queries.tasks import list_tasks
        all_tasks = await list_tasks(pool)
        pending_with_date = [t for t in all_tasks if t["status"] == "pending" and t["due_date"]]
        
        for t in pending_with_date:
            lora_id = t["id"]
            lora_type = "task"
            
            existing = await calendar_queries.get_sync_record(pool, lora_type, lora_id)
            if existing:
                stats["skipped"] += 1
                continue
                
            # All-day event
            start_dt = LOCAL_TZ.localize(datetime.combine(t["due_date"], time.min))
            uid = f"lora-task-{lora_id}@lora"
            summary = f"📋 Task: {t['title']} [{t.get('project_name') or 'Inbox'}]"
            
            try:
                await create_event(summary=summary, start=start_dt, all_day=True, uid=uid)
                await calendar_queries.save_sync_record(pool, lora_type, lora_id, uid, summary)
                stats["created"] += 1
            except Exception:
                stats["errors"] += 1
        return stats
    except Exception as e:
        print(f"Sync tasks error: {e}")
        return stats

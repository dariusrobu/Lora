import caldav
import asyncio
from datetime import datetime, timedelta, date, time
from typing import List, Dict, Any, Optional
import pytz
from icalendar import Calendar as iCal, Event as iEvent, Alarm as iAlarm, vText, vRecur
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

                        all_events.append(
                            {
                                "summary": str(expanded_event.get("SUMMARY")),
                                "start": start,
                                "calendar": cal.name,
                            }
                        )
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
    alarms: List[int] = None,  # List of minutes before start
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

    if alarms:
        for minutes in alarms:
            alarm = iAlarm()
            alarm.add("action", "DISPLAY")
            alarm.add("description", f"Reminder: {summary}")
            alarm.add("trigger", timedelta(minutes=-minutes))
            event.add_component(alarm)

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
    """Deletes an event by UID. Returns True if deleted or not found."""
    try:
        client = get_caldav_client()
        cal = get_lora_calendar(client)
        try:
            event = cal.event_by_uid(uid)
            event.delete()
            return True
        except (caldav.lib.error.NotFoundError, Exception):
            # If not found by UID, try a quick search in the calendar
            # Some servers/providers might have issues with event_by_uid
            events = cal.search(uid=uid)
            if events:
                for e in events:
                    e.delete()
                return True
            # If still not found, we assume it's already gone
            return True
    except Exception as e:
        print(f"Critical error deleting event {uid}: {e}")
        return False


# --- SYNC LOGIC ---


async def sync_university_schedule_to_calendar(pool) -> dict:
    """Syncs the schedule table to Apple Calendar as weekly recurring events."""
    stats = {"created": 0, "skipped": 0, "errors": 0}
    try:
        from db.queries.schedule import get_full_schedule

        classes = await get_full_schedule(pool)

        day_map = {
            "luni": 0,
            "marți": 1,
            "miercuri": 2,
            "joi": 3,
            "vineri": 4,
            "sâmbătă": 5,
            "duminică": 6,
        }
        day_codes = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

        async with pool.acquire() as conn:
            semester_start = await conn.fetchval(
                "SELECT semester_start FROM semester_config LIMIT 1"
            )
            if not semester_start:
                semester_start = date(2026, 2, 23)

            # Fetch didactic periods for segmented syncing
            didactic_periods = await conn.fetch(
                "SELECT * FROM academic_periods WHERE period_type = 'didactic' ORDER BY start_date ASC"
            )

            if not didactic_periods:
                didactic_periods = [
                    {
                        "start_date": semester_start,
                        "end_date": semester_start + timedelta(weeks=20),
                        "id": 0,
                    }
                ]

            for p_idx, period in enumerate(didactic_periods):
                p_start = period["start_date"]
                p_end = period["end_date"]

                for c in classes:
                    lora_id = c["id"]
                    lora_type = "university_schedule"
                    uid = f"lora-schedule-{lora_id}-p{p_idx}@lora"

                    # Check if already synced
                    existing = await calendar_queries.get_sync_record(
                        pool, lora_type, lora_id, uid
                    )
                    if existing:
                        stats["skipped"] += 1
                        continue

                    target_dow = (
                        c["day_of_week"]
                        if isinstance(c["day_of_week"], int)
                        else day_map.get(str(c["day_of_week"]).lower(), 0)
                    )
                    days_diff = (target_dow - p_start.weekday() + 7) % 7
                    first_date = p_start + timedelta(days=days_diff)

                    weeks_since_sem_start = (first_date - semester_start).days // 7
                    is_odd_week = (weeks_since_sem_start + 1) % 2 == 1

                    week_type = c.get("week_type", "both")
                    rrule_interval = 1

                    if week_type in ("par", "even") and is_odd_week:
                        first_date += timedelta(weeks=1)
                        rrule_interval = 2
                    elif week_type in ("impar", "odd") and not is_odd_week:
                        first_date += timedelta(weeks=1)
                        rrule_interval = 2
                    elif week_type in ("par", "even", "impar", "odd"):
                        rrule_interval = 2

                    if first_date > p_end:
                        continue

                    start_dt = LOCAL_TZ.localize(
                        datetime.combine(first_date, c["start_time"])
                    )
                    end_dt = LOCAL_TZ.localize(
                        datetime.combine(first_date, c["end_time"])
                    )

                    summary = f"🎓 {c['subject_name']} ({c.get('class_type', 'curs').upper()})"
                    until_str = p_end.strftime("%Y%m%dT235959Z")
                    rrule = f"FREQ=WEEKLY;BYDAY={day_codes[target_dow % 7]};UNTIL={until_str}"
                    if rrule_interval > 1:
                        rrule += f";INTERVAL={rrule_interval}"

                    # Alarms for classes: 15 min before
                    alarms = [15]

                    try:
                        await create_event(
                            summary=summary,
                            start=start_dt,
                            end=end_dt,
                            location=c.get("room"),
                            uid=uid,
                            rrule=rrule,
                            alarms=alarms,
                        )
                        await calendar_queries.save_sync_record(
                            pool, lora_type, lora_id, uid, summary
                        )
                        stats["created"] += 1
                    except Exception as e:
                        print(f"Error syncing {lora_id} in period {p_idx}: {e}")
                        stats["errors"] += 1

        return stats
    except Exception as e:
        print(f"Sync schedule CRITICAL error: {e}")
        import traceback

        traceback.print_exc()
        return stats


def get_reminders_list(client: caldav.DAVClient) -> caldav.Calendar:
    """Finds the default Reminders list (prioritizing 'LoraBot', then 'Lora')."""
    principal = client.principal()
    calendars = principal.calendars()

    # Filter only those that support VTODO
    todo_calendars = []
    for cal in calendars:
        # Avoid the main Lora calendar
        if "9173b4cb-1371-4605-ae23-0ed1c5d397b1" in str(cal.url):
            continue
        try:
            # Simple check: try to fetch 1 todo (or just check properties if possible)
            # Fetching 1 todo is a reliable way to check support
            cal.todos(amount=1)
            todo_calendars.append(cal)
        except Exception:
            continue

    if not todo_calendars:
        # Fallback to the one that worked in test_todo
        for cal in calendars:
            if "Reminders" in cal.get_display_name():
                return cal
        return calendars[0]

    # Priority: "Lora" (exact/case-insensitive), then "Reminders", then "Tasks"
    for name_hint in ["Lora", "Reminders", "Tasks"]:
        for cal in todo_calendars:
            if name_hint.lower() == cal.get_display_name().lower():
                return cal

    return todo_calendars[0]


async def sync_events_table_to_calendar(pool) -> dict:
    """Syncs the events table to iCloud (both events and reminders)."""
    stats = {"created": 0, "skipped": 0, "errors": 0}
    try:
        async with pool.acquire() as conn:
            # Sync all types of events and reminders
            rows = await conn.fetch("SELECT * FROM events")

        for r in rows:
            lora_id = r["id"]
            lora_type = "event"

            existing = await calendar_queries.get_sync_record(pool, lora_type, lora_id)
            if existing:
                stats["skipped"] += 1
                continue

            all_day = r["event_time"] is None
            if all_day:
                start_dt = LOCAL_TZ.localize(
                    datetime.combine(r["event_date"], time.min)
                )
                end_dt = start_dt
            else:
                start_dt = LOCAL_TZ.localize(
                    datetime.combine(r["event_date"], r["event_time"])
                )
                end_dt = start_dt + timedelta(hours=1)

            uid = f"lora-event-{lora_id}@lora"
            icon = "📅" if r["event_type"] == "event" else "🔔"
            summary = f"{icon} {r['title']}"

            # Set alarms based on Lora settings
            alarms = []
            if r.get("remind_before_minutes"):
                alarms.append(r["remind_before_minutes"])
            if r.get("remind_1day"):
                alarms.append(1440)  # 24 hours

            try:
                await create_event(
                    summary=summary,
                    start=start_dt,
                    end=end_dt,
                    uid=uid,
                    all_day=all_day,
                    description=r.get("description"),
                    alarms=alarms,
                )
                await calendar_queries.save_sync_record(
                    pool, lora_type, lora_id, uid, summary
                )
                stats["created"] += 1
            except Exception as e:
                print(f"Error syncing event {lora_id}: {e}")
                stats["errors"] += 1
        return stats
    except Exception as e:
        print(f"Sync events error: {e}")
        return stats


async def sync_exams_to_calendar(pool) -> dict:
    """Syncs upcoming exams to iCloud as all-day events."""
    stats = {"created": 0, "skipped": 0, "errors": 0}
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT e.*, s.name as subject_name 
                FROM exams e 
                JOIN subjects s ON s.id = e.subject_id
            """)

        for r in rows:
            lora_id = r["id"]
            lora_type = "exam"

            existing = await calendar_queries.get_sync_record(pool, lora_type, lora_id)
            if existing:
                stats["skipped"] += 1
                continue

            # Exams are all-day since they lack a specific time in DB
            start_dt = LOCAL_TZ.localize(datetime.combine(r["exam_date"], time.min))
            uid = f"lora-exam-{lora_id}@lora"
            summary = f"🎓 EXAMEN: {r['subject_name']} ({r['exam_type'].upper()})"

            location = r.get("room") or ""
            description = r.get("notes") or ""

            try:
                await create_event(
                    summary=summary,
                    start=start_dt,
                    all_day=True,
                    uid=uid,
                    location=location,
                    description=description,
                )
                await calendar_queries.save_sync_record(
                    pool, lora_type, lora_id, uid, summary
                )
                stats["created"] += 1
            except Exception as e:
                print(f"Error syncing exam {lora_id}: {e}")
                stats["errors"] += 1
        return stats
    except Exception as e:
        print(f"Sync exams error: {e}")
        return stats


async def sync_tasks_with_deadlines(pool) -> dict:
    """Syncs pending tasks with deadlines as all-day events."""
    stats = {"created": 0, "skipped": 0, "errors": 0}
    try:
        from db.queries.tasks import list_tasks

        all_tasks = await list_tasks(pool)
        pending_with_date = [
            t for t in all_tasks if t["status"] == "pending" and t["due_date"]
        ]

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
                await create_event(
                    summary=summary, start=start_dt, all_day=True, uid=uid
                )
                await calendar_queries.save_sync_record(
                    pool, lora_type, lora_id, uid, summary
                )
                stats["created"] += 1
            except Exception:
                stats["errors"] += 1
        return stats
    except Exception as e:
        print(f"Sync tasks error: {e}")
        return stats


async def cleanup_calendar_orphans(pool) -> dict:
    """Deletes iCloud events for Lora entities that are now inactive or deleted."""
    stats = {"deleted": 0, "errors": 0}
    try:
        async with pool.acquire() as conn:
            # 1. Identify orphaned schedule events (inactive or missing)
            orphaned_schedule = await conn.fetch("""
                SELECT cs.ical_uid FROM calendar_sync cs
                LEFT JOIN schedule s ON cs.lora_id = s.id
                WHERE cs.lora_type = 'university_schedule'
                AND (s.id IS NULL OR s.is_active = FALSE)
            """)

            # 2. Identify orphaned events/reminders (missing)
            orphaned_events = await conn.fetch("""
                SELECT cs.ical_uid FROM calendar_sync cs
                LEFT JOIN events e ON cs.lora_id = e.id
                WHERE cs.lora_type = 'event'
                AND e.id IS NULL
            """)

            # 3. Identify orphaned tasks (missing or done)
            orphaned_tasks = await conn.fetch("""
                SELECT cs.ical_uid FROM calendar_sync cs
                LEFT JOIN tasks t ON cs.lora_id = t.id
                WHERE cs.lora_type = 'task'
                AND (t.id IS NULL OR t.status != 'pending')
            """)

            # 4. Identify orphaned exams (missing)
            orphaned_exams = await conn.fetch("""
                SELECT cs.ical_uid FROM calendar_sync cs
                LEFT JOIN exams ex ON cs.lora_id = ex.id
                WHERE cs.lora_type = 'exam'
                AND ex.id IS NULL
            """)

            all_orphans = [
                r["ical_uid"]
                for r in (
                    orphaned_schedule
                    + orphaned_events
                    + orphaned_tasks
                    + orphaned_exams
                )
            ]

            for uid in all_orphans:
                try:
                    success = await delete_event(uid)
                    if success:
                        # Only remove from our DB if we are sure it's gone from iCloud
                        await calendar_queries.delete_sync_record(pool, uid)
                        stats["deleted"] += 1
                except Exception as e:
                    print(f"Error pruning {uid}: {e}")
                    stats["errors"] += 1

        return stats
    except Exception as e:
        print(f"Cleanup orphans error: {e}")
        return stats


async def sync_from_icloud_to_lora(pool) -> dict:
    """Updates Lora entities based on changes made in iCloud (bi-directional sync)."""
    stats = {"updated": 0, "errors": 0}
    try:
        from datetime import date

        client = get_caldav_client()
        cal = get_lora_calendar(client)
        rem_list = get_reminders_list(client)

        # Collections to scan
        collections = [cal, rem_list]

        for collection in collections:
            # We fetch all components from the collection
            events = collection.events()
            for event_obj in events:
                try:
                    ical = iCal.from_ical(event_obj.data)
                    for component in ical.walk():
                        if component.name not in ("VEVENT", "VTODO"):
                            continue

                        uid = str(component.get("uid"))

                        if "@lora" not in uid:
                            # New item added directly in iCloud
                            summary = str(component.get("summary"))
                            if "🎓" in summary:
                                continue

                            dtstart = component.get("dtstart")
                            dtstart_val = dtstart.dt if dtstart else None

                            if not dtstart_val:
                                due = component.get("due")
                                dtstart_val = due.dt if due else None

                            if not dtstart_val:
                                new_date = date.today()
                                new_time = None
                            else:
                                new_date = (
                                    dtstart_val
                                    if isinstance(dtstart_val, date)
                                    else dtstart_val.date()
                                )
                                new_time = (
                                    None
                                    if isinstance(dtstart_val, date)
                                    else dtstart_val.time()
                                )

                            sync_record = await calendar_queries.get_sync_record_by_uid(
                                pool, uid
                            )
                            if sync_record:
                                continue

                            async with pool.acquire() as conn:
                                if component.name == "VTODO":
                                    # Import as task
                                    new_id = await conn.fetchval(
                                        """
                                        INSERT INTO tasks (title, due_date, status)
                                        VALUES ($1, $2, 'pending')
                                        RETURNING id
                                    """,
                                        summary,
                                        new_date,
                                    )
                                    await calendar_queries.save_sync_record(
                                        pool, "task", new_id, uid, summary
                                    )
                                else:
                                    # Import as event
                                    new_id = await conn.fetchval(
                                        """
                                        INSERT INTO events (title, event_date, event_time, event_type)
                                        VALUES ($1, $2, $3, 'event')
                                        RETURNING id
                                    """,
                                        summary,
                                        new_date,
                                        new_time,
                                    )
                                    await calendar_queries.save_sync_record(
                                        pool, "event", new_id, uid, summary
                                    )
                                stats["updated"] += 1
                            continue

                        # Existing Lora item. Find mapping.
                        sync_record = await calendar_queries.get_sync_record_by_uid(
                            pool, uid
                        )
                        if not sync_record:
                            continue

                        lora_type = sync_record["lora_type"]
                        lora_id = sync_record["lora_id"]

                        if lora_type == "event" and component.name == "VEVENT":
                            summary = str(component.get("summary"))
                            dtstart = component.get("dtstart").dt
                            new_date = (
                                dtstart if isinstance(dtstart, date) else dtstart.date()
                            )
                            new_time = (
                                None if isinstance(dtstart, date) else dtstart.time()
                            )

                            remind_mins = 0
                            remind_1day = False
                            alarms = component.walk("valarm")
                            for a in alarms:
                                trigger = a.get("trigger")
                                if trigger:
                                    td = trigger.dt
                                    mins = int(abs(td.total_seconds()) // 60)
                                    if mins == 1440:
                                        remind_1day = True
                                    elif mins > 0:
                                        remind_mins = mins

                            async with pool.acquire() as conn:
                                current = await conn.fetchrow(
                                    "SELECT title, event_date, event_time, remind_before_minutes, remind_1day FROM events WHERE id = $1",
                                    lora_id,
                                )
                                if current:
                                    clean_summary = (
                                        summary.replace("📅 ", "")
                                        .replace("🔔 ", "")
                                        .strip()
                                    )
                                    changed = (
                                        current["title"] != clean_summary
                                        or current["event_date"] != new_date
                                        or (
                                            current["event_time"] != new_time
                                            and not (
                                                current["event_time"] is None
                                                and new_time is None
                                            )
                                        )
                                        or current["remind_before_minutes"]
                                        != remind_mins
                                        or current["remind_1day"] != remind_1day
                                    )
                                    if changed:
                                        await conn.execute(
                                            """
                                            UPDATE events 
                                            SET title = $1, event_date = $2, event_time = $3, remind_before_minutes = $4, remind_1day = $5, updated_at = NOW()
                                            WHERE id = $6
                                        """,
                                            clean_summary,
                                            new_date,
                                            new_time,
                                            remind_mins,
                                            remind_1day,
                                            lora_id,
                                        )
                                        stats["updated"] += 1

                        elif lora_type == "task" and component.name == "VTODO":
                            summary = (
                                str(component.get("summary"))
                                .replace("📋 Task: ", "")
                                .strip()
                            )
                            if " [" in summary:
                                summary = summary.split(" [")[0]

                            dtstart = component.get("dtstart")
                            dtstart_val = dtstart.dt if dtstart else None
                            if not dtstart_val:
                                due = component.get("due")
                                dtstart_val = due.dt if due else None

                            new_date = (
                                dtstart_val
                                if isinstance(dtstart_val, date)
                                else (dtstart_val.date() if dtstart_val else None)
                            )

                            # Check completion
                            is_completed = False
                            status = component.get("status")
                            if status and str(status).upper() == "COMPLETED":
                                is_completed = True
                            elif component.get("completed"):
                                is_completed = True

                            async with pool.acquire() as conn:
                                current = await conn.fetchrow(
                                    "SELECT title, due_date, status FROM tasks WHERE id = $1 AND deleted_at IS NULL",
                                    lora_id,
                                )
                                if current:
                                    new_status = (
                                        "done" if is_completed else current["status"]
                                    )
                                    if (
                                        current["title"] != summary
                                        or current["due_date"] != new_date
                                        or current["status"] != new_status
                                    ):
                                        await conn.execute(
                                            """
                                            UPDATE tasks 
                                            SET title = $1, due_date = $2, status = $3, completed_at = CASE WHEN $3 = 'done' AND status != 'done' THEN NOW() ELSE completed_at END, updated_at = NOW()
                                            WHERE id = $4
                                        """,
                                            summary,
                                            new_date,
                                            new_status,
                                            lora_id,
                                        )
                                        stats["updated"] += 1
                except Exception as e:
                    print(f"Error syncing back component: {e}")
                    stats["errors"] += 1

        return stats
    except Exception as e:
        print(f"Sync from iCloud error: {e}")
        return stats


async def sync_tasks_to_reminders(pool) -> dict:
    """Syncs Lora tasks to the Lora Calendar as All-Day events (fallback for Upgraded Reminders)."""
    stats = {"created": 0, "skipped": 0, "errors": 0}
    try:
        from core.icloud import get_caldav_client, get_lora_calendar
        from icalendar import Calendar as iCal, Event as iEvent
        import db.queries.calendar as calendar_queries
        from datetime import datetime, date

        client = get_caldav_client()
        target_cal = get_lora_calendar(client)

        # Get pending tasks
        async with pool.acquire() as conn:
            tasks = await conn.fetch("""
                SELECT t.id, t.title, t.due_date, t.notes, p.name as project_name
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.status = 'pending' AND t.deleted_at IS NULL
            """)

        for t in tasks:
            lora_id = t["id"]
            title = t["title"]
            due_date = t["due_date"]  # Might be None
            notes = t["notes"] or ""
            project = t["project_name"] or "Inbox"
            target_date = due_date or date.today()

            # Check if already synced
            sync_record = await calendar_queries.get_sync_record(pool, "task", lora_id)
            if sync_record:
                # If it has no due_date in DB, it should 'follow' us to today
                if not due_date:
                    try:
                        event = target_cal.event_by_uid(sync_record["ical_uid"])
                        # Check if it's already on today
                        # Some versions of caldav return date objects, some return datetimes
                        ev_start = event.vobject_instance.vevent.dtstart.value
                        if isinstance(ev_start, datetime):
                            ev_start = ev_start.date()

                        if ev_start != target_date:
                            event.vobject_instance.vevent.dtstart.value = target_date
                            event.vobject_instance.vevent.dtend.value = target_date
                            event.save()
                            # print(f"Moved undated task {lora_id} to {target_date}")
                    except Exception:
                        # print(f"Error moving task {lora_id}: {e}")
                        pass

                stats["skipped"] += 1
                continue

            # Create VEVENT (All-Day)
            ical = iCal()
            ev = iEvent()

            display_title = f"📋 {title}"
            if project != "Inbox":
                display_title += f" [{project}]"

            ev.add("summary", display_title)
            ev.add("dtstart", target_date)
            ev.add("dtend", target_date)

            if notes:
                ev.add("description", notes)

            import time as pytime

            uid = f"lora-task-cal-{lora_id}-{int(pytime.time())}@lora"
            ev.add("uid", uid)
            ical.add_component(ev)

            try:
                target_cal.save_event(ical.to_ical())
                await calendar_queries.save_sync_record(
                    pool, "task", lora_id, uid, display_title
                )
                stats["created"] += 1
            except Exception as e:
                print(f"Error saving task as event {lora_id}: {e}")
                stats["errors"] += 1

        # Clean up: Remove events for tasks that are no longer pending
        async with pool.acquire() as conn:
            synced_tasks = await conn.fetch(
                "SELECT lora_id, ical_uid FROM calendar_sync WHERE lora_type = 'task'"
            )
            for s in synced_tasks:
                task = await conn.fetchrow(
                    "SELECT id FROM tasks WHERE id = $1 AND status = 'pending' AND deleted_at IS NULL",
                    s["lora_id"],
                )
                if not task:
                    try:
                        event = target_cal.event_by_uid(s["ical_uid"])
                        event.delete()
                        await conn.execute(
                            "DELETE FROM calendar_sync WHERE lora_type = 'task' AND lora_id = $1",
                            s["lora_id"],
                        )
                    except Exception:
                        pass

        return stats
    except Exception as e:
        print(f"Sync tasks to calendar error: {e}")
        return stats

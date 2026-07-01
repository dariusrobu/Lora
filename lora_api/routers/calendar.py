from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict
from datetime import date, timedelta

router = APIRouter(prefix="/api", tags=["calendar"])

DAY_NAMES = ["Luni", "Marți", "Miercuri", "Joi", "Vineri", "Sâmbătă", "Duminică"]


def get_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


async def get_events_for_range(pool, start: date, end: date):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM events
            WHERE event_date BETWEEN $1 AND $2
            ORDER BY event_date, event_time
            """,
            start,
            end,
        )
        return [dict(r) for r in rows]


@router.get("/calendar/week")
async def calendar_week(ref_date: str = None, user=Depends(get_current_user)):
    import db.queries.schedule as sq
    pool = await get_pool()
    try:
        d = date.fromisoformat(ref_date) if ref_date else date.today()
    except ValueError:
        d = date.today()
    monday = get_monday(d)
    sunday = monday + timedelta(days=6)

    events = await get_events_for_range(pool, monday, sunday)
    sched = []
    for i in range(5):
        day = monday + timedelta(days=i)
        try:
            sched.extend(await sq.get_schedule_for_date(pool, day))
        except Exception:
            pass

    days = []
    for i in range(7):
        day = monday + timedelta(days=i)
        day_events = [clean_dict(dict(e)) for e in events if e["event_date"] == day]
        day_sched = [clean_dict(dict(s)) for s in sched if s.get("day_of_week") == i] if sched else []
        days.append({
            "date": day.isoformat(),
            "day_name": DAY_NAMES[i],
            "events": day_events,
            "schedule": day_sched,
        })

    return {"monday": monday.isoformat(), "days": days}


@router.post("/calendar/events")
async def create_event(data: dict, user=Depends(get_current_user)):
    import db.queries.events as q
    pool = await get_pool()
    event_date = date.fromisoformat(data["date"])
    event_time = None
    if data.get("time"):
        from datetime import time
        parts = data["time"].split(":")
        event_time = time(int(parts[0]), int(parts[1]))
    eid = await q.add_event(
        pool,
        title=data["title"],
        event_date=event_date,
        event_time=event_time,
        description=data.get("description"),
        event_type=data.get("type", "event"),
    )
    return {"id": eid, "status": "created"}


@router.delete("/calendar/events/{event_id}")
async def delete_event(event_id: int, user=Depends(get_current_user)):
    import db.queries.events as q
    pool = await get_pool()
    await q.delete_event(pool, event_id)
    return {"status": "deleted"}

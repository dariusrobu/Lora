from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict
from datetime import datetime, timedelta
import pytz
from lora_api.config import TIMEZONE

REVERSE_MOOD_MAP = {5: "great", 4: "good", 3: "okay", 2: "meh", 1: "bad"}

router = APIRouter(prefix="/api", tags=["mood"])


@router.get("/mood")
async def get_mood(user=Depends(get_current_user)):
    import db.queries.mood as q
    pool = await get_pool()
    now = datetime.now(pytz.timezone(TIMEZONE))
    data = await q.get_monthly_mood_data(pool, now.year, now.month)
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    try:
        summary = await q.get_weekly_mood_summary(pool, week_start.date(), week_end.date())
    except Exception:
        summary = {}
    return {
        "monthly": [clean_dict(dict(r)) for r in data],
        "weekly": summary,
    }


@router.get("/mood/monthly")
async def get_mood_monthly(user=Depends(get_current_user)):
    import db.queries.mood as q
    pool = await get_pool()
    now = datetime.now(pytz.timezone(TIMEZONE))
    data = await q.get_monthly_mood_data(pool, now.year, now.month)
    return [{"date": d["date"], "mood": REVERSE_MOOD_MAP.get(d["value"], "okay")} for d in data]


@router.get("/mood/weekly")
async def get_mood_weekly(user=Depends(get_current_user)):
    import db.queries.mood as q
    pool = await get_pool()
    now = datetime.now(pytz.timezone(TIMEZONE))
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    summary = await q.get_weekly_mood_summary(pool, week_start.date(), week_end.date())
    return [{"mood": mood, "count": count} for mood, count in summary.items()]


@router.post("/mood")
async def log_mood(data: dict, user=Depends(get_current_user)):
    from db.queries.mood import log_mood as db_log_mood
    pool = await get_pool()
    await db_log_mood(pool, mood=data.get("mood", "neutral"), notes=data.get("notes"), log_date=data.get("date"))
    return {"status": "logged"}


@router.delete("/mood/{log_date}")
async def delete_mood_entry(log_date: str, user=Depends(get_current_user)):
    from db.queries.mood import delete_mood as db_delete_mood
    pool = await get_pool()
    await db_delete_mood(pool, log_date)
    return {"status": "deleted"}

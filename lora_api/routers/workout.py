from fastapi import APIRouter, Depends, HTTPException
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api/workout", tags=["workout"])


@router.get("/stats")
async def workout_stats(user=Depends(get_current_user)):
    import db.queries.workout as q
    pool = await get_pool()
    stats = await q.get_workout_stats(pool, days=30)
    recent = await q.get_recent_workouts(pool, days=30)
    prs = await q.get_personal_records(pool)
    return {
        "stats": clean_dict(stats),
        "recent": [clean_dict(dict(r)) for r in recent],
        "personal_records": [clean_dict(dict(p)) for p in prs],
    }


@router.post("/log")
async def log_workout(data: dict, user=Depends(get_current_user)):
    import db.queries.workout as q
    from db.queries.sport_types import get_sport_by_name
    from datetime import date
    pool = await get_pool()

    sport_name = data.get("sport_name", "Gym")
    sport = await get_sport_by_name(pool, sport_name)
    if not sport:
        raise HTTPException(status_code=404, detail=f"Sport '{sport_name}' not found")

    workout_date_str = data.get("workout_date")
    if workout_date_str:
        workout_date = date.fromisoformat(workout_date_str)
    else:
        workout_date = date.today()

    wid = await q.log_workout(
        pool,
        workout_date=workout_date,
        sport_id=sport["id"],
        duration_min=data.get("duration_min", 0),
        notes=data.get("notes"),
        calories=data.get("calories"),
    )
    for ex in data.get("exercises", []):
        await q.log_exercise(pool, wid, ex.get("name"), ex.get("sets"), ex.get("reps"), ex.get("weight_kg"))
    return {"id": wid, "status": "logged"}

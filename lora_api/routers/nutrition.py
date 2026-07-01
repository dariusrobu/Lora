from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api", tags=["nutrition"])

MEAL_TYPE_MAP = {
    "breakfast": "mic_dejun", "lunch": "pranz", "dinner": "cina", "snack": "gustare",
    "mic_dejun": "mic_dejun", "pranz": "pranz", "cina": "cina", "gustare": "gustare",
}


def _map_meal(r: dict) -> dict:
    return {
        "id": r["id"],
        "meal_type": r["meal_type"],
        "description": r.get("description", ""),
        "calories": r.get("total_calories", 0),
        "protein": r.get("total_protein", 0),
        "carbs": r.get("total_carbs", 0),
        "fat": r.get("total_fat", 0),
        "created_at": r.get("created_at", ""),
    }


@router.get("/nutrition/daily")
async def get_daily_nutrition(user=Depends(get_current_user)):
    import db.queries.nutrition as q
    from datetime import date
    pool = await get_pool()
    today = date.today()
    meals = await q.get_daily_meals(pool, today)
    totals = await q.get_daily_totals(pool, today)
    targets = await q.get_nutrition_targets(pool)
    return {
        "meals": [clean_dict(_map_meal(dict(r))) for r in meals],
        "totals": clean_dict(totals),
        "targets": clean_dict(targets),
    }


@router.get("/nutrition")
async def get_nutrition(user=Depends(get_current_user)):
    import db.queries.nutrition as q
    from datetime import date
    pool = await get_pool()
    today = date.today()
    daily = await q.get_daily_totals(pool, today)
    targets = await q.get_nutrition_targets(pool)
    return {"daily": clean_dict(daily), "targets": clean_dict(targets)}


@router.post("/nutrition")
async def log_meal(data: dict, user=Depends(get_current_user)):
    import db.queries.nutrition as q
    from datetime import date
    pool = await get_pool()
    meal_type = MEAL_TYPE_MAP.get(data.get("meal_type", ""), "gustare")
    await q.log_meal(
        pool,
        meal_date=date.today(),
        meal_type=meal_type,
        total_macros={
            "calories": data.get("calories", 0),
            "protein": data.get("protein", 0),
            "carbs": data.get("carbs", 0),
            "fat": data.get("fat", 0),
        },
        description=data.get("description", ""),
        items=[],
    )
    return {"status": "logged"}

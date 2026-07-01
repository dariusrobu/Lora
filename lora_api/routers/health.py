from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health/summary")
async def health_summary(days: int = 14, user=Depends(get_current_user)):
    import db.queries.health as q
    pool = await get_pool()
    summary = await q.get_health_summary(pool, days)
    history = await q.get_health_history(pool, days)
    if not summary or summary.get("avg_sleep") is None:
        summary = {
            "avg_sleep": 7.5, "avg_water": 1800,
            "recent_weight": 65, "prev_weight": 65,
            "weight_trend": "stable", "total_days": 0,
        }
    return {
        "summary": clean_dict(summary),
        "history": [clean_dict(dict(r)) for r in history],
    }


@router.post("/health")
async def log_health(data: dict, user=Depends(get_current_user)):
    import db.queries.health as q
    pool = await get_pool()
    await q.upsert_health_log(pool, **data)
    return {"status": "logged"}

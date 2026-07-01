from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api", tags=["insights"])


@router.get("/insights")
async def get_insights(user=Depends(get_current_user)):
    import db.queries.finance as fq
    import db.queries.tasks as tq
    import db.queries.insights as iq
    from datetime import date, timedelta
    pool = await get_pool()
    today = date.today()
    budget = await fq.get_budget_status(pool)
    tasks = await tq.list_tasks(pool, status="pending")
    overdue = [clean_dict(dict(t)) for t in tasks if t.get("due_date") and t["due_date"] < today]
    try:
        pattern = await iq.get_behavioral_patterns(pool, days=30)
    except Exception:
        pattern = {}
    return {
        "budget_alerts": [clean_dict(dict(b)) for b in budget],
        "overdue_tasks": overdue,
        "patterns": pattern,
    }

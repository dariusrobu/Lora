from fastapi import APIRouter, Depends, Query
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict
from datetime import date

router = APIRouter(prefix="/api/finances", tags=["finance"])


@router.get("/summary")
async def finance_summary(month: int | None = None, year: int | None = None, user=Depends(get_current_user)):
    import db.queries.finance as q
    pool = await get_pool()
    from datetime import datetime as dt
    m = month or dt.now().month
    y = year or dt.now().year
    summary = await q.get_monthly_summary(pool, m, y)
    budget = await q.get_budget_status(pool)
    categories = await q.get_monthly_category_totals(pool, m, y)
    return {
        "summary": clean_dict(summary),
        "budget_alerts": [clean_dict(dict(b)) for b in budget],
        "categories": [clean_dict(dict(c)) for c in categories],
    }


@router.get("/chart")
async def finance_chart(days: int = 7, user=Depends(get_current_user)):
    import db.queries.finance as q
    pool = await get_pool()
    rows = await q.get_finance_history(pool, days)
    return [clean_dict(dict(r)) for r in rows]


@router.get("/history")
async def finance_history(limit: int = 20, user=Depends(get_current_user)):
    import db.queries.finance as q
    pool = await get_pool()
    rows = await q.get_recent_transactions(pool, limit)
    return [clean_dict(dict(r)) for r in rows]


@router.post("")
async def log_transaction(data: dict, user=Depends(get_current_user)):
    import db.queries.finance as q
    pool = await get_pool()
    tid = await q.log_transaction(
        pool, amount=data["amount"], category=data.get("category", ""),
        description=data.get("description", ""), tx_type=data.get("type", "expense"),
    )
    return {"id": tid, "status": "created"}


@router.delete("/{tx_id}")
async def delete_transaction(tx_id: int, user=Depends(get_current_user)):
    import db.queries.finance as q
    pool = await get_pool()
    ok = await q.delete_transaction(pool, tx_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"status": "deleted"}

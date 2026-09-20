from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api/finances", tags=["finance"])


@router.get("/summary")
async def finance_summary(month: int | None = None, year: int | None = None, user=Depends(get_current_user)):
    import db.queries.finance as q
    pool = await get_pool()
    from datetime import datetime as dt
    m = month or dt.now().month
    y = year or dt.now().year
    summary = await q.get_monthly_summary(pool, m, y)
    inc = summary.get("income", 0.0)
    exp = summary.get("expense", 0.0)
    summary["balance"] = round(inc - exp, 2)
    summary["monthly_balance"] = round(inc - exp, 2)

    async with pool.acquire() as conn:
        total_row = await conn.fetchrow(
            """
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as total_income,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as total_expense
            FROM finances
            """
        )
        total_balance = float(total_row["total_income"]) - float(total_row["total_expense"])
    summary["total_balance"] = round(total_balance, 2)

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


@router.get("/product-memories")
async def get_product_memories(user=Depends(get_current_user)):
    from db.queries.product_memory import list_product_memories
    pool = await get_pool()
    rows = await list_product_memories(pool)
    return [clean_dict(r) for r in rows]


@router.delete("/product-memories/{mem_id}")
async def remove_product_memory(mem_id: int, user=Depends(get_current_user)):
    from db.queries.product_memory import delete_product_memory
    pool = await get_pool()
    ok = await delete_product_memory(pool, mem_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted"}


@router.get("/merchant-memories")
async def get_merchant_memories(user=Depends(get_current_user)):
    from db.queries.product_memory import list_merchant_memories
    pool = await get_pool()
    rows = await list_merchant_memories(pool)
    return [clean_dict(r) for r in rows]


@router.delete("/merchant-memories/{mem_id}")
async def remove_merchant_memory(mem_id: int, user=Depends(get_current_user)):
    from db.queries.product_memory import delete_merchant_memory
    pool = await get_pool()
    ok = await delete_merchant_memory(pool, mem_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted"}


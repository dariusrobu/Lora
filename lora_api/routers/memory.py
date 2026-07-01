from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api", tags=["memory"])


@router.get("/memory")
async def list_memories(limit: int = 50, user=Depends(get_current_user)):
    import db.queries.memory as q
    pool = await get_pool()
    rows = await q.list_all_memories(pool)
    return [clean_dict(dict(r)) for r in rows[:limit]]


@router.post("/memory")
async def save_memory(data: dict, user=Depends(get_current_user)):
    import db.queries.memory as q
    pool = await get_pool()
    mid = await q.save_memory_fact(
        pool, fact=data["fact"], category=data.get("category", "general"),
        confidence=data.get("confidence", 1.0),
    )
    return {"id": mid, "status": "saved"}


@router.delete("/memory/{fact_id}")
async def delete_memory(fact_id: int, user=Depends(get_current_user)):
    import db.queries.memory as q
    pool = await get_pool()
    await q.delete_fact(pool, fact_id)
    return {"status": "deleted"}

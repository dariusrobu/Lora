from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api", tags=["shopping"])


@router.get("/shopping")
async def list_shopping(user=Depends(get_current_user)):
    import db.queries.shopping as q
    pool = await get_pool()
    rows = await q.list_shopping_items(pool, include_bought=True)
    return [clean_dict(dict(r)) for r in rows]


@router.post("/shopping")
async def add_shopping_item(data: dict, user=Depends(get_current_user)):
    import db.queries.shopping as q
    pool = await get_pool()
    sid = await q.add_shopping_item(pool, data["item"], data.get("category"))
    return {"id": sid, "status": "created"}


@router.patch("/shopping/{item_id}")
async def toggle_shopping_item(item_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.shopping as q
    pool = await get_pool()
    await q.toggle_item_status(pool, item_id, data.get("is_bought", True))
    return {"status": "updated"}


@router.delete("/shopping/{item_id}")
async def delete_shopping_item(item_id: int, user=Depends(get_current_user)):
    import db.queries.shopping as q
    pool = await get_pool()
    await q.delete_item_by_id(pool, item_id)
    return {"status": "deleted"}


@router.delete("/shopping/clear")
async def clear_shopping(user=Depends(get_current_user)):
    import db.queries.shopping as q
    pool = await get_pool()
    await q.clear_bought_items(pool)
    return {"status": "cleared"}

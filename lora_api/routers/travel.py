from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api/travel", tags=["travel"])


@router.get("/lists")
async def get_travel_lists(user=Depends(get_current_user)):
    import db.queries.travel as q
    pool = await get_pool()
    lists = await q.get_all_travel_lists(pool)
    result = {}
    for lst in lists:
        items = await q.get_travel_items(pool, lst)
        result[lst] = [clean_dict(dict(i)) for i in items]
    return result


@router.get("/items")
async def get_travel_items(list_name: str, user=Depends(get_current_user)):
    import db.queries.travel as q
    pool = await get_pool()
    items = await q.get_travel_items(pool, list_name)
    return [clean_dict(dict(i)) for i in items]


@router.patch("/items/{item_id}")
async def toggle_packed(item_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.travel as q
    pool = await get_pool()
    await q.toggle_packed_status(pool, item_id, data.get("is_packed", True))
    return {"status": "updated"}

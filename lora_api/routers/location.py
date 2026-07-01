from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict
from lora_api.config import TELEGRAM_USER_ID

router = APIRouter(prefix="/api", tags=["location"])


@router.get("/places")
async def get_places(user=Depends(get_current_user)):
    import db.queries.locations as q
    pool = await get_pool()
    rows = await q.list_saved_locations(pool, TELEGRAM_USER_ID)
    return [clean_dict(dict(r)) for r in rows]


@router.post("/places")
async def save_place(data: dict, user=Depends(get_current_user)):
    import db.queries.locations as q
    pool = await get_pool()
    pid = await q.add_saved_location(
        pool, TELEGRAM_USER_ID, name=data["name"],
        lat=data["lat"], lon=data["lon"],
        address=data.get("address"),
    )
    return {"id": pid, "status": "saved"}

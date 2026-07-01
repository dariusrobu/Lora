from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api", tags=["focus"])


@router.get("/focus/status")
async def focus_status(user=Depends(get_current_user)):
    return {"active": False, "message": "Focus via Telegram bot"}


@router.post("/focus/start")
async def start_focus(data: dict, user=Depends(get_current_user)):
    import db.queries.focus as q
    pool = await get_pool()
    sid = await q.start_session(pool, data.get("duration_min", 25), data.get("task_description"))
    return {"id": sid, "status": "started"}

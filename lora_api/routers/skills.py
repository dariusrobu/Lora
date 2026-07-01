from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("")
async def list_skills(user=Depends(get_current_user)):
    import db.queries.skills as q
    pool = await get_pool()
    rows = await q.get_all_skills(pool)
    return [clean_dict(dict(r)) for r in rows]


@router.post("/log")
async def log_skill(data: dict, user=Depends(get_current_user)):
    import db.queries.skills as q
    pool = await get_pool()
    skill = await q.get_skill_by_name(pool, data["skill_name"])
    if not skill:
        sid = await q.add_skill(pool, data["skill_name"])
    else:
        sid = skill["id"]
    log_id = await q.log_skill_value(pool, sid, data.get("value", 1))
    return {"id": log_id, "status": "logged"}

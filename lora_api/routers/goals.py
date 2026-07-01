from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api", tags=["goals"])


@router.get("/goals")
async def list_goals(user=Depends(get_current_user)):
    import db.queries.goals as q
    pool = await get_pool()
    rows = await q.get_all_goals(pool)
    return [clean_dict(dict(r)) for r in rows]


@router.post("/goals")
async def create_goal(data: dict, user=Depends(get_current_user)):
    import db.queries.goals as q
    pool = await get_pool()
    gid = await q.add_goal(
        pool, title=data["title"],
        description=data.get("description"),
        category=data.get("category", "general"),
        time_horizon=data.get("time_horizon", "month"),
    )
    return {"id": gid, "status": "created"}


@router.patch("/goals/{goal_id}")
async def update_goal(goal_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.goals as q
    pool = await get_pool()
    await q.update_goal(pool, goal_id, **data)
    return {"status": "updated"}


@router.post("/goals/{goal_id}/complete")
async def complete_goal(goal_id: int, user=Depends(get_current_user)):
    import db.queries.goals as q
    pool = await get_pool()
    await q.complete_goal(pool, goal_id)
    return {"status": "completed"}


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: int, user=Depends(get_current_user)):
    import db.queries.goals as q
    pool = await get_pool()
    await q.delete_goal(pool, goal_id)
    return {"status": "deleted"}


@router.post("/goals/{goal_id}/subtasks")
async def add_subtask(goal_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.goals as q
    pool = await get_pool()
    sid = await q.add_subtask(pool, goal_id, data["title"])
    return {"id": sid, "status": "created"}


@router.post("/goals/subtasks/{subtask_id}/toggle")
async def toggle_subtask(subtask_id: int, user=Depends(get_current_user)):
    import db.queries.goals as q
    pool = await get_pool()
    await q.complete_subtask(pool, subtask_id)
    return {"status": "toggled"}


@router.delete("/goals/subtasks/{subtask_id}")
async def delete_subtask(subtask_id: int, user=Depends(get_current_user)):
    import db.queries.goals as q
    pool = await get_pool()
    await q.delete_subtask(pool, subtask_id)
    return {"status": "deleted"}

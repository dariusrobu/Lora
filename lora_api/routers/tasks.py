from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict
from fastapi import HTTPException

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(status: str | None = None, project_id: int | None = None, user=Depends(get_current_user)):
    import db.queries.tasks as q
    pool = await get_pool()
    if status == "all":
        status = None
    rows = await q.list_tasks(pool, status=status, project_id=project_id)
    return [clean_dict(dict(r)) for r in rows]


@router.post("")
async def create_task(data: dict, user=Depends(get_current_user)):
    import db.queries.tasks as q
    pool = await get_pool()
    tid = await q.add_task(
        pool, title=data["title"], due_date=data.get("due_date"),
        project_id=data.get("project_id"), priority=data.get("priority", "medium"),
    )
    return {"id": tid, "status": "created"}


@router.patch("/{task_id}")
async def update_task(task_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.tasks as q
    pool = await get_pool()
    await q.update_task(pool, task_id, **data)
    return {"status": "updated"}


@router.delete("/{task_id}")
async def delete_task(task_id: int, user=Depends(get_current_user)):
    import db.queries.tasks as q
    pool = await get_pool()
    await q.delete_task(pool, task_id)
    return {"status": "deleted"}


@router.post("/{task_id}/complete")
async def complete_task(task_id: int, user=Depends(get_current_user)):
    import db.queries.tasks as q
    pool = await get_pool()
    await q.complete_task(pool, task_id)
    return {"status": "completed"}


@router.post("/{task_id}/move")
async def move_task(task_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.tasks as q
    direction = data.get("direction")
    if direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail="direction must be 'up' or 'down'")
    pool = await get_pool()
    ok = await q.move_task(pool, task_id, direction)
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot move further")
    return {"status": "moved"}

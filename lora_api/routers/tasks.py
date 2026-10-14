from datetime import date, time
from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user, require_standd_token
from lora_api.database import get_pool
from lora_api.serializers import clean_dict
from fastapi import HTTPException

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", dependencies=[Depends(require_standd_token)])
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
    due_date = data.get("due_date")
    due_time = data.get("due_time")
    if isinstance(due_date, str) and due_date:
        try:
            due_date = date.fromisoformat(due_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="due_date must use YYYY-MM-DD") from exc
    if isinstance(due_time, str) and due_time:
        try:
            due_time = time.fromisoformat(due_time)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="due_time must use HH:MM") from exc
    tid = await q.add_task(
        pool, title=data["title"], due_date=due_date, due_time=due_time,
        description=data.get("description"),
        project_id=data.get("project_id"), priority=data.get("priority", "medium"),
        university_subject_id=data.get("university_subject_id"),
        class_type=data.get("class_type", "curs"),
        tags=[str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()],
    )
    return {"id": tid, "status": "created"}


@router.patch("/{task_id}")
async def update_task(task_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.tasks as q
    allowed = {"title", "description", "due_date", "due_time", "priority", "class_type", "tags", "status", "project_id"}
    data = {k: v for k, v in data.items() if k in allowed}
    if not data:
        raise HTTPException(status_code=422, detail="Nu există câmpuri de actualizat")
    if data.get("priority") not in (None, "low", "medium", "high"):
        raise HTTPException(status_code=422, detail="priority invalid")
    if data.get("status") not in (None, "pending", "done"):
        raise HTTPException(status_code=422, detail="status invalid")
    if isinstance(data.get("due_date"), str) and data["due_date"]:
        try:
            data = {**data, "due_date": date.fromisoformat(data["due_date"])}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="due_date must use YYYY-MM-DD") from exc
    if isinstance(data.get("due_time"), str) and data["due_time"]:
        try:
            data = {**data, "due_time": time.fromisoformat(data["due_time"])}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="due_time must use HH:MM") from exc
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

from fastapi import APIRouter, Depends, HTTPException
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects(user=Depends(get_current_user)):
    import db.queries.projects as q
    pool = await get_pool()
    rows = await q.get_projects_with_counts(pool)
    return [clean_dict(dict(r)) for r in rows]


@router.post("")
async def create_project(data: dict, user=Depends(get_current_user)):
    import db.queries.projects as q
    pool = await get_pool()
    pid = await q.add_project(
        pool,
        name=data["name"],
        description=data.get("description"),
        status=data.get("status", "active"),
        deadline=data.get("deadline"),
        priority=data.get("priority", "medium"),
        category=data.get("category"),
    )
    return {"id": pid, "status": "created"}


@router.get("/{project_id}")
async def get_project(project_id: int, user=Depends(get_current_user)):
    import db.queries.projects as q
    pool = await get_pool()
    proj = await q.get_project_detail(pool, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return clean_dict(proj)


@router.patch("/{project_id}")
async def update_project(project_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.projects as q
    pool = await get_pool()
    await q.update_project(pool, project_id, **data)
    return {"status": "updated"}


@router.delete("/{project_id}")
async def delete_project(project_id: int, user=Depends(get_current_user)):
    import db.queries.projects as q
    pool = await get_pool()
    await q.delete_project(pool, project_id)
    return {"status": "deleted"}

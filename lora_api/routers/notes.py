from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api", tags=["notes"])


@router.get("/notes")
async def list_notes(user=Depends(get_current_user)):
    import db.queries.notes as q
    pool = await get_pool()
    rows = await q.list_notes(pool)
    return [clean_dict(dict(r)) for r in rows]


@router.post("/notes")
async def create_note(data: dict, user=Depends(get_current_user)):
    import db.queries.notes as q
    pool = await get_pool()
    nid = await q.add_note(
        pool,
        content=data.get("content") or data.get("title", ""),
        type=data.get("type", "note"),
        tags=data.get("tags", []),
        project_id=data.get("project_id"),
    )
    return {"id": nid, "status": "created"}


@router.delete("/notes/{note_id}")
async def delete_note(note_id: int, user=Depends(get_current_user)):
    import db.queries.notes as q
    pool = await get_pool()
    await q.delete_note(pool, note_id)
    return {"status": "deleted"}

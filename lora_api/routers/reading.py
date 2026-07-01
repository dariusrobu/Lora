from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict

router = APIRouter(prefix="/api", tags=["reading"])


@router.get("/reading")
async def list_reading(user=Depends(get_current_user)):
    import db.queries.reading as q
    pool = await get_pool()
    rows = await q.get_all_books(pool)
    stats = await q.get_reading_stats(pool)
    return {"books": [clean_dict(dict(r)) for r in rows], "stats": clean_dict(stats)}


@router.post("/reading")
async def add_book(data: dict, user=Depends(get_current_user)):
    import db.queries.reading as q
    pool = await get_pool()
    bid = await q.add_book(pool, data["title"], data.get("author"), data.get("total_pages"))
    return {"id": bid, "status": "created"}


@router.patch("/reading/{book_id}")
async def update_book(book_id: int, data: dict, user=Depends(get_current_user)):
    import db.queries.reading as q
    pool = await get_pool()
    if "pages_read" in data:
        await q.update_progress(pool, book_id, data["pages_read"])
    if "status" in data and data["status"] == "completed":
        await q.complete_book(pool, book_id, data.get("rating"))
    return {"status": "updated"}

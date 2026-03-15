from typing import List, Dict, Any, Optional

async def add_shopping_item(pool, item: str, category: Optional[str] = None):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO shopping_list (item, category) VALUES ($1, $2)",
            item, category
        )

async def list_shopping_items(pool) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM shopping_list WHERE is_bought = FALSE ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]

async def mark_item_bought(pool, item_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE shopping_list SET is_bought = TRUE, updated_at = NOW() WHERE id = $1",
            item_id
        )

async def delete_item_by_name(pool, item_name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM shopping_list WHERE item ILIKE $1",
            f"%{item_name}%"
        )

async def clear_bought_items(pool):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM shopping_list WHERE is_bought = TRUE")

from typing import List, Dict, Any, Optional


async def add_shopping_item(pool, item: str, category: Optional[str] = None) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO shopping_list (item, category) VALUES ($1, $2) RETURNING id",
            item,
            category,
        )


async def delete_item_by_id(pool, item_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM shopping_list WHERE id = $1", item_id)


async def list_shopping_items(pool, include_bought=True) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        query = "SELECT * FROM shopping_list ORDER BY is_bought ASC, updated_at DESC"
        if not include_bought:
            query = "SELECT * FROM shopping_list WHERE is_bought = FALSE ORDER BY updated_at DESC"
        rows = await conn.fetch(query)
        return [dict(r) for r in rows]


async def mark_item_bought(pool, item_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE shopping_list SET is_bought = TRUE, updated_at = NOW() WHERE id = $1",
            item_id,
        )


async def toggle_item_status(pool, item_id: int, is_bought: bool):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE shopping_list SET is_bought = $2, updated_at = NOW() WHERE id = $1",
            item_id,
            is_bought,
        )


async def delete_item_by_name(pool, item_name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM shopping_list WHERE item ILIKE $1", f"%{item_name}%"
        )


async def clear_bought_items(pool):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM shopping_list WHERE is_bought = TRUE")

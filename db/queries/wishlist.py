from typing import List, Dict, Any, Optional
import asyncpg

async def add_wish_item(
    pool, 
    user_id: int, 
    item: str, 
    description: Optional[str] = None, 
    price: Optional[float] = None, 
    category: Optional[str] = 'altele', 
    priority: Optional[str] = 'medium'
) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO wishlist (user_id, item, description, price, category, priority)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            user_id, item, description, price, category, priority
        )
        return row['id']

async def list_wish_items(pool, user_id: int, status: str = 'pending') -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM wishlist WHERE user_id = $1 AND status = $2 ORDER BY priority DESC, created_at DESC",
            user_id, status
        )
        return [dict(r) for r in rows]

async def update_wish_status(pool, item_id: int, status: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE wishlist SET status = $2, updated_at = NOW() WHERE id = $1",
            item_id, status
        )

async def delete_wish_item(pool, user_id: int, item_query: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM wishlist WHERE user_id = $1 AND item ILIKE $2",
            user_id, f"%{item_query}%"
        )

async def delete_wish_item_by_id(pool, item_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM wishlist WHERE id = $1", item_id)


async def get_wish_item(pool, item_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM wishlist WHERE id = $1", item_id)
        return dict(row) if row else None

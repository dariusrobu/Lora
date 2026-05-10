from typing import List, Dict, Any, Optional

async def add_travel_item(pool, item: str, list_name: str, category: Optional[str] = None, trip_type: str = 'both'):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO travel_items (item, list_name, category, trip_type) VALUES ($1, $2, $3, $4)",
            item, list_name, category, trip_type
        )

async def get_travel_items(pool, list_name: str, trip_type: Optional[str] = None) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        query = "SELECT * FROM travel_items WHERE list_name ILIKE $1"
        args = [list_name]
        
        if trip_type and trip_type != 'both':
            query += " AND (trip_type = $2 OR trip_type = 'both')"
            args.append(trip_type)
            
        query += " ORDER BY is_packed ASC, created_at ASC"
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]

async def toggle_packed_status(pool, item_id: int, is_packed: bool):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE travel_items SET is_packed = $1, updated_at = NOW() WHERE id = $2",
            is_packed, item_id
        )

async def mark_item_packed_by_name(pool, list_name: str, item_name: str):
    async with pool.acquire() as conn:
        # Fuzzy match item name within the list
        await conn.execute(
            "UPDATE travel_items SET is_packed = TRUE, updated_at = NOW() WHERE list_name ILIKE $1 AND item ILIKE $2",
            list_name, f"%{item_name}%"
        )

async def clear_travel_list(pool, list_name: str, reset_only: bool = False):
    async with pool.acquire() as conn:
        if reset_only:
            await conn.execute(
                "UPDATE travel_items SET is_packed = FALSE, updated_at = NOW() WHERE list_name ILIKE $1",
                list_name
            )
        else:
            await conn.execute(
                "DELETE FROM travel_items WHERE list_name ILIKE $1",
                list_name
            )

async def delete_travel_item(pool, item_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM travel_items WHERE id = $1", item_id)

async def get_all_travel_lists(pool) -> List[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT list_name FROM travel_items ORDER BY list_name ASC")
        return [r["list_name"] for r in rows]

from typing import List, Dict, Any, Optional

async def add_saved_location(pool, user_id: int, name: str, lat: float, lon: float, radius: int = 200):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO saved_locations (user_id, name, latitude, longitude, radius_meters)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, name) DO UPDATE 
            SET latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude, radius_meters = EXCLUDED.radius_meters
            """,
            user_id, name, lat, lon, radius
        )

async def list_saved_locations(pool, user_id: int) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM saved_locations WHERE user_id = $1 ORDER BY name ASC",
            user_id
        )
        return [dict(r) for r in rows]

async def delete_saved_location(pool, user_id: int, name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM saved_locations WHERE user_id = $1 AND name ILIKE $2",
            user_id, name
        )

async def get_location_by_name(pool, user_id: int, name: str) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM saved_locations WHERE user_id = $1 AND name ILIKE $2",
            user_id, name
        )
        return dict(row) if row else None

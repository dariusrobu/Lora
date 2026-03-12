from typing import List, Optional, Dict, Any

async def add_project(pool, name: str, description: Optional[str] = None, status: str = "active") -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO projects (name, description, status) VALUES ($1, $2, $3) RETURNING id",
            name, description, status
        )
        return row['id']

async def get_project(pool, project_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM projects WHERE id = $1", project_id)
        return dict(row) if row else None

async def list_projects(pool, status_not: str = "archived") -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM projects WHERE status != $1 ORDER BY updated_at DESC",
            status_not
        )
        return [dict(r) for r in rows]

async def update_project(pool, project_id: int, **kwargs):
    if not kwargs: return
    fields = [f"{k} = ${i}" for i, k in enumerate(kwargs.keys(), start=2)]
    query = f"UPDATE projects SET {', '.join(fields)}, updated_at = NOW() WHERE id = $1"
    async with pool.acquire() as conn:
        await conn.execute(query, project_id, *kwargs.values())

async def delete_project(pool, project_id: int):
    async with pool.acquire() as conn:
        # Note: schema.sql uses ON DELETE SET NULL for linked items
        await conn.execute("DELETE FROM projects WHERE id = $1", project_id)

from typing import Optional, Dict, Any, List


async def get_backup_config(pool) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM backup_config ORDER BY id LIMIT 1")
    return dict(row) if row else None


async def update_backup_config(pool, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sets = []
    params = []
    idx = 1
    for col in ("enabled", "schedule_cron", "retention_days"):
        if col in data:
            sets.append(f"{col} = ${idx}")
            params.append(data[col])
            idx += 1
    if not sets:
        return None
    sets.append("updated_at = NOW()")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE backup_config SET {', '.join(sets)} WHERE id = 1 RETURNING *",
            *params,
        )
    return dict(row) if row else None


async def get_backup_logs(pool, limit: int = 50) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM backup_log ORDER BY created_at DESC LIMIT $1", limit
        )
    return [dict(r) for r in rows]


async def create_backup_log(pool, status: str = "pending") -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO backup_log (status) VALUES ($1) RETURNING id", status
        )
    return row["id"]


async def update_backup_log(pool, log_id: int, data: Dict[str, Any]):
    sets = []
    params = []
    idx = 1
    for col in ("status", "file_name", "file_size_bytes", "error_message", "completed_at"):
        if col in data:
            sets.append(f"{col} = ${idx}")
            params.append(data[col])
            idx += 1
    if not sets:
        return
    params.append(log_id)
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE backup_log SET {', '.join(sets)} WHERE id = ${idx}",
            *params,
        )

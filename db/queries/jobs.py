from typing import Optional, Dict, Any, List


async def get_all_jobs(pool) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM job_config ORDER BY job_name"
        )
    return [dict(r) for r in rows]


async def update_job(pool, job_name: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sets = []
    params = []
    idx = 1
    for col in ("enabled", "cron_time"):
        if col in data:
            sets.append(f"{col} = ${idx}")
            params.append(data[col])
            idx += 1
    if not sets:
        return None
    sets.append(f"updated_at = NOW()")
    params.append(job_name)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE job_config SET {', '.join(sets)} WHERE job_name = ${idx} RETURNING *",
            *params,
        )
    return dict(row) if row else None


async def sync_jobs(pool, default_jobs: List[Dict[str, Any]]):
    async with pool.acquire() as conn:
        for job in default_jobs:
            await conn.execute(
                """INSERT INTO job_config (job_name, enabled, cron_time)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (job_name) DO NOTHING""",
                job["job_name"], job.get("enabled", True), job.get("cron_time"),
            )

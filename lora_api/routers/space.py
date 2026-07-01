import asyncio
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict
from lora_api.config import TELEGRAM_USER_ID

router = APIRouter(prefix="/api", tags=["space"])


@router.get("/correlations")
async def get_correlations(user=Depends(get_current_user)):
    from core.correlations import compute_correlations
    pool = await get_pool()
    results = await compute_correlations(pool)
    return results


@router.get("/correlations/history")
async def get_correlation_history(user=Depends(get_current_user)):
    import db.queries.memory as q
    pool = await get_pool()
    rows = await q.list_all_memories(pool)
    return [clean_dict(dict(r)) for r in rows if r.get("category") == "pattern"]


@router.get("/timeline")
async def get_timeline(
    days: int = Query(default=7, le=90),
    module: Optional[str] = None,
    user=Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if module:
            rows = await conn.fetch(
                """SELECT intent, module, success, error_message, created_at
                   FROM execution_log
                   WHERE module = $1 AND created_at >= NOW() - ($2 || ' days')::INTERVAL
                   ORDER BY created_at DESC LIMIT 100""",
                module, str(days),
            )
        else:
            rows = await conn.fetch(
                """SELECT intent, module, success, error_message, created_at
                   FROM execution_log
                   WHERE created_at >= NOW() - ($1 || ' days')::INTERVAL
                   ORDER BY created_at DESC LIMIT 200""",
                str(days),
            )
    return [clean_dict(dict(r)) for r in rows]


@router.get("/profile/behavior")
async def get_behavior(user=Depends(get_current_user)):
    import db.queries.profile as q
    pool = await get_pool()
    profile = await q.get_user_profile(pool, TELEGRAM_USER_ID)
    return {
        "frequent_categories": profile.get("frequent_categories", {}) if profile else {},
    }


# ---- Phase 3: Jobs ----

@router.get("/jobs")
async def list_jobs(user=Depends(get_current_user)):
    import db.queries.jobs as q
    pool = await get_pool()
    return await q.get_all_jobs(pool)


@router.put("/jobs/{job_name}")
async def update_job(job_name: str, body: dict, user=Depends(get_current_user)):
    import db.queries.jobs as q
    pool = await get_pool()
    result = await q.update_job(pool, job_name, body)
    if not result:
        raise HTTPException(404, "Job not found")
    return result


@router.post("/jobs/sync")
async def sync_jobs(user=Depends(get_current_user)):
    import db.queries.jobs as q
    pool = await get_pool()
    default_jobs = [
        {"job_name": "morning_briefing", "cron_time": "0 5 * * *"},
        {"job_name": "eod_reflection", "cron_time": "0 21 * * *"},
        {"job_name": "weekly_review", "cron_time": "0 21 * * 0"},
        {"job_name": "monthly_review", "cron_time": "0 20 1 * *"},
        {"job_name": "weekly_finance", "cron_time": "0 7 * * 1"},
        {"job_name": "budget_reset", "cron_time": "0 0 1 * *"},
        {"job_name": "proactive_insights", "cron_time": "0 9,9:30 * * *"},
        {"job_name": "history_cleanup", "cron_time": "0 4 * * *"},
        {"job_name": "profile_update", "cron_time": "0 6 * * 1"},
        {"job_name": "habit_reminder", "cron_time": "0 18 * * *"},
        {"job_name": "task_deadline_reminder", "cron_time": "0 9 * * *"},
        {"job_name": "budget_forecast", "cron_time": "0 9 * * 4"},
        {"job_name": "weather_alerts", "cron_time": "0 */3 * * *"},
        {"job_name": "shopping_cleanup", "cron_time": "0 0 * * *"},
        {"job_name": "calendar_sync", "cron_time": "*/15 * * * *"},
    ]
    await q.sync_jobs(pool, default_jobs)
    return {"ok": True, "count": len(default_jobs)}


# ---- Phase 3: Logs ----

@router.get("/logs/stats")
async def get_log_stats(
    days: int = Query(default=7, le=90),
    user=Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM execution_log WHERE created_at >= NOW() - ($1 || ' days')::INTERVAL",
            str(days),
        )
        errors = await conn.fetchval(
            "SELECT COUNT(*) FROM execution_log WHERE created_at >= NOW() - ($1 || ' days')::INTERVAL AND success = FALSE",
            str(days),
        )
        by_module = await conn.fetch(
            """SELECT module, COUNT(*) as total,
                      SUM(CASE WHEN success THEN 0 ELSE 1 END) as errors
               FROM execution_log
               WHERE created_at >= NOW() - ($1 || ' days')::INTERVAL
               GROUP BY module ORDER BY total DESC""",
            str(days),
        )
        top_errors = await conn.fetch(
            """SELECT error_message, COUNT(*) as count
               FROM execution_log
               WHERE created_at >= NOW() - ($1 || ' days')::INTERVAL
                 AND success = FALSE AND error_message IS NOT NULL
               GROUP BY error_message ORDER BY count DESC LIMIT 10""",
            str(days),
        )
    return {
        "total": total,
        "errors": errors,
        "success_rate": round((total - errors) / total * 100, 1) if total else 100,
        "by_module": [clean_dict(dict(r)) for r in by_module],
        "top_errors": [clean_dict(dict(r)) for r in top_errors],
    }


@router.get("/logs")
async def get_logs(
    days: int = Query(default=7, le=90),
    module: Optional[str] = None,
    success: Optional[bool] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_current_user),
):
    pool = await get_pool()
    where = ["created_at >= NOW() - ($1 || ' days')::INTERVAL"]
    params = [str(days)]
    idx = 2
    if module:
        where.append(f"module = ${idx}")
        params.append(module)
        idx += 1
    if success is not None:
        where.append(f"success = ${idx}")
        params.append(success)
        idx += 1
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            f"SELECT COUNT(*) FROM execution_log WHERE {' AND '.join(where)}",
            *params,
        )
        rows = await conn.fetch(
            f"SELECT * FROM execution_log WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            *params, limit, offset,
        )
    return {
        "total": count,
        "offset": offset,
        "limit": limit,
        "entries": [clean_dict(dict(r)) for r in rows],
    }


# ---- Phase 3: Calendar Sync ----

@router.get("/calendar-sync/status")
async def get_calendar_sync_status(user=Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM calendar_sync")
        by_type = await conn.fetch(
            "SELECT lora_type, COUNT(*) as count FROM calendar_sync GROUP BY lora_type ORDER BY count DESC"
        )
        last_sync = await conn.fetchrow(
            "SELECT synced_at, lora_type, lora_id, summary FROM calendar_sync ORDER BY synced_at DESC LIMIT 1"
        )
        recent_errors = await conn.fetch(
            "SELECT * FROM calendar_sync WHERE error_message IS NOT NULL ORDER BY synced_at DESC LIMIT 20"
        )
    return {
        "total_synced": total,
        "by_type": [clean_dict(dict(r)) for r in by_type],
        "last_sync": clean_dict(dict(last_sync)) if last_sync else None,
        "recent_errors": [clean_dict(dict(r)) for r in recent_errors],
    }


@router.get("/calendar-sync/history")
async def get_calendar_sync_history(
    limit: int = Query(default=50, le=200),
    user=Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM calendar_sync ORDER BY synced_at DESC LIMIT $1", limit
        )
    return [clean_dict(dict(r)) for r in rows]


@router.post("/calendar-sync/trigger")
async def trigger_calendar_sync(user=Depends(get_current_user)):
    pool = await get_pool()
    try:
        from core.icloud import (
            cleanup_calendar_orphans, sync_university_schedule_to_calendar,
            sync_events_table_to_calendar, sync_tasks_with_deadlines,
            sync_exams_to_calendar, sync_tasks_to_reminders, sync_from_icloud_to_lora,
        )
        await asyncio.gather(
            cleanup_calendar_orphans(pool),
            sync_university_schedule_to_calendar(pool),
            sync_events_table_to_calendar(pool),
            sync_tasks_with_deadlines(pool),
            sync_exams_to_calendar(pool),
            sync_tasks_to_reminders(pool),
            sync_from_icloud_to_lora(pool),
        )
        return {"ok": True, "message": "Calendar sync completed"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ---- Phase 3: Export ----

EXPORT_MODULES = {
    "tasks": ("tasks", "created_at"),
    "finance": ("transactions", "transaction_date"),
    "health": ("health_logs", "log_date"),
    "workout": ("workout_sessions", "workout_date"),
    "mood": ("mood_logs", "log_date"),
    "notes": ("notes", "created_at"),
    "goals": ("goals", "created_at"),
    "reading": ("books", "created_at"),
    "events": ("events", "event_date"),
    "shopping": ("shopping_list", "created_at"),
    "university": ("university_schedule", "created_at"),
}


@router.get("/export/{module}")
async def export_module(
    module: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    if module not in EXPORT_MODULES:
        raise HTTPException(404, f"Unknown module: {module}")
    table, date_col = EXPORT_MODULES[module]
    pool = await get_pool()
    where = []
    params = []
    idx = 1
    if start_date:
        where.append(f"{date_col} >= ${idx}")
        params.append(start_date)
        idx += 1
    if end_date:
        where.append(f"{date_col} <= ${idx}")
        params.append(end_date)
        idx += 1
    where_clause = " AND ".join(where) if where else "TRUE"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM {table} WHERE {where_clause} ORDER BY {date_col} DESC LIMIT 10000",
            *params,
        )
    return [clean_dict(dict(r)) for r in rows]


# ---- Phase 3: Backups ----

@router.get("/backups/config")
async def get_backup_config(user=Depends(get_current_user)):
    import db.queries.backup as q
    pool = await get_pool()
    config = await q.get_backup_config(pool)
    if not config:
        return {"enabled": False, "schedule_cron": "0 4 * * 0", "retention_days": 30}
    return clean_dict(config)


@router.put("/backups/config")
async def update_backup_config(body: dict, user=Depends(get_current_user)):
    import db.queries.backup as q
    pool = await get_pool()
    result = await q.update_backup_config(pool, body)
    if not result:
        raise HTTPException(404, "Backup config not found")
    return clean_dict(result)


@router.get("/backups")
async def list_backups(user=Depends(get_current_user)):
    import db.queries.backup as q
    pool = await get_pool()
    return await q.get_backup_logs(pool, limit=50)


@router.post("/backups")
async def trigger_backup(user=Depends(get_current_user)):
    import db.queries.backup as q
    import subprocess, os, datetime
    pool = await get_pool()
    log_id = await q.create_backup_log(pool, "running")
    try:
        from lora_api.config import DATABASE_URL
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"lora_backup_{ts}.sql"
        result = subprocess.run(
            ["pg_dump", DATABASE_URL, "--no-owner", "--no-acl", "-f", filename],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            size = os.path.getsize(filename)
            await q.update_backup_log(pool, log_id, {
                "status": "success", "file_name": filename,
                "file_size_bytes": size, "completed_at": datetime.datetime.now(),
            })
            return {"ok": True, "file_name": filename, "size_bytes": size}
        else:
            raise Exception(result.stderr[:500])
    except Exception as e:
        await q.update_backup_log(pool, log_id, {
            "status": "failed", "error_message": str(e), "completed_at": datetime.datetime.now(),
        })
        return {"ok": False, "error": str(e)}

from typing import List, Optional, Dict, Any
from datetime import date, timedelta

async def add_habit(pool, name: str, frequency: str = "daily", target_days: Optional[List[str]] = None) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO habits (name, frequency, target_days)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            name, frequency, target_days
        )
        return row['id']

async def get_habit(pool, habit_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM habits WHERE id = $1", habit_id)
        return dict(row) if row else None

async def list_habits(pool, is_active: bool = True) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM habits WHERE is_active = $1 ORDER BY created_at ASC",
            is_active
        )
        return [dict(r) for r in rows]

async def log_habit(pool, habit_id: int, log_date: date, status: str, note: Optional[str] = None):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO habit_logs (habit_id, log_date, status, note)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (habit_id, log_date) DO UPDATE 
            SET status = EXCLUDED.status, note = EXCLUDED.note, created_at = NOW()
            """,
            habit_id, log_date, status, note
        )
    await recalculate_streak(pool, habit_id)

async def delete_habit(pool, habit_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM habits WHERE id = $1", habit_id)

async def recalculate_streak(pool, habit_id: int):
    """
    Recalculates current and longest streaks for a habit.
    Simplified version for the initial implementation.
    """
    async with pool.acquire() as conn:
        # Get habit info
        habit = await conn.fetchrow("SELECT frequency, target_days, forgiveness_window FROM habits WHERE id = $1", habit_id)
        if not habit: return
        
        # Get logs in descending order
        logs = await conn.fetch(
            "SELECT log_date, status FROM habit_logs WHERE habit_id = $1 ORDER BY log_date DESC",
            habit_id
        )
        
        current_streak = 0
        # Basic logic: count backwards from today/yesterday for consecutive 'done'
        # In a real implementation, this handles 'skipped' and forgiveness windows
        for log in logs:
            if log['status'] == 'done':
                current_streak += 1
            elif log['status'] == 'skipped':
                continue # Skip doesn't break nor increase streak
            else:
                break
        
        await conn.execute(
            "UPDATE habits SET streak_count = $1, longest_streak = GREATEST(longest_streak, $1) WHERE id = $2",
            current_streak, habit_id
        )

async def get_today_logs(pool) -> List[int]:
    """Returns list of habit_ids logged as 'done' or 'skipped' today."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT habit_id FROM habit_logs WHERE log_date = CURRENT_DATE AND status IN ('done', 'skipped')"
        )
        return [r['habit_id'] for r in rows]

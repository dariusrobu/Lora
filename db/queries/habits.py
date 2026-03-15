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

async def get_habits_by_name(pool, name: str) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM habits WHERE name ILIKE $1 AND is_active = True",
            f"%{name}%"
        )
        return [dict(r) for r in rows]

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
        expected_date = date.today()
        
        # We allow today to be missing (if they haven't logged yet), 
        # but the streak must be anchored at today or yesterday.
        anchor_found = False
        
        for log in logs:
            l_date = log['log_date']
            l_status = log['status']
            
            # Skip skipped logs (they don't count towards streak nor break it)
            if l_status == 'skipped':
                continue
                
            # If it's a gap, we break
            # We allow a 1-day gap (today) if they haven't logged yet
            if not anchor_found:
                if l_date == date.today() or l_date == date.today() - timedelta(days=1):
                    anchor_found = True
                    expected_date = l_date
                else:
                    # No log today or yesterday that is 'done'
                    break
            
            if l_date == expected_date:
                if l_status == 'done':
                    current_streak += 1
                    expected_date -= timedelta(days=1)
                else:
                    break
            elif l_date < expected_date:
                # Gap found
                break
            # if l_date > expected_date (shouldn't happen with DESC order unless multiple logs per day, which DB prevents)
        
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

async def get_habits_completed_today(pool) -> List[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT h.name FROM habits h 
            JOIN habit_logs l ON h.id = l.habit_id 
            WHERE l.log_date = CURRENT_DATE AND l.status = 'done'
            """
        )
        return [r['name'] for r in rows]

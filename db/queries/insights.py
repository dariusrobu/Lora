from typing import List, Dict, Any
from datetime import date, timedelta
from db.queries.mood import MOOD_MAP

async def get_insight_data(pool, days: int = 30) -> List[Dict[str, Any]]:
    """
    Returns daily stats for mood, tasks, and habits over the last X days.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    async with pool.acquire() as conn:
        # 1. Get daily mood (latest entry per day)
        mood_rows = await conn.fetch(
            """
            SELECT log_date, mood FROM (
                SELECT entry_date as log_date, mood, created_at FROM journal_entries 
                WHERE entry_date BETWEEN $1 AND $2 AND mood IS NOT NULL
                UNION ALL
                SELECT created_at::date as log_date, mood, created_at FROM notes 
                WHERE type = 'journal' AND created_at::date BETWEEN $1 AND $2 AND mood IS NOT NULL
            ) combined
            ORDER BY log_date, created_at DESC
            """,
            start_date, end_date
        )
        # Deduplicate mood by date (take latest)
        mood_by_date = {}
        for r in mood_rows:
            d = r['log_date']
            if d not in mood_by_date:
                mood_by_date[d] = MOOD_MAP.get(r['mood'].lower(), 3)

        # 2. Get daily completed tasks
        task_rows = await conn.fetch(
            """
            SELECT completed_at::date as d, COUNT(*) as count 
            FROM tasks 
            WHERE status = 'done' AND completed_at::date BETWEEN $1 AND $2
            GROUP BY d
            """,
            start_date, end_date
        )
        tasks_by_date = {r['d']: r['count'] for r in task_rows}

        # 3. Get daily completed habits
        habit_rows = await conn.fetch(
            """
            SELECT log_date as d, COUNT(*) as count 
            FROM habit_logs 
            WHERE status = 'done' AND log_date BETWEEN $1 AND $2
            GROUP BY d
            """,
            start_date, end_date
        )
        habits_by_date = {r['d']: r['count'] for r in habit_rows}

        # 4. Merge into a timeline
        timeline = []
        curr = start_date
        while curr <= end_date:
            timeline.append({
                "date": curr,
                "day_of_week": curr.strftime("%A"),
                "mood": mood_by_date.get(curr),
                "tasks": tasks_by_date.get(curr, 0),
                "habits": habits_by_date.get(curr, 0)
            })
            curr += timedelta(days=1)
            
        return timeline

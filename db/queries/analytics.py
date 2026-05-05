from typing import List, Dict, Any
from datetime import datetime, timedelta

async def get_daily_aggregated_metrics(pool, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """
    Returns a daily timeline of metrics for the past `days` days.
    Includes:
    - tasks_completed: count
    - workout_duration: sum of minutes
    - mood_score: average mood (if logged in health)
    - energy_score: average energy (if logged in health)
    - total_expense: sum of expenses
    """
    start_date = datetime.now().date() - timedelta(days=days)
    
    # We will build a unified query using CTEs for each module
    query = """
    WITH date_series AS (
        SELECT generate_series(
            $2::date,
            CURRENT_DATE,
            '1 day'::interval
        )::date AS date
    ),
    daily_tasks AS (
        SELECT completed_at::date AS date, COUNT(*) as tasks_completed
        FROM tasks
        WHERE user_id = $1 AND status = 'completed' AND completed_at IS NOT NULL
        GROUP BY completed_at::date
    ),
    daily_workouts AS (
        SELECT workout_date::date AS date, SUM(duration_min) as workout_duration
        FROM workouts
        WHERE user_id = $1
        GROUP BY workout_date::date
    ),
    daily_health AS (
        SELECT date::date AS date, 
               AVG(mood) as mood_score, 
               AVG(energy) as energy_score,
               SUM(sleep_hours) as sleep_hours
        FROM health_logs
        WHERE user_id = $1
        GROUP BY date::date
    ),
    daily_finance AS (
        SELECT date::date AS date, SUM(amount) as total_expense
        FROM finance_logs
        WHERE user_id = $1 AND type = 'expense'
        GROUP BY date::date
    )
    SELECT 
        ds.date,
        COALESCE(dt.tasks_completed, 0) as tasks_completed,
        COALESCE(dw.workout_duration, 0) as workout_duration,
        dh.mood_score,
        dh.energy_score,
        dh.sleep_hours,
        COALESCE(df.total_expense, 0) as total_expense
    FROM date_series ds
    LEFT JOIN daily_tasks dt ON ds.date = dt.date
    LEFT JOIN daily_workouts dw ON ds.date = dw.date
    LEFT JOIN daily_health dh ON ds.date = dh.date
    LEFT JOIN daily_finance df ON ds.date = df.date
    ORDER BY ds.date ASC;
    """
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, user_id, start_date)
        return [dict(r) for r in rows]

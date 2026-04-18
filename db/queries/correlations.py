# db/queries/correlations.py

from typing import Dict, Any, List


async def get_30day_snapshot(pool) -> List[Dict[str, Any]]:
    """Fetch metrics for the last 30 days for correlation analysis."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            WITH date_range AS (
                SELECT generate_series(CURRENT_DATE - INTERVAL '29 days', CURRENT_DATE, '1 day')::date AS d
            ),
            daily_tasks AS (
                SELECT completed_at::date AS d, COUNT(*) as count
                FROM tasks
                WHERE status = 'done' AND completed_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY completed_at::date
            ),
            daily_workouts AS (
                SELECT workout_date AS d, COUNT(*) as count, SUM(duration_min) as total_min
                FROM workouts
                WHERE workout_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY workout_date
            ),
            daily_focus AS (
                SELECT session_date AS d, SUM(duration_min) as total_min
                FROM focus_sessions
                WHERE completed = TRUE AND session_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY session_date
            ),
            daily_expenses AS (
                SELECT tx_date AS d, SUM(amount) as total
                FROM finances
                WHERE type = 'expense' AND tx_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY tx_date
            ),
            daily_habits AS (
                SELECT log_date AS d, COUNT(*) as done_count
                FROM habit_logs
                WHERE status = 'done' AND log_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY log_date
            ),
            total_active_habits AS (
                SELECT COUNT(*) as count FROM habits WHERE is_active = TRUE
            )
            SELECT 
                dr.d as date,
                h.sleep_hours,
                h.sleep_quality,
                h.water_ml,
                j.mood,
                COALESCE(t.count, 0) as tasks_completed,
                COALESCE(w.count, 0) as workout_count,
                COALESCE(f.total_min, 0) as focus_minutes,
                COALESCE(e.total, 0) as expenses,
                COALESCE(hb.done_count, 0) as habits_done,
                (SELECT count FROM total_active_habits) as total_habits
            FROM date_range dr
            LEFT JOIN health_logs h ON dr.d = h.log_date
            LEFT JOIN journal_entries j ON dr.d = j.entry_date
            LEFT JOIN daily_tasks t ON dr.d = t.d
            LEFT JOIN daily_workouts w ON dr.d = w.d
            LEFT JOIN daily_focus f ON dr.d = f.d
            LEFT JOIN daily_expenses e ON dr.d = e.d
            LEFT JOIN daily_habits hb ON dr.d = hb.d
            ORDER BY dr.d ASC
        """)
        return [dict(r) for r in rows]


async def get_weekly_patterns(pool) -> List[Dict[str, Any]]:
    """Fetch metrics aggregated by day of week (0=Sunday to 6=Saturday)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            WITH metrics AS (
                SELECT 
                    EXTRACT(DOW FROM log_date) as dow,
                    sleep_hours,
                    water_ml,
                    1 as health_logged
                FROM health_logs
                WHERE log_date >= CURRENT_DATE - INTERVAL '60 days'
            ),
            task_metrics AS (
                SELECT 
                    EXTRACT(DOW FROM completed_at) as dow,
                    COUNT(*) as tasks
                FROM tasks
                WHERE status = 'done' AND completed_at >= CURRENT_DATE - INTERVAL '60 days'
                GROUP BY 1
            ),
            expense_metrics AS (
                SELECT 
                    EXTRACT(DOW FROM tx_date) as dow,
                    SUM(amount) as total_expenses
                FROM finances
                WHERE type = 'expense' AND tx_date >= CURRENT_DATE - INTERVAL '60 days'
                GROUP BY 1
            )
            SELECT 
                d.dow,
                ROUND(AVG(m.sleep_hours), 2) as avg_sleep,
                ROUND(AVG(m.water_ml)) as avg_water,
                COALESCE(t.tasks, 0) as total_tasks,
                COALESCE(e.total_expenses, 0) as total_expenses
            FROM (SELECT generate_series(0, 6) as dow) d
            LEFT JOIN metrics m ON d.dow = m.dow
            LEFT JOIN task_metrics t ON d.dow = t.dow
            LEFT JOIN expense_metrics e ON d.dow = e.dow
            GROUP BY d.dow, t.tasks, e.total_expenses
            ORDER BY d.dow ASC
        """)
        return [dict(r) for r in rows]

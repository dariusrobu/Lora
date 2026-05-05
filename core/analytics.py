import math
from typing import List, Dict, Any

def pearson_correlation(x: List[float], y: List[float]) -> float:
    """Calculates the Pearson correlation coefficient between two lists."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_x_sq = sum(xi**2 for xi in x)
    sum_y_sq = sum(yi**2 for yi in y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    
    numerator = n * sum_xy - sum_x * sum_y
    denominator = math.sqrt((n * sum_x_sq - sum_x**2) * (n * sum_y_sq - sum_y**2))
    
    if denominator == 0:
        return 0.0
        
    return numerator / denominator

async def calculate_correlations(pool, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """
    Calculates simple behavioral correlations over the past N days.
    """
    from db.queries.analytics import get_daily_aggregated_metrics
    
    data = await get_daily_aggregated_metrics(pool, user_id, days)
    if len(data) < 7:
        return [] # Not enough data
        
    tasks = [d["tasks_completed"] for d in data]
    workouts = [d["workout_duration"] for d in data]
    expenses = [d["total_expense"] for d in data]
    
    # For mood and sleep, we only correlate days where data exists
    mood_days = [d for d in data if d["mood_score"] is not None]
    sleep_days = [d for d in data if d["sleep_hours"] is not None]

    correlations = []

    # 1. Workout vs Productivity (Tasks)
    corr_work_task = pearson_correlation(workouts, tasks)
    if abs(corr_work_task) > 0.3:
        correlations.append({
            "metric_a": "Activitate fizică",
            "metric_b": "Productivitate (Task-uri)",
            "direction": "pozitivă" if corr_work_task > 0 else "negativă",
            "strength": abs(corr_work_task)
        })

    # 2. Mood vs Productivity
    if len(mood_days) >= 5:
        moods = [d["mood_score"] for d in mood_days]
        tasks_on_mood_days = [d["tasks_completed"] for d in mood_days]
        corr_mood_task = pearson_correlation(moods, tasks_on_mood_days)
        if abs(corr_mood_task) > 0.3:
            correlations.append({
                "metric_a": "Starea de spirit",
                "metric_b": "Productivitate (Task-uri)",
                "direction": "pozitivă" if corr_mood_task > 0 else "negativă",
                "strength": abs(corr_mood_task)
            })
            
    # 3. Sleep vs Mood
    if len(sleep_days) >= 5 and len(mood_days) >= 5:
        # Find intersecting days
        valid_days = [d for d in data if d["sleep_hours"] is not None and d["mood_score"] is not None]
        if len(valid_days) >= 5:
            sleeps = [d["sleep_hours"] for d in valid_days]
            moods = [d["mood_score"] for d in valid_days]
            corr_sleep_mood = pearson_correlation(sleeps, moods)
            if abs(corr_sleep_mood) > 0.3:
                correlations.append({
                    "metric_a": "Orele de somn",
                    "metric_b": "Starea de spirit",
                    "direction": "pozitivă" if corr_sleep_mood > 0 else "negativă",
                    "strength": abs(corr_sleep_mood)
                })

    # 4. Expenses vs Mood (Retail therapy check)
    if len(mood_days) >= 5:
        moods = [d["mood_score"] for d in mood_days]
        exp_on_mood_days = [d["total_expense"] for d in mood_days]
        corr_mood_exp = pearson_correlation(moods, exp_on_mood_days)
        if abs(corr_mood_exp) > 0.3:
            correlations.append({
                "metric_a": "Starea de spirit",
                "metric_b": "Cheltuieli",
                "direction": "pozitivă" if corr_mood_exp > 0 else "negativă",
                "strength": abs(corr_mood_exp)
            })

    # Sort by strength
    correlations.sort(key=lambda x: x["strength"], reverse=True)
    return correlations

async def generate_suggestions(pool, user_id: int) -> List[str]:
    """Generates proactive behavioral suggestions."""
    suggestions = []
    
    # Check if any expense was logged in the last 48h
    async with pool.acquire() as conn:
        last_expense = await conn.fetchval(
            "SELECT created_at FROM finance_logs WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
            user_id
        )
        
        from datetime import datetime, timedelta
        if not last_expense or datetime.now() - last_expense > timedelta(hours=48):
            suggestions.append("Nu ai logat nicio cheltuială în ultimele 48 de ore. Ai omis ceva?")
            
        # Check upcoming tasks
        upcoming_tasks = await conn.fetch(
            "SELECT title, due_date FROM tasks WHERE user_id = $1 AND status = 'pending' AND due_date = CURRENT_DATE + INTERVAL '1 day' LIMIT 1",
            user_id
        )
        for task in upcoming_tasks:
            suggestions.append(f"Mâine expiră task-ul: '{task['title']}'. Ești pe drumul cel bun?")
            
    return suggestions

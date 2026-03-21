# db/queries/workout.py

async def log_workout(pool, workout_date, type, duration_min, notes) -> int:
    return await pool.fetchval("""
        INSERT INTO workouts (workout_date, type, duration_min, notes)
        VALUES ($1, $2, $3, $4) RETURNING id
    """, workout_date, type, duration_min, notes)

async def log_exercise(pool, workout_id, name, sets, reps, weight_kg) -> None:
    await pool.execute("""
        INSERT INTO workout_exercises (workout_id, name, sets, reps, weight_kg)
        VALUES ($1, $2, $3, $4, $5)
    """, workout_id, name, sets, reps, weight_kg)

async def get_recent_workouts(pool, days=7) -> list:
    rows = await pool.fetch("""
        SELECT w.id, w.workout_date, w.type, w.duration_min, w.notes,
            json_agg(
                json_build_object(
                    'name', e.name, 'sets', e.sets, 
                    'reps', e.reps, 'weight_kg', e.weight_kg
                ) ORDER BY e.id
            ) FILTER (WHERE e.id IS NOT NULL) as exercises
        FROM workouts w
        LEFT JOIN workout_exercises e ON e.workout_id = w.id
        WHERE w.workout_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
        GROUP BY w.id
        ORDER BY w.workout_date DESC
    """, days)
    return [dict(r) for r in rows]

async def get_workout_stats(pool, days=30) -> dict:
    row = await pool.fetchrow("""
        SELECT 
            COUNT(DISTINCT w.id) as total_sessions,
            COUNT(DISTINCT w.workout_date) as active_days,
            MODE() WITHIN GROUP (ORDER BY w.type) as most_common_type,
            ROUND(AVG(w.duration_min)) as avg_duration
        FROM workouts w
        WHERE w.workout_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
    """, days)
    return dict(row) if row else {}

async def get_exercise_progress(pool, exercise_name, days=30) -> list:
    rows = await pool.fetch("""
        SELECT w.workout_date, e.sets, e.reps, e.weight_kg
        FROM workout_exercises e
        JOIN workouts w ON w.id = e.workout_id
        WHERE LOWER(e.name) LIKE LOWER($1)
          AND w.workout_date >= CURRENT_DATE - $2 * INTERVAL '1 day'
        ORDER BY w.workout_date ASC
    """, f"%{exercise_name}%", days)
    return [dict(r) for r in rows]

async def get_long_term_stats(pool, days=180) -> dict:
    row = await pool.fetchrow("""
        SELECT 
            COUNT(DISTINCT w.id) as total_sessions,
            COUNT(DISTINCT w.workout_date) as active_days,
            SUM(w.duration_min) as total_min,
            COUNT(DISTINCT w.type) as workout_types,
            MODE() WITHIN GROUP (ORDER BY w.type) as most_common_type,
            ROUND(AVG(w.duration_min)) as avg_duration,
            COUNT(DISTINCT DATE_TRUNC('week', w.workout_date::timestamp)) as active_weeks
        FROM workouts w
        WHERE w.workout_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
    """, days)
    
    # Breakdown pe tip
    type_rows = await pool.fetch("""
        SELECT type, COUNT(*) as count, SUM(duration_min) as total_min
        FROM workouts
        WHERE workout_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
        GROUP BY type
        ORDER BY count DESC
    """, days)
    
    # Top exerciții (după volum total kg)
    top_exercises = await pool.fetch("""
        SELECT e.name, 
               COUNT(*) as times_done,
               MAX(e.weight_kg) as max_weight,
               SUM(e.sets * e.reps * COALESCE(e.weight_kg, 0)) as total_volume_kg
        FROM workout_exercises e
        JOIN workouts w ON w.id = e.workout_id
        WHERE w.workout_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
          AND e.name IS NOT NULL
        GROUP BY e.name
        ORDER BY total_volume_kg DESC
        LIMIT 5
    """, days)
    
    # Trend lunar — sesiuni per lună
    monthly_trend = await pool.fetch("""
        SELECT TO_CHAR(DATE_TRUNC('month', workout_date), 'Mon YYYY') as month,
               COUNT(*) as sessions
        FROM workouts
        WHERE workout_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
        GROUP BY DATE_TRUNC('month', workout_date)
        ORDER BY DATE_TRUNC('month', workout_date) ASC
    """, days)
    
    result = dict(row) if row else {}
    result['by_type'] = [dict(r) for r in type_rows]
    result['top_exercises'] = [dict(r) for r in top_exercises]
    result['monthly_trend'] = [dict(r) for r in monthly_trend]
    return result

async def get_weekly_workout_summary(pool, start_date, end_date) -> dict:
    row = await pool.fetchrow("""
        SELECT COUNT(*) as sessions,
               SUM(duration_min) as total_min
        FROM workouts
        WHERE workout_date >= $1 AND workout_date <= $2
    """, start_date, end_date)
    return dict(row) if row else {"sessions": 0, "total_min": 0}

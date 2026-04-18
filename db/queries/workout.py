# db/queries/workout.py


async def log_workout(
    pool, workout_date, sport_id, duration_min, notes, calories=None
) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO workouts (workout_date, sport_id, duration_min, notes, calories)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
        """,
            workout_date,
            sport_id,
            duration_min,
            notes,
            calories,
        )


async def log_exercise(pool, workout_id, name, sets, reps, weight_kg) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO workout_exercises (workout_id, name, sets, reps, weight_kg)
            VALUES ($1, $2, $3, $4, $5)
        """,
            workout_id,
            name,
            sets,
            reps,
            weight_kg,
        )


async def get_recent_workouts(pool, days=7) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT w.id, w.workout_date, w.sport_id, st.name as type, st.icon, w.duration_min, w.notes,
                json_agg(
                    json_build_object(
                        'name', e.name, 'sets', e.sets, 
                        'reps', e.reps, 'weight_kg', e.weight_kg
                    ) ORDER BY e.id
                ) FILTER (WHERE e.id IS NOT NULL) as exercises
            FROM workouts w
            JOIN sport_types st ON st.id = w.sport_id
            LEFT JOIN workout_exercises e ON e.workout_id = w.id
            WHERE w.workout_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
            GROUP BY w.id, st.name, st.icon
            ORDER BY w.workout_date DESC, w.id DESC
        """,
            days,
        )
    return [dict(r) for r in rows]


async def get_workout_stats(pool, days=30) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT w.id) as total_sessions,
                COUNT(DISTINCT w.workout_date) as active_days,
                MODE() WITHIN GROUP (ORDER BY st.name) as most_common_type,
                ROUND(AVG(w.duration_min)) as avg_duration
            FROM workouts w
            JOIN sport_types st ON st.id = w.sport_id
            WHERE w.workout_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
        """,
            days,
        )
    return dict(row) if row else {}


async def get_exercise_progress(pool, exercise_name, days=30) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT w.workout_date, e.sets, e.reps, e.weight_kg
            FROM workout_exercises e
            JOIN workouts w ON w.id = e.workout_id
            WHERE LOWER(e.name) LIKE LOWER($1)
              AND w.workout_date >= CURRENT_DATE - $2 * INTERVAL '1 day'
            ORDER BY w.workout_date ASC
        """,
            f"%{exercise_name}%",
            days,
        )
    return [dict(r) for r in rows]


async def get_long_term_stats(pool, days=180) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT w.id) as total_sessions,
                COUNT(DISTINCT w.workout_date) as active_days,
                SUM(w.duration_min) as total_min,
                COUNT(DISTINCT w.sport_id) as workout_types,
                MODE() WITHIN GROUP (ORDER BY st.name) as most_common_type,
                ROUND(AVG(w.duration_min)) as avg_duration,
                COUNT(DISTINCT DATE_TRUNC('week', w.workout_date::timestamp)) as active_weeks
            FROM workouts w
            JOIN sport_types st ON st.id = w.sport_id
            WHERE w.workout_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
        """,
            days,
        )

        type_rows = await conn.fetch(
            """
            SELECT st.name as type, st.icon, COUNT(*) as count, SUM(w.duration_min) as total_min
            FROM workouts w
            JOIN sport_types st ON st.id = w.sport_id
            WHERE w.workout_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
            GROUP BY st.name, st.icon
            ORDER BY count DESC
        """,
            days,
        )

        top_exercises = await conn.fetch(
            """
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
        """,
            days,
        )

        monthly_trend = await conn.fetch(
            """
            SELECT TO_CHAR(DATE_TRUNC('month', workout_date), 'Mon YYYY') as month,
                   COUNT(*) as sessions
            FROM workouts
            WHERE workout_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
            GROUP BY DATE_TRUNC('month', workout_date)
            ORDER BY DATE_TRUNC('month', workout_date) ASC
        """,
            days,
        )

    result = dict(row) if row else {}
    result["by_type"] = [dict(r) for r in type_rows]
    result["top_exercises"] = [dict(r) for r in top_exercises]
    result["monthly_trend"] = [dict(r) for r in monthly_trend]
    return result


async def get_weekly_workout_summary(pool, start_date, end_date) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) as sessions,
                   SUM(duration_min) as total_min
            FROM workouts
            WHERE workout_date >= $1 AND workout_date <= $2
        """,
            start_date,
            end_date,
        )
    return dict(row) if row else {"sessions": 0, "total_min": 0}


# ──────────────────────────────────────────────────────────────
# NEW FUNCTIONS
# ──────────────────────────────────────────────────────────────


async def get_workout_by_id(pool, workout_id: int) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT w.*, st.name as sport_name, st.icon as sport_icon
            FROM workouts w
            JOIN sport_types st ON w.sport_id = st.id
            WHERE w.id = $1
        """,
            workout_id,
        )
        if not row:
            return None
        res = dict(row)

        ex_rows = await conn.fetch(
            """
            SELECT * FROM workout_exercises WHERE workout_id = $1 ORDER BY id ASC
        """,
            workout_id,
        )
        res["exercises"] = [dict(r) for r in ex_rows]
        return res


async def update_workout(
    pool, workout_id: int, sport_id: int, duration_min: int, notes: str
) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE workouts
            SET sport_id = $1, duration_min = $2, notes = $3
            WHERE id = $4
            RETURNING *
        """,
            sport_id,
            duration_min,
            notes,
            workout_id,
        )
    return dict(row) if row else {}


async def delete_workout(pool, workout_id: int) -> bool:
    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM workouts WHERE id = $1", workout_id)
        return res == "DELETE 1"


async def get_personal_records(pool) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT name as exercise_name, MAX(weight_kg) as max_weight
            FROM workout_exercises
            WHERE weight_kg IS NOT NULL AND weight_kg > 0
            GROUP BY name
            ORDER BY name ASC
        """)
    return [dict(r) for r in rows]


async def get_week_stats(pool) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT 
                COUNT(w.id) as sessions,
                COALESCE(SUM(w.duration_min), 0) as total_min,
                COUNT(DISTINCT w.workout_date) as active_days
            FROM workouts w
            WHERE DATE_TRUNC('week', w.workout_date) = DATE_TRUNC('week', CURRENT_DATE)
        """)

        split_rows = await conn.fetch("""
            SELECT st.name, st.icon, COUNT(*) as sessions
            FROM workouts w
            JOIN sport_types st ON w.sport_id = st.id
            WHERE DATE_TRUNC('week', w.workout_date) = DATE_TRUNC('week', CURRENT_DATE)
            GROUP BY st.name, st.icon
            ORDER BY sessions DESC
        """)

    res = dict(row) if row else {"sessions": 0, "total_min": 0, "active_days": 0}
    res["split"] = [dict(r) for r in split_rows]
    return res


async def get_all_exercises(pool) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM exercises ORDER BY name ASC")
    return [dict(r) for r in rows]


async def add_exercise(pool, name: str, category: str, muscle_group: str) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO exercises (name, category, muscle_group)
            VALUES ($1, $2, $3)
            RETURNING *
        """,
            name,
            category,
            muscle_group,
        )
    return dict(row)


async def update_exercise(pool, exercise_id: int, **kwargs) -> dict:
    if not kwargs:
        raise ValueError("No fields to update")

    set_clauses = []
    values = []

    for i, (key, value) in enumerate(kwargs.items(), start=1):
        set_clauses.append(f"{key} = ${i}")
        values.append(value)

    values.append(exercise_id)
    query = f"UPDATE exercises SET {', '.join(set_clauses)} WHERE id = ${len(values)} RETURNING *"

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
    return dict(row) if row else {}


async def delete_exercise(pool, exercise_id: int) -> bool:
    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM exercises WHERE id = $1", exercise_id)
        return res == "DELETE 1"

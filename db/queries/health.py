from typing import Optional, List, Dict, Any
from datetime import date


async def upsert_health_log(
    pool,
    log_date: date,
    sleep_hours: Optional[float] = None,
    sleep_quality: Optional[str] = None,
    water_ml: Optional[int] = None,
    nutrition: Optional[str] = None,
    weight_kg: Optional[float] = None,
    cigarettes: Optional[int] = None,
    notes: Optional[str] = None,
) -> None:
    """
    Upserts a health log entry for a specific date.
    Uses COALESCE to avoid overwriting existing values with NULL.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO health_logs (
                log_date, sleep_hours, sleep_quality, water_ml, nutrition, weight_kg, cigarettes, notes
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (log_date) 
            DO UPDATE SET 
            sleep_hours   = COALESCE($2, health_logs.sleep_hours),
            sleep_quality = COALESCE($3, health_logs.sleep_quality),
            water_ml      = COALESCE($4, health_logs.water_ml),
            nutrition     = COALESCE($5, health_logs.nutrition),
            weight_kg     = COALESCE($6, health_logs.weight_kg),
            cigarettes    = COALESCE($7, health_logs.cigarettes),
            notes         = COALESCE($8, health_logs.notes),
            updated_at    = NOW()
            RETURNING id
            """,
            log_date,
            sleep_hours,
            sleep_quality,
            water_ml,
            nutrition,
            weight_kg,
            cigarettes,
            notes,
        )
        return row["id"]


async def add_cigarettes(pool, log_date: date, count: int) -> int:
    """
    Adds cigarettes to the existing count for the day. Returns the new total.
    """
    async with pool.acquire() as conn:
        new_total = await conn.fetchval(
            """
            INSERT INTO health_logs (log_date, cigarettes)
            VALUES ($1, $2)
            ON CONFLICT (log_date) 
            DO UPDATE SET 
                cigarettes = COALESCE(health_logs.cigarettes, 0) + EXCLUDED.cigarettes,
                updated_at = NOW()
            RETURNING cigarettes
            """,
            log_date,
            count,
        )
        return new_total


async def add_water(pool, log_date: date, ml_to_add: int) -> int:
    """
    Adds water to the existing amount for the day. Returns the new total.
    """
    async with pool.acquire() as conn:
        new_total = await conn.fetchval(
            """
            INSERT INTO health_logs (log_date, water_ml)
            VALUES ($1, $2)
            ON CONFLICT (log_date) 
            DO UPDATE SET 
                water_ml = COALESCE(health_logs.water_ml, 0) + EXCLUDED.water_ml,
                updated_at = NOW()
            RETURNING water_ml
            """,
            log_date,
            ml_to_add,
        )
        return new_total


async def get_health_history(pool, days: int = 30) -> List[Dict[str, Any]]:
    """
    Retrieves health logs for the last N days.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM health_logs 
            WHERE log_date > CURRENT_DATE - $1::integer
            ORDER BY log_date ASC
            """,
            int(days),
        )
        return [dict(r) for r in rows]


async def get_health_summary(pool, days: int = 7) -> Dict[str, Any]:
    """
    Aggregates health stats for the last N days.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 
                AVG(sleep_hours) as avg_sleep,
                MODE() WITHIN GROUP (ORDER BY sleep_quality) as common_sleep_quality,
                AVG(water_ml) as avg_water,
                MAX(water_ml) as max_water,
                AVG(cigarettes) as avg_cigarettes,
                SUM(cigarettes) as total_cigarettes,
                MIN(weight_kg) FILTER (WHERE weight_kg > 0) as min_weight,
                MAX(weight_kg) FILTER (WHERE weight_kg > 0) as max_weight,
                COUNT(*) FILTER (WHERE nutrition IN ('great', 'good')) as good_nutrition_days,
                COUNT(*) as total_days
            FROM health_logs
            WHERE log_date > CURRENT_DATE - $1::integer
            """,
            int(days),
        )

        # Trend calculation for weight
        recent_weights = await conn.fetch(
            """
            SELECT weight_kg FROM health_logs 
            WHERE weight_kg IS NOT NULL 
            ORDER BY log_date DESC LIMIT 2
            """
        )

        trend = "stable"
        if len(recent_weights) >= 2:
            w1 = recent_weights[0]["weight_kg"]  # newest
            w2 = recent_weights[1]["weight_kg"]  # second newest
            if w1 < w2:
                trend = "down"
            elif w1 > w2:
                trend = "up"

        summary = dict(row) if row else {}
        summary["weight_trend"] = trend
        summary["recent_weight"] = (
            recent_weights[0]["weight_kg"] if recent_weights else None
        )
        summary["prev_weight"] = (
            recent_weights[1]["weight_kg"] if len(recent_weights) >= 2 else None
        )

        return summary


async def get_health_log(pool, log_date: date) -> Optional[Dict[str, Any]]:
    """
    Retrieves the health log for a specific date.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM health_logs WHERE log_date = $1", log_date
        )
        return dict(row) if row else None

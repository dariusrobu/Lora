from typing import List, Optional, Dict, Any
from datetime import date

async def upsert_health_log(pool, log_date: date, **kwargs) -> int:
    """Updates or inserts health metrics for a specific date."""
    keys = []
    values = []
    placeholders = []
    updates = []
    
    # Always include log_date as $1
    keys.append("log_date")
    values.append(log_date)
    placeholders.append("$1")
    
    i = 2
    for k, v in kwargs.items():
        if v is not None:
            keys.append(k)
            values.append(v)
            placeholders.append(f"${i}")
            updates.append(f"{k} = EXCLUDED.{k}")
            i += 1
            
    if not updates:
        return 0 # Nothing to update
        
    query = f"""
        INSERT INTO health_logs ({', '.join(keys)})
        VALUES ({', '.join(placeholders)})
        ON CONFLICT (log_date) DO UPDATE
        SET {', '.join(updates)}, updated_at = NOW()
        RETURNING id
    """
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        return row['id'] if row else 0

async def get_health_log(pool, log_date: date) -> Optional[Dict[str, Any]]:
    """Retrieves health log for a specific date."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM health_logs WHERE log_date = $1",
            log_date
        )
        return dict(row) if row else None

async def get_health_history(pool, days: int = 30) -> List[Dict[str, Any]]:
    """Retrieves historical health data for the specified number of days."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM health_logs 
            WHERE log_date > CURRENT_DATE - INTERVAL '1 day' * $1
            ORDER BY log_date ASC
            """,
            days
        )
        return [dict(r) for r in rows]

async def get_monthly_health_avg(pool, start_date, end_date) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT 
                ROUND(AVG(sleep_hours)::numeric, 1) as avg_sleep,
                ROUND(AVG(water_ml)::numeric, 0) as avg_water,
                MIN(weight_kg) as min_weight,
                MAX(weight_kg) as max_weight
            FROM health_logs
            WHERE log_date >= $1 AND log_date < $2
        """, start_date, end_date)
        return dict(row) if row else {}

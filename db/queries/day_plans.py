from typing import Optional, Dict, Any
from datetime import date

async def save_day_plan(pool, plan_date: date, user_input: Optional[str], itinerary: str, wake_time: Optional[str] = None) -> None:
    """Saves or updates a day plan for a specific date."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO day_plans (plan_date, user_input, itinerary, wake_time)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (plan_date) 
            DO UPDATE SET user_input = EXCLUDED.user_input, 
                          itinerary = EXCLUDED.itinerary,
                          wake_time = COALESCE(EXCLUDED.wake_time, day_plans.wake_time),
                          created_at = NOW()
            """,
            plan_date, user_input, itinerary, wake_time
        )

async def get_day_plan(pool, plan_date: date) -> Optional[Dict[str, Any]]:
    """Retrieves the day plan for a specific date."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM day_plans WHERE plan_date = $1",
            plan_date
        )
        return dict(row) if row else None

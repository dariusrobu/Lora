from typing import Optional, Dict, Any

async def get_user_profile(pool, telegram_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_profile WHERE telegram_id = $1",
            telegram_id
        )
        return dict(row) if row else None

async def create_user_profile(pool, telegram_id: int, timezone: str, morning_time: str, eod_time: str):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_profile (telegram_id, timezone, morning_time, eod_time)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
            telegram_id, timezone, morning_time, eod_time
        )

async def update_user_profile(pool, telegram_id: int, **kwargs):
    if not kwargs:
        return
    
    fields = []
    values = []
    for i, (key, value) in enumerate(kwargs.items(), start=2):
        fields.append(f"{key} = ${i}")
        values.append(value)
    
    query = f"UPDATE user_profile SET {', '.join(fields)}, updated_at = NOW() WHERE telegram_id = $1"
    
    async with pool.acquire() as conn:
        await conn.execute(query, telegram_id, *values)

async def is_onboarding_complete(pool, telegram_id: int) -> bool:
    profile = await get_user_profile(pool, telegram_id)
    return profile.get("onboarding_complete", False) if profile else False

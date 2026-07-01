from typing import Optional, Dict, Any

# Whitelist of columns allowed in update_user_profile to prevent SQL injection
_PROFILE_UPDATABLE_COLUMNS = frozenset(
    {
        "name",
        "timezone",
        "morning_time",
        "eod_time",
        "tone",
        "personal_notes",
        "onboarding_complete",
        "last_briefing_date",
        "last_eod_date",
        "last_weekly_date",
        "last_journal_date",
        "last_plan_date",
        "last_weekly_review_date",
        "last_finance_summary_date",
        "last_evening_date",
        "last_monthly_review_date",
        "water_target_ml",
        "university_name",
        "faculty",
        "specialization",
        "study_year",
        "study_group",
        "active_hours_start",
        "active_hours_end",
        "preferred_tone",
        "latitude",
        "longitude",
        "city_name",
        "home_latitude",
        "home_longitude",
        "is_at_home",
        "current_location_name",
        "llm_provider",
        "llm_host",
        "llm_model",
        "gemini_api_key",
        "units",
        "language",
        "week_start_day",
        "currency",
        "dietary_preferences",
        "notification_config",
    }
)


async def get_user_profile(pool, telegram_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_profile WHERE telegram_id = $1", telegram_id
        )
        return dict(row) if row else None


async def create_user_profile(
    pool, telegram_id: int, timezone: str, morning_time: str, eod_time: str
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_profile (telegram_id, timezone, morning_time, eod_time)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
            telegram_id,
            timezone,
            morning_time,
            eod_time,
        )


async def update_user_profile(pool, telegram_id: int, **kwargs):
    if not kwargs:
        return

    invalid = set(kwargs.keys()) - _PROFILE_UPDATABLE_COLUMNS
    if invalid:
        raise ValueError(f"update_user_profile: unknown column(s): {invalid}")

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

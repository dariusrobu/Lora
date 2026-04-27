import json
import logging
from typing import Dict, Any

logger = logging.getLogger("modules.profile")


async def update_profile_from_behavior(pool, user_id: int):
    """
    Analyzes user behavior from the last 30 days and updates frequent_categories.
    Looks at finance categories and task projects/tags.
    """
    logger.info(f"🔄 Updating behavioral profile for user {user_id}")

    async with pool.acquire() as conn:
        # 1. Analyze Finance Categories (last 30 days)
        finance_rows = await conn.fetch(
            """
            SELECT category, COUNT(*) as count
            FROM finances
            WHERE tx_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY category
            ORDER BY count DESC
            LIMIT 5
            """
        )
        finance_cats = {r["category"]: r["count"] for r in finance_rows}

        # 2. Analyze Task Categories/Projects (last 30 days)
        task_rows = await conn.fetch(
            """
            SELECT project, COUNT(*) as count
            FROM tasks
            WHERE created_at >= CURRENT_DATE - INTERVAL '30 days' AND project IS NOT NULL
            GROUP BY project
            ORDER BY count DESC
            LIMIT 5
            """
        )
        task_cats = {r["project"]: r["count"] for r in task_rows}

        # 3. Combine and Update frequent_categories
        frequent_categories = {"finance": finance_cats, "tasks": task_cats}

        await conn.execute(
            """
            UPDATE user_profile
            SET frequent_categories = $1, updated_at = NOW()
            WHERE telegram_id = $2
            """,
            json.dumps(frequent_categories),
            user_id,
        )

    logger.info(f"✅ Behavioral profile updated for user {user_id}")


async def get_user_profile_full(pool, user_id: int) -> Dict[str, Any]:
    """Retrieves the full user profile including behavioral data."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_profile WHERE telegram_id = $1", user_id
        )
        return dict(row) if row else {}

"""Read-only delivery health for the local launchd monitor."""

import asyncio

import asyncpg

from lora_v2.config import Settings


async def delivery_status() -> str:
    settings = Settings.from_env()
    conn = await asyncpg.connect(settings.database_url, timeout=5)
    try:
        delayed = await conn.fetchval(
            """SELECT EXISTS (
                SELECT 1 FROM notification_outbox
                WHERE owner_id=$1 AND channel='telegram'
                AND status IN ('pending','leased')
                AND due_at < now()-interval '2 minutes'
            ) OR EXISTS (
                SELECT 1 FROM alert_occurrences
                WHERE owner_id=$1 AND status='pending'
                AND alert_at BETWEEN now()-interval '1 day' AND now()-interval '2 minutes'
            )""",
            settings.telegram_user_id,
        )
        return 'backlog' if delayed else 'ok'
    finally:
        await conn.close()


async def moodle_status() -> str:
    """A running n8n container is insufficient if course extraction stopped."""
    settings = Settings.from_env()
    conn = await asyncpg.connect(settings.database_url, timeout=5)
    try:
        row = await conn.fetchrow(
            """SELECT count(*) AS courses,
            bool_and(last_synced_at >= now()-interval '12 hours') AS fresh
            FROM moodle_course_sync WHERE owner_id=$1""",
            settings.telegram_user_id,
        )
        return "ok" if row["courses"] and row["fresh"] else "stale"
    finally:
        await conn.close()


def main() -> None:
    try:
        async def check() -> tuple[str, str]:
            return await delivery_status(), await moodle_status()
        delivery, moodle = asyncio.run(check())
        print(f'delivery={delivery}\nmoodle_sync={moodle}')
    except Exception:
        print('delivery=down\nmoodle_sync=down')


if __name__ == '__main__':
    main()

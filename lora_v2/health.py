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


def main() -> None:
    try:
        print(f'delivery={asyncio.run(delivery_status())}')
    except Exception:
        print('delivery=down')


if __name__ == '__main__':
    main()

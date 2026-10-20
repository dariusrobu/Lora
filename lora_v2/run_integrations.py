"""Independent integration loop: failures cannot block reminder delivery."""

import asyncio
import json
import logging
import os

from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.obsidian import sync_configured_vault

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = Settings.from_env()
    pool = await create_pool(settings)
    try:
        await migrate(pool)
        while True:
            if os.getenv('LORA_V2_FULL_CUTOVER', 'false').lower() == 'true':
                try:
                    await sync_configured_vault(pool, settings.telegram_user_id)
                except Exception as exc:
                    logger.error('Obsidian sync failed: %s', type(exc).__name__)
                    await pool.execute(
                        """INSERT INTO integration_status(name,status,detail) VALUES ('obsidian','error',$1::jsonb)
                        ON CONFLICT(name) DO UPDATE SET status='error',detail=EXCLUDED.detail,checked_at=now()""",
                        json.dumps({'error': type(exc).__name__}),
                    )
            await asyncio.sleep(60)
    finally:
        await pool.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == '__main__':
    main()

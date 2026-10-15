"""Send-only v2 worker while the legacy bot owns Telegram polling."""

import asyncio
import logging

from telegram import Bot

from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.worker import run_forever


async def run() -> None:
    settings = Settings.from_env()
    pool = await create_pool(settings)
    try:
        await migrate(pool)
        async with Bot(settings.telegram_bot_token) as bot:
            await run_forever(pool, bot, settings, interactive_notifications=True)
    finally:
        await pool.close()


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(run())


if __name__ == "__main__":
    main()

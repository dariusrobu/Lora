"""Keep the existing file-only Obsidian OCR/draft automation independent of polling."""

import asyncio
import logging
import os

from dotenv import load_dotenv


async def run() -> None:
    load_dotenv()
    from integrations.obsidian_processor import process_vault_safe

    interval = max(60, int(os.getenv('OBSIDIAN_PROCESS_INTERVAL_MINUTES', '15')) * 60)
    while True:
        await asyncio.sleep(interval)
        if os.getenv('OBSIDIAN_SYNC_ENABLED', 'true').lower() == 'true':
            await process_vault_safe()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == '__main__':
    main()

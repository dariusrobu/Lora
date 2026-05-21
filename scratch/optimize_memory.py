import asyncio
from core.memory import optimize_user_memory
from db.connection import get_pool
from core.gemini import client
from core.config import TELEGRAM_USER_ID


async def main():
    pool = await get_pool()
    user_id = TELEGRAM_USER_ID

    print(f"Starting memory optimization for user {user_id}...")
    reply = await optimize_user_memory(pool, client, user_id)
    print(f"Result: {reply}")


if __name__ == "__main__":
    asyncio.run(main())

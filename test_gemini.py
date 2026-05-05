import asyncio
import os
import json
from core.gemini import get_gemini_response
import asyncpg


async def main():
    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    history = []
    res = await get_gemini_response(
        pool,
        12345,
        user_message="Lora, vreau să adaug un obiectiv: Să termin proiectul Lora pe anul acesta. Leagă-l de task-urile cu cuvintele cheie python și frontend.",
        user_name="Darius",
        tone="direct",
        context_snapshot="",
        history=history,
        personal_notes="",
    )
    print("RES:")
    print(json.dumps(res, indent=2))
    await pool.close()


asyncio.run(main())

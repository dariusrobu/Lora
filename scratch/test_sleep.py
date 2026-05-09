
import asyncio
from core.gemini import get_gemini_response
from db.connection import get_pool
from core.config import TELEGRAM_USER_ID

async def test_sleep_extraction():
    pool = await get_pool()
    user_id = TELEGRAM_USER_ID
    
    test_messages = [
        "Am dormit 8 ore aseară, a fost un somn bun.",
        "Am dormit de la 12 la 8 dimineața.",
        "Dormit 7 ore jumătate, m-am simțit excelent.",
        "Am dormit prost, doar 4 ore.",
        "Azi am dormit 7 ore.",
        "Am băut 2 litri de apă și am dormit 8 ore."
    ]
    
    for msg in test_messages:
        print(f"\n--- Testing message: {msg} ---")
        response = await get_gemini_response(
            pool, user_id, msg, "User", "warm", "No context", []
        )
        print(f"Intent: {response.get('intent')}")
        print(f"Module: {response.get('module')}")
        print(f"Data: {response.get('data')}")
        print(f"Reply: {response.get('reply')}")

if __name__ == "__main__":
    asyncio.run(test_sleep_extraction())

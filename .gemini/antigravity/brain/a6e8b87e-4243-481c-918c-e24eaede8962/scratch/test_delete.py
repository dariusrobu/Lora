import asyncio
from db.connection import get_pool, close_pool
from core.router import route_intent

async def test_delete():
    pool = await get_pool()
    
    print("\n--- Testing memory_delete intent ---")
    intent_response = {
        "intent": "memory_delete",
        "module": "memory",
        "data": {"fact_id": 1},
        "reply": "Ștergem amintirea..."
    }
    reply, markup = await route_intent(pool, intent_response)
    print("Reply:")
    print(reply)
    
    await close_pool()

if __name__ == "__main__":
    import os
    import sys
    sys.path.append(os.getcwd())
    asyncio.run(test_delete())

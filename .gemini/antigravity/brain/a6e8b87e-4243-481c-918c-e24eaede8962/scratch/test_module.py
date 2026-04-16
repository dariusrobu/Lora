import asyncio
from db.connection import get_pool, close_pool
from core.router import route_intent

async def test_module():
    pool = await get_pool()
    
    print("\n--- Testing memory_view intent ---")
    intent_response = {
        "intent": "memory_view",
        "module": "memory",
        "data": {},
        "reply": "Iată ce am găsit în memoria mea:"
    }
    reply, markup = await route_intent(pool, intent_response)
    print("Reply:")
    print(reply)
    
    await close_pool()

if __name__ == "__main__":
    import os
    import sys
    sys.path.append(os.getcwd())
    asyncio.run(test_module())

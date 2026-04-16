import asyncio
from db.connection import get_pool, close_pool
from core.context import build_context

async def test_relevance():
    pool = await get_pool()
    
    print("\n--- Testing Relevant Context Retrieval ---")
    # Simulate a follow-up message where sah might be relevant
    context = await build_context(pool, current_message="Azi am jucat puțin sah.")
    print("Context snapshot with memory:")
    print(context)
    
    await close_pool()

if __name__ == "__main__":
    import os
    import sys
    sys.path.append(os.getcwd())
    asyncio.run(test_relevance())

import asyncio
from db.connection import get_pool, close_pool
from core.memory import extract_and_save_facts
from core.context import build_context
from core.gemini import client

async def test_memory():
    pool = await get_pool()
    
    # Simulate a user message and assistant reply
    user_msg = "Sunt pasionat de sah si locuiesc in Cluj-Napoca."
    assistant_reply = "Am notat ca esti din Cluj si iti place sahul! Sahul e un joc minunat pentru minte."
    
    print("--- Testing Fact Extraction ---")
    await extract_and_save_facts(pool, client, user_msg, assistant_reply)
    
    # Wait a bit for the async task if it was fire-and-forget, 
    # but here we called it directly without asyncio.create_task for the test.
    
    print("\n--- Testing Context Retrieval ---")
    # Simulate a follow-up message where sah might be relevant
    context = await build_context(pool, current_message="Vreau să joc ceva.")
    print("Context snapshot with memory:")
    print(context)
    
    await close_pool()

if __name__ == "__main__":
    import os
    import sys
    sys.path.append(os.getcwd())
    asyncio.run(test_memory())

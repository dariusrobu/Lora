# scratch/test_correlations.py

import asyncio
import os
import json
from db.connection import get_pool
from core.correlations import compute_correlations, get_unseen_correlations
from modules.insights import run_proactive_insights
from dotenv import load_dotenv

load_dotenv()

async def test_correlations():
    print("🚀 Starting Correlation Engine Test...")
    pool = await get_pool()
    
    try:
        # 1. Test compute_correlations
        print("\n--- Testing compute_correlations ---")
        correlations = await compute_correlations(pool)
        print(f"Found {len(correlations)} correlations:")
        print(json.dumps(correlations, indent=2, ensure_ascii=False))
        
        # 2. Test anti-spam logic
        print("\n--- Testing anti-spam logic ---")
        unseen = await get_unseen_correlations(pool, correlations)
        print(f"Unseen correlations: {len(unseen)}")
        
        # 3. Test the full proactive insight run (it won't send if no insights)
        # We'll mock the bot just to see if it triggers
        class MockBot:
            async def send_message(self, chat_id, text, parse_mode=None):
                print(f"\n--- MockBot Sending Message ---\n{text}")

        print("\n--- Testing run_proactive_insights ---")
        await run_proactive_insights(pool, MockBot())
        
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(test_correlations())

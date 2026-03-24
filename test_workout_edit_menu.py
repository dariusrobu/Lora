import asyncio
import os
from unittest.mock import MagicMock, AsyncMock

# Mock dependencies
import sys
sys.modules["matplotlib"] = MagicMock()
sys.modules["matplotlib.pyplot"] = MagicMock()

from modules.workout import handle_workout_callback
from db.connection import get_pool

async def test_edit_menu():
    pool = await get_pool()
    
    # Mock query
    query = AsyncMock()
    query.data = "workout_edit"
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()
    
    print(f"🧪 Testing '{query.data}' callback...")
    try:
        await handle_workout_callback(query, pool, query.data)
        if query.edit_message_text.called:
            args, kwargs = query.edit_message_text.call_args
            print(f"🤖 REPLY TEXT:\n{args[0]}")
            print(f"🤖 PARSE MODE: {kwargs.get('parse_mode')}")
        else:
            print("❌ No reply message sent!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_edit_menu())

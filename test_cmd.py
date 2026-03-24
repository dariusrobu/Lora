import asyncio
import os
import json
from unittest.mock import MagicMock, AsyncMock

# Mock dependencies
import sys
sys.modules["matplotlib"] = MagicMock()
sys.modules["matplotlib.pyplot"] = MagicMock()

from bot.handler import projects_command
from db.connection import get_pool

async def test_cmd():
    pool = await get_pool()
    
    # Mock update and context
    update = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_user.id = int(os.environ.get("TELEGRAM_USER_ID"))
    
    context = MagicMock()
    context.bot_data = {"pool": pool}
    
    print("\n🧪 Testing '/projects' command function...")
    await projects_command(update, context)
    
    if update.message.reply_text.called:
        args, kwargs = update.message.reply_text.call_args
        print(f"🤖 REPLY:\n{args[0]}")
    else:
        print("❌ No reply sent!")

if __name__ == "__main__":
    asyncio.run(test_cmd())

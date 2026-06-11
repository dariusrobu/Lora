import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

# Add project root to sys.path
sys.path.append("/Users/robudarius/Lora")

from db.connection import get_pool, close_pool
from core.state import set_state, get_state, clear_state
from bot.handler import message_handler

class MockMessage:
    def __init__(self, text):
        self.text = text
        self.voice = None
        self.photo = None
        self.video = None
        self.sticker = None
        
        # Async methods
        self.reply_text = AsyncMock()

class MockUpdate:
    def __init__(self, text):
        self.message = MockMessage(text)
        self.effective_user = MagicMock()
        self.effective_user.id = 6838073664
        self.effective_chat = MagicMock()
        self.effective_chat.id = 6838073664
        self.update_id = 9999

class MockContext:
    def __init__(self):
        self.application = MagicMock()
        self.user_data = {}
        self.bot = AsyncMock()

async def run_test():
    pool = await get_pool()
    
    print("Setting state to 'awaiting_action_confirm'...")
    await set_state(pool, "awaiting_action_confirm", "tasks", "add_task", None, {"pending_intent": {"intent": "add_task"}})
    
    # 1. Test sending a non-confirmation message
    print("\nSending non-confirmation message: 'ce mai faci?'")
    update = MockUpdate("ce mai faci?")
    context = MockContext()
    
    await message_handler(update, context, pool)
    
    # Check if replied with the blocking warning
    print(f"Reply text mock called: {update.message.reply_text.call_args_list}")
    
    # Check if state is still active (not cleared)
    state = await get_state(pool)
    print(f"State active after non-confirmation message: {state is not None} (type={state.get('state_type') if state else None})")
    
    # 2. Test sending a confirmation message: 'da'
    print("\nSending confirmation message: 'da'")
    update_confirm = MockUpdate("da")
    
    # Mock route_intent to bypass actual DB execution / LLM calls
    import core.router
    original_route_intent = core.router.route_intent
    core.router.route_intent = AsyncMock(return_value=("Mocked Final Reply", None, None))
    
    try:
        await message_handler(update_confirm, context, pool)
        
        print(f"Reply text mock called on confirm: {update_confirm.message.reply_text.call_args_list}")
        
        # Check if state was cleared
        state_after = await get_state(pool)
        print(f"State active after 'da': {state_after is not None}")
    finally:
        # Restore route_intent
        core.router.route_intent = original_route_intent
        # Ensure state is cleared
        await clear_state(pool)
        
    await close_pool()

if __name__ == "__main__":
    asyncio.run(run_test())

import asyncio
import sys
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

# Add project root to sys.path
sys.path.append("/Users/robudarius/Lora")

from db.connection import get_pool, close_pool
from bot.handler import callback_handler

class MockQuery:
    def __init__(self, data, from_user_id=6838073664):
        self.data = data
        self.from_user = MagicMock()
        self.from_user.id = from_user_id
        self.bot = AsyncMock()
        self.message = AsyncMock()
        
        # Async mock methods
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()

class MockUpdate:
    def __init__(self, query):
        self.callback_query = query
        self.effective_user = query.from_user
        self.effective_chat = MagicMock()
        self.effective_chat.id = 6838073664

async def run_test():
    pool = await get_pool()
    
    print("Inserting temporary task and habit...")
    yesterday_date = date.today() - timedelta(days=1)
    
    async with pool.acquire() as conn:
        temp_task_id = await conn.fetchval(
            "INSERT INTO tasks (title, status, due_date) VALUES ($1, 'pending', $2) RETURNING id",
            "Test Callback Task", yesterday_date
        )
        temp_habit_id = await conn.fetchval(
            "INSERT INTO habits (name, description, is_active, target_days) VALUES ($1, $2, TRUE, $3) RETURNING id",
            "Test Callback Habit", "Desc", [0,1,2,3,4,5,6]
        )
        
        # Clean up any existing logs
        await conn.execute("DELETE FROM habit_logs WHERE habit_id = $1", temp_habit_id)
        
    try:
        # 1. Test task reschedule callback
        print(f"\n--- Testing task:reschedule:{temp_task_id}:tomorrow ---")
        query_reschedule = MockQuery(f"task:reschedule:{temp_task_id}:tomorrow")
        update_reschedule = MockUpdate(query_reschedule)
        
        await callback_handler(update_reschedule, MagicMock(), pool)
        
        # Verify db updated
        async with pool.acquire() as conn:
            due_date = await conn.fetchval("SELECT due_date FROM tasks WHERE id = $1", temp_task_id)
            print(f"Database Task Due Date after callback: {due_date} (expected: {date.today() + timedelta(days=1)})")
            
        print(f"Query.answer called: {query_reschedule.answer.call_args_list}")
        print(f"Query.edit_message_text called: {query_reschedule.edit_message_text.call_args_list}")

        # 2. Test habit log_yesterday callback
        print(f"\n--- Testing habit:log_yesterday:{temp_habit_id} ---")
        query_log = MockQuery(f"habit:log_yesterday:{temp_habit_id}")
        update_log = MockUpdate(query_log)
        
        await callback_handler(update_log, MagicMock(), pool)
        
        # Verify db updated
        async with pool.acquire() as conn:
            log_exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM habit_logs WHERE habit_id = $1 AND log_date = $2)", temp_habit_id, yesterday_date)
            print(f"Database Habit Log exists: {log_exists} (expected: True)")
            
        print(f"Query.answer called: {query_log.answer.call_args_list}")
        print(f"Query.edit_message_text called: {query_log.edit_message_text.call_args_list}")

        # 3. Test ignore callback
        print(f"\n--- Testing task:ignore:{temp_task_id} ---")
        query_ignore = MockQuery(f"task:ignore:{temp_task_id}")
        update_ignore = MockUpdate(query_ignore)
        await callback_handler(update_ignore, MagicMock(), pool)
        print(f"Query.answer called: {query_ignore.answer.call_args_list}")
        print(f"Query.edit_message_text called: {query_ignore.edit_message_text.call_args_list}")

    finally:
        print("\nCleaning up temporary records...")
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM tasks WHERE id = $1", temp_task_id)
            await conn.execute("DELETE FROM habit_logs WHERE habit_id = $1", temp_habit_id)
            await conn.execute("DELETE FROM habits WHERE id = $1", temp_habit_id)
            print("Cleanup completed.")
            
    await close_pool()

if __name__ == "__main__":
    asyncio.run(run_test())

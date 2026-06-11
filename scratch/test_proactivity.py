import asyncio
import sys
from datetime import date, timedelta

# Add project root to sys.path
sys.path.append("/Users/robudarius/Lora")

from db.connection import get_pool, close_pool
from scheduler.jobs import proactive_check

class MockBot:
    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
        print("--- SEND MESSAGE MOCK ---")
        print(f"Chat ID: {chat_id}")
        print(f"Text: {text}")
        print(f"Parse Mode: {parse_mode}")
        print(f"Reply Markup: {reply_markup}")
        if reply_markup:
            # InlineKeyboardMarkup buttons
            for row in reply_markup.inline_keyboard:
                buttons = [f"[{b.text} (data={b.callback_data})]" for b in row]
                print(f"Buttons: {' | '.join(buttons)}")
        print("------------------------")

class MockApplication:
    def __init__(self):
        self.bot = MockBot()

async def run_test():
    pool = await get_pool()
    application = MockApplication()
    
    print("Inserting temporary overdue task and missed habit for testing...")
    yesterday_date = date.today() - timedelta(days=1)
    yesterday_weekday = yesterday_date.weekday()
    
    async with pool.acquire() as conn:
        # 1. Insert temporary overdue task
        temp_task_id = await conn.fetchval(
            """
            INSERT INTO tasks (title, status, due_date, created_at)
            VALUES ($1, 'pending', $2, NOW() - INTERVAL '2 days')
            RETURNING id
            """,
            "Test Overdue Task Proactivity Check",
            yesterday_date
        )
        print(f"Inserted temp task ID: {temp_task_id}")
        
        # 2. Insert temporary active habit with yesterday's weekday in target_days
        temp_habit_id = await conn.fetchval(
            """
            INSERT INTO habits (name, description, is_active, target_days)
            VALUES ($1, $2, TRUE, $3)
            RETURNING id
            """,
            "Test Habit Proactivity Check",
            "This is a test habit description",
            [yesterday_weekday]
        )
        print(f"Inserted temp habit ID: {temp_habit_id}")
        
        # 3. Ensure no sent nudges exist for these temp IDs
        await conn.execute("DELETE FROM sent_nudges WHERE nudge_type IN ($1, $2)", 
                           f"task_overdue_{temp_task_id}", 
                           f"habit_missed_{temp_habit_id}_{yesterday_date}")

    try:
        print("\nRunning proactive_check()...")
        await proactive_check(application, pool)
        
        # Run again to verify that nudges are NOT sent a second time (deduplication check)
        print("\nRunning proactive_check() a second time (should NOT print send messages)...")
        await proactive_check(application, pool)
        
    finally:
        print("\nCleaning up temporary records...")
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM tasks WHERE id = $1", temp_task_id)
            await conn.execute("DELETE FROM habits WHERE id = $1", temp_habit_id)
            await conn.execute("DELETE FROM sent_nudges WHERE nudge_type IN ($1, $2)", 
                               f"task_overdue_{temp_task_id}", 
                               f"habit_missed_{temp_habit_id}_{yesterday_date}")
            print("Cleanup completed.")
            
    await close_pool()

if __name__ == "__main__":
    asyncio.run(run_test())

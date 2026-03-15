from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def task_keyboard(task_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Done", callback_data=f"tasks:complete:{task_id}"),
            InlineKeyboardButton("✏️ Edit", callback_data=f"tasks:edit:{task_id}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"tasks:delete:{task_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def habit_keyboard(habit_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Log", callback_data=f"habits:done:{habit_id}"),
            InlineKeyboardButton("⏭ Skip", callback_data=f"habits:skip:{habit_id}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"habits:delete:{habit_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def habit_checkin_keyboard(habit_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Done", callback_data=f"habits:done:{habit_id}"),
            InlineKeyboardButton("⏭ Skip", callback_data=f"habits:skip:{habit_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def confirmation_keyboard(module: str, action: str, item_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Yes, delete", callback_data=f"{module}:{action}_confirmed:{item_id}"),
            InlineKeyboardButton("Cancel", callback_data=f"{module}:cancel:{item_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def habit_list_keyboard(habits: list) -> InlineKeyboardMarkup:
    # Row of Done buttons for today's habits
    keyboard = []
    for h in habits:
        keyboard.append([
            InlineKeyboardButton(f"✅ {h['name'].capitalize()}", callback_data=f"habits:done:{h['id']}:list")
        ])
    return InlineKeyboardMarkup(keyboard)

def task_list_keyboard(tasks: list) -> InlineKeyboardMarkup:
    # Multiple tasks, each with a 'Done' button
    keyboard = []
    for t in tasks:
        # One row per task: [ Title (Done) ]
        keyboard.append([
            InlineKeyboardButton(f"✅ {t['title'][:20]}...", callback_data=f"tasks:complete:{t['id']}:list")
        ])
    return InlineKeyboardMarkup(keyboard)

def mood_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("😊 Great", callback_data="mood:great"),
            InlineKeyboardButton("🙂 Good", callback_data="mood:good"),
        ],
        [
            InlineKeyboardButton("😐 Okay", callback_data="mood:okay"),
            InlineKeyboardButton("😔 Tough", callback_data="mood:bad"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

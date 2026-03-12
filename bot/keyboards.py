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

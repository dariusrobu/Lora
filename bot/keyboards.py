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

# ── Workout Keyboards ──────────────────────────────────────────

def workout_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📝 Log antrenament", callback_data="workout_log"),
            InlineKeyboardButton("📊 Statistici", callback_data="workout_stats_menu"),
        ],
        [
            InlineKeyboardButton("🏆 Personal Records", callback_data="workout_prs"),
            InlineKeyboardButton("📅 Săptămâna", callback_data="workout_week"),
        ],
        [
            InlineKeyboardButton("✏️ Editează", callback_data="workout_edit"),
            InlineKeyboardButton("🗑️ Șterge", callback_data="workout_delete"),
        ],
        [
            InlineKeyboardButton("⚙️ Sporturi", callback_data="workout_sports"),
            InlineKeyboardButton("🏋️ Exerciții", callback_data="workout_exercises"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def workout_stats_period_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("7 zile", callback_data="workout_stats_7"),
            InlineKeyboardButton("30 zile", callback_data="workout_stats_30"),
            InlineKeyboardButton("180 zile", callback_data="workout_stats_180"),
        ],
        [InlineKeyboardButton("⬅️ Înapoi", callback_data="workout_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def sport_category_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Forță", callback_data="workout_cat_Forță"),
            InlineKeyboardButton("Cardio", callback_data="workout_cat_Cardio"),
        ],
        [
            InlineKeyboardButton("Sport", callback_data="workout_cat_Sport"),
            InlineKeyboardButton("Mobilitate", callback_data="workout_cat_Mobilitate"),
        ],
        [InlineKeyboardButton("⬅️ Înapoi", callback_data="workout_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def sports_list_keyboard(sports: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    # Build buttons 2 per row
    for i in range(0, len(sports), 2):
        row = [InlineKeyboardButton(f"{sports[i].get('icon', '')} {sports[i]['name']}", callback_data=f"workout_sport_{sports[i]['id']}")]
        if i + 1 < len(sports):
            row.append(InlineKeyboardButton(f"{sports[i+1].get('icon', '')} {sports[i+1]['name']}", callback_data=f"workout_sport_{sports[i+1]['id']}"))
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("➕ Adaugă sport nou", callback_data="workout_add_sport")])
    keyboard.append([InlineKeyboardButton("⬅️ Înapoi", callback_data="workout_main")])
    return InlineKeyboardMarkup(keyboard)

def exercises_list_keyboard(exercises: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for i in range(0, len(exercises), 2):
        row = [InlineKeyboardButton(exercises[i]['name'], callback_data=f"workout_exercise_{exercises[i]['id']}")]
        if i + 1 < len(exercises):
            row.append(InlineKeyboardButton(exercises[i+1]['name'], callback_data=f"workout_exercise_{exercises[i+1]['id']}"))
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("➕ Adaugă exercițiu", callback_data="workout_add_exercise")])
    keyboard.append([InlineKeyboardButton("⬅️ Înapoi", callback_data="workout_main")])
    return InlineKeyboardMarkup(keyboard)

def confirm_delete_keyboard(item_type: str, item_id: int) -> InlineKeyboardMarkup:
    # item_type can be 'workout', 'sport', 'exercise'
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmă", callback_data=f"workout_confirm_delete_{item_type}_{item_id}"),
            InlineKeyboardButton("❌ Anulează", callback_data="workout_main"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

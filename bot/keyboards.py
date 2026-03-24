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


def task_list_keyboard(tasks: list, back_callback: str = "tasks:main") -> InlineKeyboardMarkup:
    # Multiple tasks, each with a 'Done' button
    keyboard = []
    for t in tasks:
        # One row per task: [ Title (Done) ]
        keyboard.append([
            InlineKeyboardButton(f"✅ {t['title'][:25]}", callback_data=f"tasks:complete:{t['id']}:list")
        ])
    keyboard.append([InlineKeyboardButton("◀️ Înapoi", callback_data=back_callback)])
    return InlineKeyboardMarkup(keyboard)

def tasks_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📋 Toate task-urile", callback_data="tasks:list_all"),
            InlineKeyboardButton("📂 Pe proiecte", callback_data="tasks:projects_list"),
        ],
        [
            InlineKeyboardButton("➕ Task nou", callback_data="tasks:new"),
            InlineKeyboardButton("➕ Proiect nou", callback_data="projects:new"),
        ],
        [
            InlineKeyboardButton("✅ Recent încheiate", callback_data="tasks:recent_done")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def tasks_projects_keyboard(projects_with_counts: list) -> InlineKeyboardMarkup:
    keyboard = []
    for p in projects_with_counts:
        # p is dict with 'id', 'name', 'task_count'
        label = f"📁 {p['name']} ({p['task_count']})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"tasks:project_view:{p['id']}")])
    
    keyboard.append([InlineKeyboardButton("➕ Proiect nou", callback_data="projects:new")])
    keyboard.append([InlineKeyboardButton("◀️ Înapoi", callback_data="tasks:main")])
    return InlineKeyboardMarkup(keyboard)

def tasks_project_detail_keyboard(project_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("➕ Adaugă task aici", callback_data=f"tasks:new_for_project:{project_id}"),
        ],
        [
            InlineKeyboardButton("🏁 Marcheză proiect ca GATA", callback_data=f"projects:complete:{project_id}"),
            InlineKeyboardButton("🗑️ Șterge proiect", callback_data=f"projects:delete:{project_id}"),
        ],
        [InlineKeyboardButton("◀️ Înapoi la proiecte", callback_data="tasks:projects_list")]
    ]
    return InlineKeyboardMarkup(keyboard)

def projects_main_keyboard(projects: list) -> InlineKeyboardMarkup:
    # Dedicated projects dashboard keyboard
    keyboard = []
    
    # 1. Row for adding
    keyboard.append([InlineKeyboardButton("➕ Proiect Nou", callback_data="projects:new")])
    
    # 2. List some projects as buttons (max 5 for the main view)
    for p in projects[:5]:
        keyboard.append([InlineKeyboardButton(f"📂 {p['name']}", callback_data=f"tasks:project_view:{p['id']}")])
    
    # 3. View all / Tasks
    keyboard.append([
        InlineKeyboardButton("📋 Vezi toate", callback_data="tasks:projects_list"),
        InlineKeyboardButton("✅ Tasks", callback_data="tasks:main")
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


# ── Goals module keyboards ──────────────────────────────────────────

def goals_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Goals active", callback_data="goals_active"), InlineKeyboardButton("✅ Completate", callback_data="goals_completed")],
        [InlineKeyboardButton("➕ Goal nou", callback_data="goals_new"), InlineKeyboardButton("📊 Overview", callback_data="goals_overview")]
    ])

def goals_category_keyboard(context: str = "new") -> InlineKeyboardMarkup:
    categories = ["Academice", "Sport", "Skills", "Financiare", "Lectură", "Personal", "Sănătate"]
    keyboard = []
    for i in range(0, len(categories), 2):
        row = [InlineKeyboardButton(categories[i], callback_data=f"goals_category_{categories[i]}_{context}")]
        if i + 1 < len(categories):
            row.append(InlineKeyboardButton(categories[i+1], callback_data=f"goals_category_{categories[i+1]}_{context}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Anulează", callback_data="goals_cancel")])
    return InlineKeyboardMarkup(keyboard)

def goals_list_keyboard(goals: list) -> InlineKeyboardMarkup:
    keyboard = []
    for g in goals:
        label = f"🎯 {g['title']} ({g.get('progress', 0)}%)"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"goals_detail_{g['id']}")])
    keyboard.append([InlineKeyboardButton("◀️ Înapoi", callback_data="goals_cancel")])
    return InlineKeyboardMarkup(keyboard)

def goal_detail_keyboard(goal_id: int, is_completed: bool) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✏️ Editează", callback_data=f"goals_edit_{goal_id}"), InlineKeyboardButton("➕ Sub-task", callback_data=f"goals_add_subtask_{goal_id}")]
    ]
    if not is_completed:
        keyboard.append([InlineKeyboardButton("✅ Completat", callback_data=f"goals_complete_goal_{goal_id}"), InlineKeyboardButton("🗑️ Șterge", callback_data=f"goals_delete_{goal_id}")])
    else:
        keyboard.append([InlineKeyboardButton("🗑️ Șterge", callback_data=f"goals_delete_{goal_id}")])
    keyboard.append([InlineKeyboardButton("◀️ Înapoi", callback_data="goals_active")])
    return InlineKeyboardMarkup(keyboard)

def subtasks_keyboard(subtasks: list, goal_id: int) -> InlineKeyboardMarkup:
    keyboard = []
    for st in subtasks:
        icon = "✅" if st['is_completed'] else "⬜"
        keyboard.append([InlineKeyboardButton(f"{icon} {st['title']}", callback_data=f"goals_complete_subtask_{st['id']}")])
    keyboard.append([InlineKeyboardButton("◀️ Înapoi", callback_data=f"goals_detail_{goal_id}")])
    return InlineKeyboardMarkup(keyboard)

def confirm_delete_goal_keyboard(goal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirmă", callback_data=f"goals_confirm_delete_{goal_id}"), InlineKeyboardButton("❌ Anulează", callback_data=f"goals_detail_{goal_id}")]
    ])

# ── Skill Tracking ─────────────────────────────────────────────

def skills_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats", callback_data="skills_list"), InlineKeyboardButton("➕ Log", callback_data="skills_log_list")],
        [InlineKeyboardButton("📈 Progress", callback_data="skills_progress"), InlineKeyboardButton("⚙️ Manage", callback_data="skills_manage")],
        [InlineKeyboardButton("◀️ Înapoi", callback_data="skills_cancel")]
    ])

def skills_list_keyboard(skills: list, action_prefix: str = "skills_detail_") -> InlineKeyboardMarkup:
    keyboard = []
    for s in skills:
        keyboard.append([InlineKeyboardButton(f"{s['name']}", callback_data=f"{action_prefix}{s['id']}")])
    
    keyboard.append([InlineKeyboardButton("➕ Adaugă Skill Nou", callback_data="skills_add_new")])
    keyboard.append([InlineKeyboardButton("◀️ Înapoi", callback_data="skills_cancel")])
    return InlineKeyboardMarkup(keyboard)

def skill_detail_keyboard(skill_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Log Value", callback_data=f"skills_log_entry_{skill_id}")],
        [InlineKeyboardButton("📊 Istoric", callback_data=f"skills_history_{skill_id}")],
        [InlineKeyboardButton("🗑️ Șterge", callback_data=f"skills_delete_{skill_id}")],
        [InlineKeyboardButton("◀️ Înapoi", callback_data="skills_list")]
    ])

def confirm_delete_skill_keyboard(skill_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirmă", callback_data=f"skills_confirm_delete_{skill_id}"), 
         InlineKeyboardButton("❌ Anulează", callback_data=f"skills_detail_{skill_id}")]
    ])

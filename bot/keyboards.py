import os
from bot.callback_utils import make_callback_data
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from bot.formatter import escape_md


def task_keyboard(task_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Done",
                callback_data=make_callback_data("tasks", "complete", task_id),
            ),
            InlineKeyboardButton(
                "✏️ Edit", callback_data=make_callback_data("tasks", "edit", task_id)
            ),
            InlineKeyboardButton(
                "🗑 Delete", callback_data=make_callback_data("tasks", "delete", task_id)
            ),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def task_list_keyboard(
    tasks: list, back_callback: str = "tasks:main"
) -> InlineKeyboardMarkup:
    # Use a grid layout (2 buttons per row) for better aesthetics
    keyboard = []
    
    # Limit to top 10 tasks to avoid "button spam"
    display_tasks = tasks[:10]
    
    for i in range(0, len(display_tasks), 2):
        row = []
        # First button in row
        t1 = display_tasks[i]
        label1 = f"✅ {t1['title'][:18]}.." if len(t1['title']) > 18 else f"✅ {t1['title']}"
        row.append(
            InlineKeyboardButton(
                label1,
                callback_data=make_callback_data("tasks", "complete", t1["id"], "list"),
            )
        )
        
        # Second button in row (if exists)
        if i + 1 < len(display_tasks):
            t2 = display_tasks[i+1]
            label2 = f"✅ {t2['title'][:18]}.." if len(t2['title']) > 18 else f"✅ {t2['title']}"
            row.append(
                InlineKeyboardButton(
                    label2,
                    callback_data=make_callback_data("tasks", "complete", t2["id"], "list"),
                )
            )
        keyboard.append(row)

    # Add a "View More in Dashboard" button if we truncated the list
    if len(tasks) > 10:
        keyboard.append([
            InlineKeyboardButton(
                "➕ Vezi toate (Dashboard)", 
                web_app=WebAppInfo(url=os.getenv("DASHBOARD_URL", ""))
            )
        ])

    keyboard.append([InlineKeyboardButton("◀️ Înapoi", callback_data=back_callback)])
    return InlineKeyboardMarkup(keyboard)


def tasks_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "📋 Toate task-urile",
                callback_data=make_callback_data("tasks", "list_all"),
            ),
            InlineKeyboardButton(
                "📂 Pe proiecte",
                callback_data=make_callback_data("tasks", "projects_list"),
            ),
        ],
        [
            InlineKeyboardButton(
                "➕ Task nou", callback_data=make_callback_data("tasks", "new")
            ),
            InlineKeyboardButton(
                "➕ Proiect nou", callback_data=make_callback_data("projects", "new")
            ),
        ],
        [
            InlineKeyboardButton(
                "✅ Recent încheiate",
                callback_data=make_callback_data("tasks", "recent_done"),
            )
        ],
        [
            InlineKeyboardButton(
                "🚀 Open Dashboard",
                web_app=WebAppInfo(
                    url=os.getenv(
                        "DASHBOARD_URL", "https://lora-dashboard.railway.app/dashboard"
                    )
                ),
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def tasks_projects_keyboard(projects_with_counts: list) -> InlineKeyboardMarkup:
    keyboard = []
    for p in projects_with_counts:
        # p is dict with 'id', 'name', 'task_count'
        label = f"📁 {p['name']} ({p['task_count']})"
        keyboard.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=make_callback_data("tasks", "project_view", p["id"]),
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "➕ Proiect nou", callback_data=make_callback_data("projects", "new")
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                "◀️ Înapoi", callback_data=make_callback_data("tasks", "main")
            )
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def tasks_confirm_delete_keyboard(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Confirmă",
                    callback_data=make_callback_data(
                        "tasks", "delete_confirmed", task_id
                    ),
                ),
                InlineKeyboardButton(
                    "❌ Anulează", callback_data=make_callback_data("tasks", "cancel")
                ),
            ]
        ]
    )


def tasks_undo_delete_keyboard(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "↩️ Undo (Anulează ștergerea)",
                    callback_data=make_callback_data("tasks", "undo_delete", task_id),
                )
            ]
        ]
    )


def projects_confirm_delete_keyboard(project_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Confirmă",
                    callback_data=make_callback_data(
                        "projects", "delete_confirmed", project_id
                    ),
                ),
                InlineKeyboardButton(
                    "❌ Anulează",
                    callback_data=make_callback_data("tasks", "projects_list"),
                ),
            ]
        ]
    )


def tasks_project_detail_keyboard(project_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Adaugă task aici",
                callback_data=make_callback_data(
                    "tasks", "new_for_project", project_id
                ),
            ),
        ],
        [
            InlineKeyboardButton(
                "🏁 Marcheză proiect ca GATA",
                callback_data=make_callback_data("projects", "complete", project_id),
            ),
            InlineKeyboardButton(
                "🗑️ Șterge proiect",
                callback_data=make_callback_data("projects", "delete", project_id),
            ),
        ],
        [
            InlineKeyboardButton(
                "◀️ Înapoi la proiecte",
                callback_data=make_callback_data("tasks", "projects_list"),
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def projects_main_keyboard(projects: list) -> InlineKeyboardMarkup:
    # Dedicated projects dashboard keyboard
    keyboard = []

    # 1. Row for adding
    keyboard.append(
        [
            InlineKeyboardButton(
                "➕ Proiect Nou", callback_data=make_callback_data("projects", "new")
            )
        ]
    )

    # 2. List some projects as buttons (max 5 for the main view)
    for p in projects[:5]:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"📂 {p['name']}",
                    callback_data=make_callback_data("tasks", "project_view", p["id"]),
                )
            ]
        )

    # 3. View all / Tasks
    keyboard.append(
        [
            InlineKeyboardButton(
                "📋 Vezi toate",
                callback_data=make_callback_data("tasks", "projects_list"),
            ),
            InlineKeyboardButton(
                "✅ Tasks", callback_data=make_callback_data("tasks", "main")
            ),
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def mood_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "😊 Great", callback_data=make_callback_data("mood", "great")
            ),
            InlineKeyboardButton(
                "🙂 Good", callback_data=make_callback_data("mood", "good")
            ),
        ],
        [
            InlineKeyboardButton(
                "😐 Okay", callback_data=make_callback_data("mood", "okay")
            ),
            InlineKeyboardButton(
                "😔 Tough", callback_data=make_callback_data("mood", "bad")
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── Workout Keyboards ──────────────────────────────────────────


def workout_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "📝 Log antrenament", callback_data=make_callback_data("workout_log")
            ),
            InlineKeyboardButton(
                "📊 Statistici", callback_data=make_callback_data("workout_stats_menu")
            ),
        ],
        [
            InlineKeyboardButton(
                "🏆 Personal Records", callback_data=make_callback_data("workout_prs")
            ),
            InlineKeyboardButton(
                "📅 Săptămâna", callback_data=make_callback_data("workout_week")
            ),
        ],
        [
            InlineKeyboardButton(
                "✏️ Editează", callback_data=make_callback_data("workout_edit")
            ),
            InlineKeyboardButton(
                "🗑️ Șterge", callback_data=make_callback_data("workout_delete")
            ),
        ],
        [
            InlineKeyboardButton(
                "⚙️ Sporturi", callback_data=make_callback_data("workout_sports")
            ),
            InlineKeyboardButton(
                "🏋️ Exerciții", callback_data=make_callback_data("workout_exercises")
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def workout_stats_period_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "7 zile", callback_data=make_callback_data("workout_stats_7")
            ),
            InlineKeyboardButton(
                "30 zile", callback_data=make_callback_data("workout_stats_30")
            ),
            InlineKeyboardButton(
                "180 zile", callback_data=make_callback_data("workout_stats_180")
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Înapoi", callback_data=make_callback_data("workout_main")
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def sport_category_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "Forță", callback_data=make_callback_data("workout_cat_Forță")
            ),
            InlineKeyboardButton(
                "Cardio", callback_data=make_callback_data("workout_cat_Cardio")
            ),
        ],
        [
            InlineKeyboardButton(
                "Sport", callback_data=make_callback_data("workout_cat_Sport")
            ),
            InlineKeyboardButton(
                "Mobilitate", callback_data=make_callback_data("workout_cat_Mobilitate")
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Înapoi", callback_data=make_callback_data("workout_main")
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def sports_list_keyboard(sports: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    # Build buttons 2 per row
    for i in range(0, len(sports), 2):
        row = [
            InlineKeyboardButton(
                f"{sports[i].get('icon', '')} {sports[i]['name']}",
                callback_data=make_callback_data(f"workout_sport_{sports[i]['id']}"),
            )
        ]
        if i + 1 < len(sports):
            row.append(
                InlineKeyboardButton(
                    f"{sports[i + 1].get('icon', '')} {sports[i + 1]['name']}",
                    callback_data=make_callback_data(
                        f"workout_sport_{sports[i + 1]['id']}"
                    ),
                )
            )
        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton(
                "➕ Adaugă sport nou",
                callback_data=make_callback_data("workout_add_sport"),
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Înapoi", callback_data=make_callback_data("workout_main")
            )
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def exercises_list_keyboard(exercises: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for i in range(0, len(exercises), 2):
        row = [
            InlineKeyboardButton(
                exercises[i]["name"],
                callback_data=make_callback_data(
                    f"workout_exercise_{exercises[i]['id']}"
                ),
            )
        ]
        if i + 1 < len(exercises):
            row.append(
                InlineKeyboardButton(
                    exercises[i + 1]["name"],
                    callback_data=make_callback_data(
                        f"workout_exercise_{exercises[i + 1]['id']}"
                    ),
                )
            )
        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton(
                "➕ Adaugă exercițiu",
                callback_data=make_callback_data("workout_add_exercise"),
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Înapoi", callback_data=make_callback_data("workout_main")
            )
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def confirm_delete_keyboard(item_type: str, item_id: int) -> InlineKeyboardMarkup:
    # item_type can be 'workout', 'sport', 'exercise'
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Confirmă",
                callback_data=make_callback_data(
                    f"workout_confirm_delete_{item_type}_{item_id}"
                ),
            ),
            InlineKeyboardButton(
                "❌ Anulează", callback_data=make_callback_data("workout_main")
            ),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# ── Goals module keyboards ──────────────────────────────────────────


def goals_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🎯 Goals active", callback_data=make_callback_data("goals_active")
                ),
                InlineKeyboardButton(
                    "✅ Completate", callback_data=make_callback_data("goals_completed")
                ),
            ],
            [
                InlineKeyboardButton(
                    "➕ Goal nou", callback_data=make_callback_data("goals_new")
                ),
                InlineKeyboardButton(
                    "📊 Overview", callback_data=make_callback_data("goals_overview")
                ),
            ],
        ]
    )


def goals_category_keyboard(context: str = "new") -> InlineKeyboardMarkup:
    categories = [
        "Academice",
        "Sport",
        "Skills",
        "Financiare",
        "Lectură",
        "Personal",
        "Sănătate",
    ]
    keyboard = []
    for i in range(0, len(categories), 2):
        row = [
            InlineKeyboardButton(
                categories[i],
                callback_data=make_callback_data(
                    f"goals_category_{categories[i]}_{context}"
                ),
            )
        ]
        if i + 1 < len(categories):
            row.append(
                InlineKeyboardButton(
                    categories[i + 1],
                    callback_data=make_callback_data(
                        f"goals_category_{categories[i + 1]}_{context}"
                    ),
                )
            )
        keyboard.append(row)
    keyboard.append(
        [
            InlineKeyboardButton(
                "❌ Anulează", callback_data=make_callback_data("goals_cancel")
            )
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def goals_list_keyboard(goals: list) -> InlineKeyboardMarkup:
    keyboard = []
    display_goals = goals[:10]
    for i in range(0, len(display_goals), 2):
        row = []
        g1 = display_goals[i]
        label1 = f"🎯 {g1['title'][:15]}.." if len(g1['title']) > 15 else f"🎯 {g1['title']}"
        row.append(InlineKeyboardButton(label1, callback_data=make_callback_data(f"goals_detail_{g1['id']}")))
        
        if i + 1 < len(display_goals):
            g2 = display_goals[i+1]
            label2 = f"🎯 {g2['title'][:15]}.." if len(g2['title']) > 15 else f"🎯 {g2['title']}"
            row.append(InlineKeyboardButton(label2, callback_data=make_callback_data(f"goals_detail_{g2['id']}")))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("◀️ Înapoi", callback_data=make_callback_data("goals_cancel"))])
    return InlineKeyboardMarkup(keyboard)


def goal_detail_keyboard(goal_id: int, is_completed: bool) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "✏️ Editează", callback_data=make_callback_data(f"goals_edit_{goal_id}")
            ),
            InlineKeyboardButton(
                "➕ Sub-task",
                callback_data=make_callback_data(f"goals_add_subtask_{goal_id}"),
            ),
        ]
    ]
    if not is_completed:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "✅ Completat",
                    callback_data=make_callback_data(f"goals_complete_goal_{goal_id}"),
                ),
                InlineKeyboardButton(
                    "🗑️ Șterge",
                    callback_data=make_callback_data(f"goals_delete_{goal_id}"),
                ),
            ]
        )
    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🗑️ Șterge",
                    callback_data=make_callback_data(f"goals_delete_{goal_id}"),
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                "◀️ Înapoi", callback_data=make_callback_data("goals_active")
            )
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def subtasks_keyboard(subtasks: list, goal_id: int) -> InlineKeyboardMarkup:
    keyboard = []
    for st in subtasks:
        icon = "✅" if st["is_completed"] else "⬜"
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{icon} {st['title']}",
                    callback_data=make_callback_data(
                        f"goals_complete_subtask_{st['id']}"
                    ),
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                "◀️ Înapoi", callback_data=make_callback_data(f"goals_detail_{goal_id}")
            )
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def confirm_delete_goal_keyboard(goal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Confirmă",
                    callback_data=make_callback_data(f"goals_confirm_delete_{goal_id}"),
                ),
                InlineKeyboardButton(
                    "❌ Anulează",
                    callback_data=make_callback_data(f"goals_detail_{goal_id}"),
                ),
            ]
        ]
    )


# ── Skill Tracking ─────────────────────────────────────────────


def skills_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📊 Stats", callback_data=make_callback_data("skills_list")
                ),
                InlineKeyboardButton(
                    "➕ Log", callback_data=make_callback_data("skills_log_list")
                ),
            ],
            [
                InlineKeyboardButton(
                    "📈 Progress", callback_data=make_callback_data("skills_progress")
                ),
                InlineKeyboardButton(
                    "⚙️ Manage", callback_data=make_callback_data("skills_manage")
                ),
            ],
            [
                InlineKeyboardButton(
                    "◀️ Înapoi", callback_data=make_callback_data("skills_cancel")
                )
            ],
        ]
    )


def skills_list_keyboard(
    skills: list, action_prefix: str = "skills_detail_"
) -> InlineKeyboardMarkup:
    keyboard = []
    for i in range(0, len(skills), 2):
        row = []
        s1 = skills[i]
        row.append(InlineKeyboardButton(s1['name'], callback_data=make_callback_data(f"{action_prefix}{s1['id']}")))
        if i + 1 < len(skills):
            s2 = skills[i+1]
            row.append(InlineKeyboardButton(s2['name'], callback_data=make_callback_data(f"{action_prefix}{s2['id']}")))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("➕ Skill Nou", callback_data=make_callback_data("skills_add_new"))])
    keyboard.append([InlineKeyboardButton("◀️ Înapoi", callback_data=make_callback_data("skills_cancel"))])
    return InlineKeyboardMarkup(keyboard)


def skill_detail_keyboard(skill_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📝 Log Value",
                    callback_data=make_callback_data(f"skills_log_entry_{skill_id}"),
                )
            ],
            [
                InlineKeyboardButton(
                    "📊 Istoric",
                    callback_data=make_callback_data(f"skills_history_{skill_id}"),
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑️ Șterge",
                    callback_data=make_callback_data(f"skills_delete_{skill_id}"),
                )
            ],
            [
                InlineKeyboardButton(
                    "◀️ Înapoi", callback_data=make_callback_data("skills_list")
                )
            ],
        ]
    )


def confirm_delete_skill_keyboard(skill_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Confirmă",
                    callback_data=make_callback_data(
                        f"skills_confirm_delete_{skill_id}"
                    ),
                ),
                InlineKeyboardButton(
                    "❌ Anulează",
                    callback_data=make_callback_data(f"skills_detail_{skill_id}"),
                ),
            ]
        ]
    )


# ── Reading module keyboards ────────────────────────────────────────


def reading_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📖 Biblioteca", callback_data=make_callback_data("reading_library")
                ),
                InlineKeyboardButton(
                    "📝 Note", callback_data=make_callback_data("reading_notes")
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Stats", callback_data=make_callback_data("reading_stats_menu")
                ),
                InlineKeyboardButton(
                    "🔄 Update Progress",
                    callback_data=make_callback_data("reading_update_prompt"),
                ),
            ],
            [
                InlineKeyboardButton(
                    "➕ Carte nouă", callback_data=make_callback_data("reading_add")
                ),
                InlineKeyboardButton(
                    "🏁 Finalizează",
                    callback_data=make_callback_data("reading_complete_prompt"),
                ),
            ],
        ]
    )


def reading_stats_period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "7 zile", callback_data=make_callback_data("reading_stats_7")
                ),
                InlineKeyboardButton(
                    "30 zile", callback_data=make_callback_data("reading_stats_30")
                ),
            ],
            [
                InlineKeyboardButton(
                    "Anul acesta",
                    callback_data=make_callback_data("reading_stats_year"),
                ),
                InlineKeyboardButton(
                    "Toate timpurile",
                    callback_data=make_callback_data("reading_stats_all"),
                ),
            ],
            [
                InlineKeyboardButton(
                    "◀️ Înapoi", callback_data=make_callback_data("reading_main")
                )
            ],
        ]
    )


def reading_books_keyboard(
    books: list, action_prefix: str = "reading_detail_"
) -> InlineKeyboardMarkup:
    keyboard = []
    for b in books:
        title = escape_md(b.get("title", "")[:30])
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"📖 {title}",
                    callback_data=make_callback_data(f"{action_prefix}{b['id']}"),
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                "◀️ Înapoi", callback_data=make_callback_data("reading_main")
            )
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def reading_book_detail_keyboard(book_id: int, status: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "🔄 Update pagini",
                callback_data=make_callback_data(f"reading_update_book_{book_id}"),
            ),
            InlineKeyboardButton(
                "📝 Adaugă notă",
                callback_data=make_callback_data(f"reading_note_book_{book_id}"),
            ),
        ],
    ]
    if status == "reading":
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🏁 Marchează terminată",
                    callback_data=make_callback_data(f"reading_finish_book_{book_id}"),
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                "📖 Vezi note",
                callback_data=make_callback_data(f"reading_view_notes_{book_id}"),
            ),
            InlineKeyboardButton(
                "🗑️ Șterge",
                callback_data=make_callback_data(f"reading_delete_book_{book_id}"),
            ),
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                "◀️ Înapoi la bibliotecă",
                callback_data=make_callback_data("reading_library"),
            )
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def reading_confirm_delete_keyboard(book_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Confirmă",
                    callback_data=make_callback_data(
                        f"reading_confirm_delete_{book_id}"
                    ),
                ),
                InlineKeyboardButton(
                    "❌ Anulează",
                    callback_data=make_callback_data(f"reading_detail_{book_id}"),
                ),
            ]
        ]
    )


# ── Health Module Keyboards ──────────────────────────────────────────────


def health_summary_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💧 Apă", callback_data=make_callback_data("health", "log_water")
                ),
                InlineKeyboardButton(
                    "😴 Somn", callback_data=make_callback_data("health", "log_sleep")
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚖️ Greutate",
                    callback_data=make_callback_data("health", "log_weight"),
                ),
                InlineKeyboardButton(
                    "🍎 Nutriție",
                    callback_data=make_callback_data("health", "log_nutrition"),
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Grafic COMPLET",
                    callback_data=make_callback_data("health", "chart"),
                ),
            ],
            [
                InlineKeyboardButton(
                    "📜 Jurnal AZI",
                    callback_data=make_callback_data("health", "today_logs"),
                ),
            ],
        ]
    )


def health_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔙 Înapoi la Dashboard",
                    callback_data=make_callback_data("health", "summary"),
                )
            ],
        ]
    )


# ── Memory Module Keyboards ──────────────────────────────────────────────


def memory_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🗑️ Șterge ultima",
                    callback_data=make_callback_data("memory", "delete_last"),
                ),
                InlineKeyboardButton(
                    "🧹 Șterge tot",
                    callback_data=make_callback_data("memory", "clear_all"),
                ),
            ],
            [
                InlineKeyboardButton(
                    "✨ Optimizează (AI)",
                    callback_data=make_callback_data("memory", "optimize"),
                ),
                InlineKeyboardButton(
                    "📊 Categorii",
                    callback_data=make_callback_data("memory", "view_categories"),
                ),
            ],
            [
                InlineKeyboardButton(
                    "◀️ Înapoi", callback_data=make_callback_data("chat", "main")
                ),
            ],
        ]
    )

# ── Travel module keyboards ──────────────────────────────────────────

def travel_list_keyboard(items: list, list_name: str) -> InlineKeyboardMarkup:
    keyboard = []
    # Build buttons for unpacked items primarily
    for i in range(0, len(items), 2):
        row = []
        item1 = items[i]
        label1 = f"⬜ {item1['item'][:15]}" if not item1['is_packed'] else f"✅ {item1['item'][:15]}"
        row.append(
            InlineKeyboardButton(
                label1,
                callback_data=make_callback_data("travel", "toggle", item1["id"], list_name),
            )
        )
        
        if i + 1 < len(items):
            item2 = items[i+1]
            label2 = f"⬜ {item2['item'][:15]}" if not item2['is_packed'] else f"✅ {item2['item'][:15]}"
            row.append(
                InlineKeyboardButton(
                    label2,
                    callback_data=make_callback_data("travel", "toggle", item2["id"], list_name),
                )
            )
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🧹 Resetează", callback_data=make_callback_data("travel", "clear", list_name)),
        InlineKeyboardButton("📋 Vezi lista", callback_data=make_callback_data("travel", "list", list_name))
    ])
    return InlineKeyboardMarkup(keyboard)

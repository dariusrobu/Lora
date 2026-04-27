from bot.callback_utils import make_callback_data
from typing import Dict, Any, Tuple, Optional
from bot.formatter import escape_md
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import db.queries.goals as goal_queries


async def handle_goal_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    if intent == "add_goal":
        title = data.get("title")
        description = data.get("description")
        category = data.get("category", "Personal")

        goal = await goal_queries.add_goal(pool, title, description, category)
        return f"🎯 Obiectiv adăugat: *{escape_md(goal['title'])}*", None

    elif intent == "view_goals":
        text, markup = await get_goals_dashboard(pool)
        return text, markup

    elif intent == "add_subtask":
        goal_title = data.get("title")
        task_title = data.get("task_title")

        goal = await goal_queries.get_goal_by_title(pool, goal_title)
        if not goal:
            return f"❌ Nu am găsit obiectivul '{escape_md(goal_title)}'.", None

        await goal_queries.add_subtask(pool, goal["id"], task_title)
        return (
            f"✅ Sub-task adăugat la *{escape_md(goal['title'])}*: {escape_md(task_title)}",
            None,
        )

    elif intent == "complete_subtask":
        goal_title = data.get("title")
        task_title = data.get("task_title")

        goal = await goal_queries.get_goal_by_title(pool, goal_title)
        if not goal:
            return f"❌ Nu am găsit obiectivul '{escape_md(goal_title)}'.", None

        task = await goal_queries.get_goal_task_by_title(pool, goal["id"], task_title)
        if not task:
            return (
                f"❌ Nu am găsit sub-task-ul '{escape_md(task_title)}' în obiectivul *{escape_md(goal['title'])}*.",
                None,
            )

        await goal_queries.complete_subtask(pool, task["id"])

        updated_goal = await goal_queries.get_goal_by_id(pool, goal["id"])
        return (
            f"✅ Sub-task finalizat! Progres *{escape_md(updated_goal['title'])}*: {updated_goal['progress']}%",
            None,
        )

    elif intent == "complete_goal":
        goal_title = data.get("title")
        goal = await goal_queries.get_goal_by_title(pool, goal_title)
        if not goal:
            return f"❌ Nu am găsit obiectivul '{escape_md(goal_title)}'.", None
        await goal_queries.complete_goal(pool, goal["id"])
        return f"🎉 Goal completat: *{escape_md(goal['title'])}*", None

    elif intent == "delete_goal":
        goal_title = data.get("title")
        goal = await goal_queries.get_goal_by_title(pool, goal_title)
        if not goal:
            return f"❌ Nu am găsit obiectivul '{escape_md(goal_title)}'.", None
        await goal_queries.delete_goal(pool, goal["id"])
        return f"🗑️ Goal șters: *{escape_md(goal['title'])}*", None

    elif intent == "update_goal":
        goal_title = data.get("title")
        goal = await goal_queries.get_goal_by_title(pool, goal_title)
        if not goal:
            return f"❌ Nu am găsit obiectivul '{escape_md(goal_title)}'.", None

        new_title = data.get("new_title", goal["title"])
        desc = data.get("description", goal["description"])
        cat = data.get("category", goal["category"])
        await goal_queries.update_goal(pool, goal["id"], new_title, desc, cat)
        return f"✅ Obiectiv actualizat: *{escape_md(new_title)}*", None

    return "Această acțiune pentru goals nu este încă suportată\\.", None


# ── Dashboard Rendering ────────────────────────────────────────────────


async def get_goals_dashboard(pool) -> Tuple[str, Any]:
    overview = await goal_queries.get_goals_overview(pool)
    active = overview.get("total_active", 0)
    completed = overview.get("total_completed", 0)
    risk = overview.get("total_risk", 0)

    lines = [
        "🎯 *Goals Dashboard*",
        "━━━━━━━━━━━━━━━",
        f"Active: *{active}* · Completate: *{completed}* · ⚠️ În pericol: *{risk}*",
    ]
    from bot.keyboards import goals_main_keyboard

    return "\n".join(lines), goals_main_keyboard()


async def get_active_goals(pool) -> Tuple[str, Any]:
    goals = await goal_queries.get_all_goals(pool)
    from bot.keyboards import goals_list_keyboard

    if not goals:
        return "🎯 Nu ai obiective active momentan\\.", goals_list_keyboard([])

    lines = ["🎯 *Goals Active*\n"]
    current_cat = None
    for g in goals:
        if g["category"] != current_cat:
            current_cat = g["category"]
            lines.append(f"*{escape_md(current_cat)}*")

        progress = g.get("progress", 0)
        filled = int(progress / 10)
        bar = "█" * filled + "░" * (10 - filled)
        lines.append(f"• {escape_md(g['title'])} — `{bar}` {progress}%")

    return "\n".join(lines), goals_list_keyboard(goals)


async def get_completed_goals(pool) -> Tuple[str, Any]:
    goals = await goal_queries.get_completed_goals(pool)
    from telegram import InlineKeyboardMarkup

    if not goals:
        return "✅ Nu ai obiective finalizate încă\\.", InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "◀️ Înapoi", callback_data=make_callback_data("goals", "cancel")
                    )
                ]
            ]
        )

    lines = ["✅ *Obiective Completate*\n"]
    for g in goals:
        date_str = g["updated_at"].strftime("%d %b %Y") if g["updated_at"] else "N\\/A"
        lines.append(f"• {escape_md(g['title'])} — {escape_md(date_str)}")

    return "\n".join(lines), InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "◀️ Înapoi", callback_data=make_callback_data("goals", "cancel")
                )
            ]
        ]
    )


async def get_goal_detail(pool, goal_id: int) -> Tuple[str, Any]:
    goal_data = await goal_queries.get_goal_by_id(pool, goal_id)
    if not goal_data:
        from bot.keyboards import goals_main_keyboard

        return "❌ Goal-ul nu mai există\\.", goals_main_keyboard()

    title = escape_md(goal_data["title"])
    category = escape_md(goal_data["category"])
    progress = goal_data.get("progress", 0)
    filled = int(progress / 10)
    bar = "█" * filled + "░" * (10 - filled)
    is_completed = goal_data["status"] == "completed"

    tasks = goal_data.get("tasks", [])
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t["is_completed"])

    lines = [
        f"🎯 *{title}*",
        "━━━━━━━━━━━━━━━",
        f"Categorie: *{category}*",
        f"Progres: `{bar}` {progress}%",
    ]
    if total_tasks > 0:
        lines.append(f"Sub-tasks: *{completed_tasks}/{total_tasks}* completate\n")
        for t in tasks:
            icon = "✅" if t["is_completed"] else "⬜"
            lines.append(f"{icon} {escape_md(t['title'])}")

    if goal_data.get("description"):
        lines.append(f"\n📝 Descriere: {escape_md(goal_data['description'])}")

    days_ago = "N\\/A"
    if goal_data.get("updated_at"):
        from datetime import datetime

        delta = (datetime.now() - goal_data["updated_at"].replace(tzinfo=None)).days
        days_ago = f"{delta} zile în urmă" if delta > 0 else "Azi"

    lines.append(f"\n_Ultimul update: {days_ago}_")

    from bot.keyboards import goal_detail_keyboard

    return "\n".join(lines), goal_detail_keyboard(goal_id, is_completed)


async def get_goals_overview(pool) -> Tuple[str, Any]:
    overview = await goal_queries.get_goals_overview(pool)
    lines = ["📊 *Overview Goals*", "━━━━━━━━━━━━━━━"]

    cats = overview.get("categories", [])
    if not cats:
        lines.append("Niciun goal existent\\.")
    else:
        for c in cats:
            cat_name = escape_md(c["category"])
            parts = []
            if c["active_count"] > 0:
                parts.append(f"*{c['active_count']} active*")
            if c["completed_count"] > 0:
                parts.append(f"*{c['completed_count']} completate*")
            if c["risk_count"] > 0:
                parts.append(f"⚠️ *{c['risk_count']} în pericol*")

            summary = " · ".join(parts) if parts else "0"
            lines.append(f"• {cat_name}: {summary}")

    from telegram import InlineKeyboardMarkup

    return "\n".join(lines), InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "◀️ Înapoi", callback_data=make_callback_data("goals", "cancel")
                )
            ]
        ]
    )


# ── Callback Flow ──────────────────────────────────────────────────
async def handle_goals_callback(query, pool, data: str):
    from core.state import set_state, clear_state

    parts = data.split("_")

    try:
        if data == "goals_cancel":
            await clear_state(pool)
            text, markup = await get_goals_dashboard(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif data == "goals_overview":
            text, markup = await get_goals_overview(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif data == "goals_active":
            text, markup = await get_active_goals(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif data == "goals_completed":
            text, markup = await get_completed_goals(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif data == "goals_new":
            from bot.keyboards import goals_category_keyboard

            await query.edit_message_text(
                "➕ *Goal Nou*\n\nAlege categoria:",
                parse_mode="MarkdownV2",
                reply_markup=goals_category_keyboard("new"),
            )

        elif data.startswith("goals_category_"):
            # goals_category_{category}_{context}
            context = parts[-1]
            category = data.replace("goals_category_", "").rsplit("_", 1)[0]

            if context == "new":
                await set_state(
                    pool,
                    "awaiting_goal_title",
                    "goals",
                    "add_goal",
                    None,
                    {"category": category},
                )
                from telegram import InlineKeyboardMarkup, InlineKeyboardButton

                await query.edit_message_text(
                    f"Categoria: *{category}*\n\nScrie titlul obiectivului:",
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Anulează",
                                    callback_data=make_callback_data("goals", "cancel"),
                                )
                            ]
                        ]
                    ),
                )

        elif data.startswith("goals_detail_"):
            goal_id = int(parts[-1])
            await clear_state(pool)
            text, markup = await get_goal_detail(pool, goal_id)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif data.startswith("goals_edit_"):
            goal_id = int(parts[-1])
            await query.answer(
                "Folosește Gemini vocal ('editează goal-ul X') pentru editări\\.",
                show_alert=True,
            )

        elif data.startswith("goals_add_subtask_"):
            goal_id = int(parts[-1])
            await set_state(
                pool, "awaiting_subtask_title", "goals", "add_subtask", goal_id
            )
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton

            await query.edit_message_text(
                "➕ *Adaugă sub-task*\n\nScrie titlul sub-task-ului:",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "❌ Anulează",
                                callback_data=make_callback_data(
                                    "goals", "detail", goal_id
                                ),
                            )
                        ]
                    ]
                ),
            )

        elif data.startswith("goals_complete_subtask_"):
            subtask_id = int(parts[-1])
            await goal_queries.complete_subtask(pool, subtask_id)

            # Recalculate and go back to goal detail
            goal_id = await pool.fetchval(
                "SELECT goal_id FROM goal_tasks WHERE id = $1", subtask_id
            )
            text, markup = await get_goal_detail(pool, goal_id)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif data.startswith("goals_complete_goal_"):
            goal_id = int(parts[-1])
            await goal_queries.complete_goal(pool, goal_id)
            await query.answer("Goal completat! 🎉")
            text, markup = await get_goal_detail(pool, goal_id)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif data.startswith("goals_delete_"):
            goal_id = int(parts[-1])
            from bot.keyboards import confirm_delete_goal_keyboard

            await query.edit_message_text(
                "⚠️ Ești sigur că vrei să ștergi acest goal și toate sub-taskurile lui?",
                reply_markup=confirm_delete_goal_keyboard(goal_id),
            )

        elif data.startswith("goals_confirm_delete_"):
            goal_id = int(parts[-1])
            await goal_queries.delete_goal(pool, goal_id)
            await query.answer("Goal șters\\.")
            text, markup = await get_goals_dashboard(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

    except Exception as e:
        print(f"Error in handle_goals_callback: {e}")
        await query.answer("A apărut o eroare\\.", show_alert=True)


# ── Message Flow (Stateful) ─────────────────────────────────────────
async def handle_goals_message(update, pool, state: dict, text: str):
    from core.state import set_state, clear_state

    action = state.get("action")
    item_id = state.get("item_id")
    extra = state.get("extra") or {}

    try:
        if action == "add_goal":
            if state["state_type"] == "awaiting_goal_title":
                title = text.strip()
                await set_state(
                    pool,
                    "awaiting_goal_description",
                    "goals",
                    "add_goal",
                    None,
                    {"category": extra.get("category"), "title": title},
                )
                from telegram import InlineKeyboardMarkup, InlineKeyboardButton

                await update.message.reply_text(
                    "Scurtă descriere? (sau /skip)",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Anulează",
                                    callback_data=make_callback_data("goals", "cancel"),
                                )
                            ]
                        ]
                    ),
                )

            elif state["state_type"] == "awaiting_goal_description":
                desc = None if text.strip() == "/skip" else text.strip()
                title = extra.get("title")
                category = extra.get("category", "Personal")

                goal = await goal_queries.add_goal(pool, title, desc, category)
                await clear_state(pool)
                await update.message.reply_text("✅ Goal salvat!")

                text_md, markup = await get_goal_detail(pool, goal["id"])
                await update.message.reply_text(
                    text_md, parse_mode="MarkdownV2", reply_markup=markup
                )

        elif action == "add_subtask":
            if state["state_type"] == "awaiting_subtask_title":
                title = text.strip()
                await goal_queries.add_subtask(pool, item_id, title)
                await clear_state(pool)

                text_md, markup = await get_goal_detail(pool, item_id)
                await update.message.reply_text(
                    text_md, parse_mode="MarkdownV2", reply_markup=markup
                )

    except Exception as e:
        print(f"Error in goals state handler: {e}")
        await update.message.reply_text(f"❌ A apărut o eroare: {e}")

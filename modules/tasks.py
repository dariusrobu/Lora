from typing import Dict, Any, Tuple
from datetime import datetime
import re
import db.queries.tasks as task_queries
from bot.formatter import escape_md


def parse_add_task_text(text: str) -> Dict[str, Any] | None:
    """
    Fast regex parser for add_task intents.
    Bypasses Gemini for simple, unambiguous patterns.
    Returns dict with 'title', 'project', 'priority', 'due_date' or None if no match.
    """
    original = text.strip()

    # Pattern 1: "adauga/add task proiectul/to project X: title"
    m = re.match(
        r"(?:adaug[ăa]|add|create)\s+(?:task|task-ul|taskul)\s+(?:proiectul|to project)\s+(\S+?)\s*:\s*(.+)$",
        original,
        re.IGNORECASE,
    )
    if m:
        return {"project": m.group(1), "title": m.group(2).strip()}

    # Pattern 1b: "add task project X: title" (flexible, handles typos like "tasj")
    m = re.match(
        r"(?:adaug[ăa]|add|creat[ăe])\s+ta?s?k?\w*\s+project\s+(\S+?)\s*:\s*(.+)$",
        original,
        re.IGNORECASE,
    )
    if m:
        return {"project": m.group(1), "title": m.group(2).strip()}

    # Pattern 2: "adauga/add task prioritate/priority X: title"
    m = re.match(
        r"(?:adaug[ăa]|add|create)\s+(?:task|task-ul|taskul)\s+(?:prioritate[tă]?|priority)\s+(\S+)\s*:\s*(.+)$",
        original,
        re.IGNORECASE,
    )
    if m:
        return {
            "priority": _normalize_priority(m.group(1)),
            "title": m.group(2).strip(),
        }

    # Pattern 3: "adauga/add task: title" or "adaug/add task title"
    m = re.match(
        r"(?:adaug[ăa]|add|create)\s+(?:task|task-ul|taskul)\s*[:\-]?\s*(.+)$",
        original,
        re.IGNORECASE,
    )
    if m:
        return {"title": m.group(1).strip()}

    # Pattern 4: Just extract everything after "add task" as title
    m = re.match(
        r"(?:adaug[ăa]|add|creat[ăe])\s+ta?s?k?\w*\s+(.+)$",
        original,
        re.IGNORECASE,
    )
    if m:
        rest = m.group(1).strip()
        # Try to split by colon for project: title
        parts = rest.split(":", 1)
        if len(parts) == 2:
            return {"project": parts[0].strip(), "title": parts[1].strip()}
        return {"title": rest}

    return None


def _normalize_priority(p: str) -> str:
    """Normalize priority string to low/medium/high."""
    p = p.lower().strip()
    if p in ("high", "mare", "înaltă", "important", "urgent", "h"):
        return "high"
    if p in ("low", "mică", "low", "l"):
        return "low"
    return "medium"


async def handle_tasks_callback(query, pool, data: str) -> None:
    """Processes task-related callback queries (tasks: and projects:)."""
    from core.state import clear_state, set_state
    from db.queries.projects import delete_project, get_project, update_project_status
    from bot.keyboards import (
        tasks_confirm_delete_keyboard,
        projects_confirm_delete_keyboard,
    )

    parts = data.split(":")
    module = parts[0]
    action = parts[1]

    if module == "tasks":
        if action == "main":
            text, markup = await get_tasks_dashboard(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif action == "projects_list":
            text, markup = await get_projects_list_view(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif action == "list_all":
            text, markup = await handle_task_intent(pool, "list_tasks", {})
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif action == "recent_done":
            tasks = await task_queries.list_tasks(pool, status="done")
            if not tasks:
                await query.answer("Nu ai task-uri finalizate recent.")
                return

            lines = ["✅ *Task\\-uri finalizate recent:*"]
            for t in tasks[:10]:
                lines.append(f"• ~{escape_md(t['title'])}~")

            from bot.keyboards import tasks_main_keyboard

            await query.edit_message_text(
                "\n".join(lines),
                parse_mode="MarkdownV2",
                reply_markup=tasks_main_keyboard(),
            )

        elif action == "project_view":
            project_id = int(parts[2])
            text, markup = await get_project_tasks_view(pool, project_id)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif action == "complete":
            task_id = int(parts[2])
            is_list = len(parts) > 3 and parts[3] == "list"

            task = await task_queries.get_task(pool, task_id)
            await task_queries.complete_task(pool, task_id)
            task_title = task["title"] if task else "Task"
            await query.answer(f"✅ Bifat: {task_title}")

            if is_list:
                text, markup = await handle_task_intent(pool, "list_tasks", {})
                await query.edit_message_text(
                    text, parse_mode="MarkdownV2", reply_markup=markup
                )
            else:
                await query.edit_message_text(
                    f"✅ Task completat: *{escape_md(task_title)}*",
                    parse_mode="MarkdownV2",
                )

        elif action == "delete":
            task_id = int(parts[2])
            task = await task_queries.get_task(pool, task_id)
            task_title = task["title"] if task else "Task"

            await set_state(pool, "awaiting_confirmation", "tasks", "delete", task_id)
            await query.edit_message_text(
                f"Are you sure you want to delete *{escape_md(task_title)}*?",
                parse_mode="MarkdownV2",
                reply_markup=tasks_confirm_delete_keyboard(task_id),
            )

        elif action == "delete_confirmed":
            task_id = int(parts[2])
            task = await task_queries.get_task(pool, task_id)
            task_title = task["title"] if task else "Task"
            await task_queries.delete_task(pool, task_id)
            await query.answer("🗑️ Task șters.")
            await clear_state(pool)
            text, markup = await get_tasks_dashboard(pool)
            await query.edit_message_text(
                f"🗑️ Task șters: *{escape_md(task_title)}*\n\n{text}",
                parse_mode="MarkdownV2",
                reply_markup=markup,
            )

        elif action == "new":
            await set_state(pool, "awaiting_task_input", "tasks", "add", None)
            await query.edit_message_text(
                "📝 *Adaugă task nou*\n\nScrie titlul task\\-ului \\(și opțional data sau prioritatea\\)\\.\n_Ex: Cumpără becuri mâine \\!\\!high_",
                parse_mode="MarkdownV2",
            )

        elif action == "new_for_project":
            project_id = int(parts[2])
            await set_state(pool, "awaiting_task_input", "tasks", "add", project_id)
            await query.edit_message_text(
                "📝 *Adaugă task în proiect*\n\nScrie titlul task\\-ului\\.\nLora îl va asocia automat cu acest proiect\\.",
                parse_mode="MarkdownV2",
            )

        elif action == "edit":
            task_id = int(parts[2])
            task = await task_queries.get_task(pool, task_id)
            task_title = task["title"] if task else "Task"
            await set_state(pool, "awaiting_edit_field", "tasks", "edit", task_id)
            await query.edit_message_text(
                f"What would you like to change about *{escape_md(task_title)}*?\\n\\n"
                f"You can say things like:\\n"
                f"• change title to 'Buy oat milk'\\n"
                f"• set due date to Friday\\n"
                f"• change priority to high",
                parse_mode="MarkdownV2",
            )

        elif action == "cancel":
            await clear_state(pool)
            await query.answer("Anulat.")
            text, markup = await get_tasks_dashboard(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

    elif module == "projects":
        if action == "new":
            await set_state(pool, "awaiting_project_input", "projects", "add", None)
            await query.edit_message_text(
                "📂 *Creează proiect nou*\n\nScrie numele proiectului și o scurtă descriere\\.\n_Ex: Licență, Planificare și scriere capitol 1_",
                parse_mode="MarkdownV2",
            )

        elif action == "delete":
            project_id = int(parts[2])
            project = await get_project(pool, project_id)
            project_name = project["name"] if project else "Proiect"

            await query.edit_message_text(
                f"⚠️ Ești sigur că vrei să ștergi proiectul *{escape_md(project_name)}*?\\n\\n"
                f"Task\\-urile asociate vor rămâne fără proiect, dar nu vor fi șterse\\.",
                parse_mode="MarkdownV2",
                reply_markup=projects_confirm_delete_keyboard(project_id),
            )

        elif action == "delete_confirmed":
            project_id = int(parts[2])
            await delete_project(pool, project_id)
            await query.answer("🗑️ Proiect șters.")
            text, markup = await get_projects_list_view(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

        elif action == "complete":
            project_id = int(parts[2])
            await update_project_status(pool, project_id, "done")
            await query.answer("🏁 Proiect marcat ca finalizat!")
            text, markup = await get_projects_list_view(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )

    await query.answer()


async def handle_task_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any]:
    """Handles task-related intents and returns reply text + keyboard."""

    if intent == "add_task":
        title = (
            data.get("title")
            or data.get("description")
            or data.get("name")
            or data.get("text")
        )
        priority: str | None = data.get("priority")
        project_name: str | None = data.get("project") or data.get("project_name")
        if not title:
            # Fallback: try to parse from original user message
            user_msg = data.get("_user_message", "")
            if user_msg:
                parsed = parse_add_task_text(user_msg)
                if parsed:
                    title = parsed.get("title")
                    if not title:
                        title = parsed.get("name")
                    if not project_name and parsed.get("project"):
                        project_name = parsed.get("project")
                    if not priority and parsed.get("priority"):
                        priority = parsed.get("priority")
            if not title:
                return "What task should I add? (I didn't catch the title)", None

        due_date_str = data.get("due_date")
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except Exception:
                pass

        priority = priority or "medium"
        project_id = data.get("project_id") or data.get("id")
        project_name = project_name or data.get("project") or data.get("project_name")

        if not project_id and project_name:
            import db.queries.projects as project_queries

            # Get only active/on-hold projects for linking
            projects = await project_queries.list_projects(
                pool, exclude_status="archived"
            )
            # Try exact match first
            match = next(
                (p for p in projects if p["name"].lower() == project_name.lower()), None
            )
            # If no exact match, try partial match
            if not match:
                match = next(
                    (p for p in projects if project_name.lower() in p["name"].lower()),
                    None,
                )

            if match:
                project_id = match["id"]
                # Update project_name to the matched one for the reply
                project_name = match["name"]

        task_id = await task_queries.add_task(
            pool,
            title=title,
            notes=data.get("notes"),
            priority=data.get("priority", "medium"),
            due_date=due_date,
            project_id=project_id,
            is_recurring=data.get("is_recurring", False),
            recurrence=data.get("recurrence"),
        )

        from bot.keyboards import task_keyboard

        return f"Done ✅ Added *{escape_md(title)}*", task_keyboard(task_id)

    elif intent == "list_tasks":
        project_id: int | None = data.get("project_id")
        project_name: str | None = data.get("project") or data.get("project_name")

        if not project_id and project_name:
            import db.queries.projects as project_queries

            project = await project_queries.get_project_by_name(pool, project_name)
            if project:
                project_id = project["id"]

        tasks: list[dict[str, Any]] = await task_queries.list_tasks(
            pool, project_id=project_id
        )
        if not tasks:
            msg = (
                f"Momentan nu ai niciun task activ pentru proiectul *{escape_md(project_name)}*\\! 🎉"
                if project_name
                else "Niciun task restant\\! 🎉"
            )
            return msg, None

        # Group tasks by project_name (query already sorted by project_name NULLS LAST)
        from collections import OrderedDict
        from datetime import date as _date

        today: _date = _date.today()
        groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        no_project_key: str = "Fără proiect"

        for t in tasks:
            key: str = t.get("project_name") or no_project_key
            groups.setdefault(key, []).append(t)

        # Move "Fără proiect" to the end if it exists
        if no_project_key in groups and list(groups.keys())[-1] != no_project_key:
            no_proj_tasks = groups.pop(no_project_key)
            groups[no_project_key] = no_proj_tasks

        lines: list[str] = ["📋 *Tasks*"]

        for group_name, group_tasks in groups.items():
            lines.append("")
            lines.append(f"*{escape_md(group_name)}*")
            for t in group_tasks:
                prefix: str = ""
                if t.get("due_date") and t["due_date"] < today:
                    prefix = "🔴 "
                elif t.get("priority") == "high":
                    prefix = "⚠️ "
                lines.append(f"{prefix}• {escape_md(t['title'])}")

        from bot.keyboards import task_list_keyboard

        return "\n".join(lines), task_list_keyboard(tasks, back_callback="tasks:main")

        from bot.keyboards import task_list_keyboard

        return "\n".join(lines), task_list_keyboard(tasks, back_callback="tasks:main")

    elif intent == "complete_task":
        # Usually Gemini finds the ID or we get it from a button
        task_id = data.get("id")
        if not task_id:
            return "Which task would you like to complete?", None

        await task_queries.complete_task(pool, task_id)
        task = await task_queries.get_task(pool, task_id)
        return f"Completed ✅ *{escape_md(task['title'])}*", None

    elif intent == "edit_task":
        task_id = data.get("id")
        # Try to find task by search term if ID is missing
        search_term = str(
            data.get("query")
            or data.get("search")
            or data.get("old_title")
            or data.get("name")
            or ""
        )

        if not task_id and search_term:
            if search_term.isdigit():
                task_id = int(search_term)
            else:
                matches = await task_queries.get_tasks_by_title(pool, search_term)
                if len(matches) == 1:
                    task_id = matches[0]["id"]
                elif len(matches) > 1:
                    from bot.keyboards import task_list_keyboard

                    return (
                        f"I found multiple tasks matching *{escape_md(search_term)}*. Which one did you mean?",
                        task_list_keyboard(matches, back_callback="tasks:main"),
                    )

        if not task_id:
            return "Which task should I edit?", None

        # Clean up data to only include valid update fields
        upd = {}
        # If Gemini provided 'new_title', use it. If it provided 'title' and we found the task via search_term, 'title' is likely the new one.
        new_title = data.get("new_title") or (
            data.get("title") if search_term else None
        )
        if new_title:
            upd["title"] = new_title

        for k in ["notes", "priority", "due_date"]:
            if k in data:
                upd[k] = data[k]

        if not upd:
            return (
                "What should I change about it? (e.g., 'Rename it to X' or 'Set priority to high')",
                None,
            )

        await task_queries.update_task(pool, task_id, **upd)
        task = await task_queries.get_task(pool, task_id)
        from bot.keyboards import task_keyboard

        return f"Updated ✅ *{escape_md(task['title'])}*", task_keyboard(task_id)

    elif intent == "delete_task":
        task_id = data.get("id")
        title = str(
            data.get("title")
            or data.get("name")
            or data.get("text")
            or data.get("query")
            or ""
        )

        if not task_id and title:
            if title.isdigit():
                task_id = int(title)
            else:
                matches = await task_queries.get_tasks_by_title(pool, title)
                if len(matches) == 1:
                    task_id = matches[0]["id"]
                elif len(matches) > 1:
                    from bot.keyboards import task_list_keyboard

                    return (
                        f"I found multiple tasks matching *{escape_md(title)}*. Which one did you mean?",
                        task_list_keyboard(matches, back_callback="tasks:main"),
                    )
            # if 0 matches, we'll fall through to "Which task..."

        if not task_id:
            return "Which task should I delete?", None

        task = await task_queries.get_task(pool, task_id)
        if not task:
            return "I couldn't find that task.", None


async def get_tasks_dashboard(pool) -> Tuple[str, Any]:
    """Returns a high-level overview of pending tasks grouped by project."""
    tasks = await task_queries.list_tasks(pool, status="pending")
    if not tasks:
        from bot.keyboards import tasks_main_keyboard

        return (
            "Nu ai niciun task activ în acest moment\\! 🎉\nPoți adăuga unul nou prin limbaj natural sau folosind butonul de mai jos\\.",
            tasks_main_keyboard(),
        )

    # Simple count
    total = len(tasks)
    overdue = sum(
        1 for t in tasks if t.get("due_date") and t["due_date"] < datetime.now().date()
    )

    # Grouping for the summary
    from collections import Counter

    projects = Counter(t.get("project_name") or "Fără proiect" for t in tasks)

    lines = ["📋 *Tasks Overview*\n"]
    lines.append(f"✅ *{total}* task\\-uri active pe *{len(projects)}* proiecte\\.")
    if overdue > 0:
        lines.append(f"🔴 *{overdue}* sunt restante\\!")

    lines.append("\n*Repartiție pe proiecte:*")
    for proj, count in projects.items():
        lines.append(f"• {escape_md(proj)}: {count}")

    from bot.keyboards import tasks_main_keyboard

    return "\n".join(lines), tasks_main_keyboard()


async def get_projects_list_view(pool) -> Tuple[str, Any]:
    """Lists all projects with their task counts."""
    import db.queries.projects as project_queries

    projects = await project_queries.list_projects(pool, exclude_status="archived")

    projects_with_counts = []
    for p in projects:
        tasks = await task_queries.list_tasks(pool, project_id=p["id"])
        projects_with_counts.append(
            {"id": p["id"], "name": p["name"], "task_count": len(tasks)}
        )

    msg = "📂 *Proiectele Tale*\n\nAlege un proiect pentru a vedea detaliile sau a adăuga task\\-uri noi\\."
    from bot.keyboards import tasks_projects_keyboard

    return msg, tasks_projects_keyboard(projects_with_counts)


async def get_project_tasks_view(pool, project_id: int) -> Tuple[str, Any]:
    """Lists tasks for a specific project."""
    import db.queries.projects as project_queries

    project = await project_queries.get_project(pool, project_id)
    if not project:
        return "Proiectul nu a fost găsit\\.", None

    tasks = await task_queries.list_tasks(pool, project_id=project_id)

    lines = [f"📂 *Proiect: {escape_md(project['name'])}*"]
    if project.get("description"):
        lines.append(f"_{escape_md(project['description'])}_")
    lines.append("")

    if not tasks:
        lines.append("Niciun task activ în acest proiect\\.")
    else:
        for t in tasks:
            prefix = (
                "🔴 "
                if t.get("due_date") and t["due_date"] < datetime.now().date()
                else "• "
            )
            lines.append(f"{prefix}{escape_md(t['title'])}")

    from bot.keyboards import task_list_keyboard

    return "\n".join(lines), task_list_keyboard(
        tasks, back_callback="tasks:projects_list"
    )

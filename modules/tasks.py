from bot.callback_utils import make_callback_data
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, date, timedelta
import re
import asyncio
import db.queries.tasks as task_queries
from bot.formatter import escape_md
from core.council import get_decisions, send_feedback_to_cto


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
    # Simplified pattern that handles "adaug task:" as a unit
    m = re.match(
        r"(?:adaug|add|create)\s*task\s*[:\-]?\s*(.+)$",
        original,
        re.IGNORECASE,
    )
    if m:
        return {"title": m.group(1).strip()}

    # Pattern 4: Just extract everything after "add task" as title
    m = re.match(
        r"(?:adaug|add|create)\s*task\s+(.+)$",
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
            text, markup, _ = await handle_task_intent(pool, "list_tasks", {})
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

            # Immediate sync to Reminders
            try:
                from core.icloud import sync_tasks_to_reminders

                asyncio.create_task(sync_tasks_to_reminders(pool))
            except Exception as e:
                print(f"Error triggering task sync: {e}")

            if is_list:
                text, markup, _ = await handle_task_intent(pool, "list_tasks", {})
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
                f"Sigur vrei să ștergi task-ul *{escape_md(task_title)}*?",
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

            from bot.keyboards import tasks_undo_delete_keyboard

            await query.edit_message_text(
                f"🗑️ Am șters task-ul: *{escape_md(task_title)}*",
                parse_mode="MarkdownV2",
                reply_markup=tasks_undo_delete_keyboard(task_id),
            )

        elif action == "undo_delete":
            task_id = int(parts[2])
            await task_queries.restore_task(pool, task_id)
            task = await task_queries.get_task(pool, task_id)
            task_title = task["title"] if task else "Task"
            await query.answer("↩️ Task restaurat.")

            text, markup = await get_tasks_dashboard(pool)
            await query.edit_message_text(
                f"↩️ Am restaurat task-ul: *{escape_md(task_title)}*\n\n{text}",
                parse_mode="MarkdownV2",
                reply_markup=markup,
            )

        elif action == "new":
            await set_state(pool, "awaiting_task_input", "tasks", "add", None)
            prompt = "📝 *Adaugă task nou*\n\nScrie titlul task\\-ului \\(și opțional data sau prioritatea\\)\\.\n_Ex: Cumpără becuri mâine \\!\\!high_"
            await query.edit_message_text(
                prompt,
                parse_mode="MarkdownV2",
            )
            await _save_prompt_to_conversation(pool, prompt)

        elif action == "new_for_project":
            project_id = int(parts[2])
            await set_state(pool, "awaiting_task_input", "tasks", "add", project_id)
            prompt = "📝 *Adaugă task în proiect*\n\nScrie titlul task\\-ului\\.\nLora îl va asocia automat cu acest proiect\\."
            await query.edit_message_text(
                prompt,
                parse_mode="MarkdownV2",
            )
            await _save_prompt_to_conversation(pool, prompt)

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
            prompt = "📂 *Creează proiect nou*\n\nScrie numele proiectului și o scurtă descriere\\.\n_Ex: Licență, Planificare și scriere capitol 1_"
            await query.edit_message_text(
                prompt,
                parse_mode="MarkdownV2",
            )
            await _save_prompt_to_conversation(pool, prompt)

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

        elif action == "edit":
            project_id = int(parts[2])
            project = await get_project(pool, project_id)
            if not project:
                await query.answer("Proiect negăsit.")
                return
            await set_state(
                pool, "awaiting_project_edit", "projects", "edit", project_id
            )
            await query.edit_message_text(
                f"✏️ *Editează proiect: {escape_md(project['name'])}*\n\n"
                f"Scrie noua descriere sau cuvântul *delete* pentru a șterge proiectul\\.\n\n"
                f"_Descriere curentă:_ {escape_md(project.get('description') or '—')}_",
                parse_mode="MarkdownV2",
            )

        elif action == "complete":
            project_id = int(parts[2])
            await update_project_status(pool, project_id, "done")
            await query.answer("🏁 Proiect marcat ca finalizat!")
            text, markup = await get_projects_list_view(pool)
            await query.edit_message_text(
                text, parse_mode="MarkdownV2", reply_markup=markup
            )


async def handle_task_intent(
    pool, intent: str, data: Dict[str, Any], user_id: int = None, bot=None
) -> Tuple[str, Any, Optional[int]]:
    """Handles task-related intents and returns reply text + keyboard + item_id."""

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
                return "Ce task vrei să adaugi? (N-am înțeles titlul)", None, None

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

        # Immediate sync to Reminders
        try:
            from core.icloud import sync_tasks_to_reminders

            asyncio.create_task(sync_tasks_to_reminders(pool))
        except Exception as e:
            print(f"Error triggering task sync: {e}")

        from bot.keyboards import task_keyboard

        reply_msg = f"Am adăugat ✅ *{escape_md(title)}*"
        if due_date:
            from bot.formatter import format_date_short

            reply_msg += f" (până pe {format_date_short(due_date)})"
        if project_name:
            reply_msg += f" în proiectul *{escape_md(project_name)}*"

        # --- PROACTIVE MEMORY: Find similar tasks ---
        from core.config import TELEGRAM_USER_ID

        similar = await task_queries.find_similar_tasks(pool, title, TELEGRAM_USER_ID)
        if similar:
            s = similar[0]
            hours = s.get("duration_hours", 0) or 0

            if hours < 1:
                duration_str = f"{int(hours * 60)} minute"
            elif hours < 24:
                duration_str = f"{int(hours)} ore"
            else:
                duration_str = f"{int(hours / 24)} zile"

            from bot.formatter import format_date_short

            date_str = format_date_short(s["completed_at"])

            reply_msg += f"\n\n💡 _Ai mai avut un task similar pe {date_str} — a durat {duration_str}\\._"

        return reply_msg, task_keyboard(task_id), task_id

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
            return msg, None, None

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
                meta: list[str] = []

                # Priority
                prio = t.get("priority", "medium")
                if prio == "high":
                    prefix = "⚠️ "
                    meta.append("🔥")
                elif prio == "low":
                    meta.append("🧊")

                # Due Date
                if t.get("due_date"):
                    from bot.formatter import format_date_short

                    date_str = format_date_short(t["due_date"])
                    if t["due_date"] < today:
                        prefix = "🔴 "
                        meta.append(f"*{escape_md(date_str)}*")
                    else:
                        meta.append(f"{escape_md(date_str)}")

                meta_str = f" \\({', '.join(meta)}\\)" if meta else ""
                lines.append(f"{prefix}• {escape_md(t['title'])}{meta_str}")

        from bot.keyboards import task_list_keyboard

        return (
            "\n".join(lines),
            task_list_keyboard(tasks, back_callback="tasks:main"),
            None,
        )

    elif intent == "complete_task":
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
                        f"Am găsit mai multe task-uri cu *{escape_md(title)}*. Pe care l-ai terminat?",
                        task_list_keyboard(matches, back_callback="tasks:main"),
                        None,
                    )

        if not task_id:
            return (
                "Ce task ai terminat? (Dă-mi un nume sau bifează-l din listă)",
                None,
                None,
            )

        await task_queries.complete_task(pool, task_id)

        # Immediate sync to Reminders
        try:
            from core.icloud import sync_tasks_to_reminders

            asyncio.create_task(sync_tasks_to_reminders(pool))
        except Exception as e:
            print(f"Error triggering task sync: {e}")

        task = await task_queries.get_task(pool, task_id)
        task_title = task["title"] if task else "Task necunoscut"

        if task and task.get("project_id"):
            decisions = await get_decisions(task["project_id"])
            if decisions:
                linked_decision = decisions[0]
                decision_text = linked_decision.get("title", "")[:50]
                context_msg = f"\n\n💡 Aliniat cu decizia Council: *{decision_text}*"
            else:
                context_msg = ""
        else:
            context_msg = ""

        feedback_msg = (
            f"✅ *{escape_md(task_title)}* completat\!{context_msg}\n\n"
            "Pe o scară de la 1 la 10, cât de greu a fost? "
            "(Răspunde cu un număr)"
        )
        return feedback_msg, None, task_id

    elif intent == "submit_task_feedback":
        difficulty = data.get("difficulty") or data.get("rating")
        task_id = data.get("task_id")
        task_title = data.get("task_title", "Completed task")
        context = data.get("context", "")

        if not difficulty:
            return "Ce dificultate? (1-10)", None, None

        try:
            difficulty = int(difficulty)
            difficulty = max(1, min(10, difficulty))
        except (ValueError, TypeError):
            return "Te rog un număr între 1-10.", None, None

        sent = await send_feedback_to_cto(difficulty, task_title, context)
        if sent:
            return (
                f"Feedback salvat! 📊 Difficultate: *{difficulty}/10*\nMulțumesc! 💙",
                None,
                None,
            )
        return "⚠️ Nu am putut trimite feedback la CTO.", None, None

    elif intent == "edit_task":
        task_id = data.get("id")
        # Try to find task by search term
        search_term = str(
            data.get("query")
            or data.get("search")
            or data.get("old_title")
            or data.get("name")
            or data.get("title")  # Gemini often puts the target task here
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
                        f"Am găsit mai multe task-uri cu *{escape_md(search_term)}*. Pe care vrei să-l editez?",
                        task_list_keyboard(matches, back_callback="tasks:main"),
                        None,
                    )

        if not task_id:
            return (
                "Ce task vrei să editez? (Dă-mi un nume sau bifează-l din listă)",
                None,
                None,
            )

        # Clean up data to only include valid update fields
        upd = {}
        # If we have a new title specifically, or if the user specified a new title in the message
        if data.get("new_title"):
            upd["title"] = data["new_title"]

        for k in ["notes", "priority", "due_date"]:
            if k in data and data[k] is not None:
                val = data[k]
                if k == "due_date" and isinstance(val, str):
                    try:
                        val = datetime.strptime(val, "%Y-%m-%d").date()
                    except Exception:
                        continue
                upd[k] = val

        # Handle project reassignment
        project_name = data.get("project") or data.get("project_name")
        if project_name:
            import db.queries.projects as project_queries

            project = await project_queries.get_project_by_name(pool, project_name)
            if project:
                upd["project_id"] = project["id"]
                # For the reply message
                data["project"] = project["name"]
            else:
                # Optional: Handle project not found?
                # For now just log it or ignore
                pass

        if not upd:
            return (
                "Ce anume vrei să schimb? (ex: 'Schimbă titlul în X' sau 'Pune prioritate mare')",
                None,
                None,
            )

        # Fetch old task state for comparison
        old_task = await task_queries.get_task(pool, task_id)
        
        await task_queries.update_task(pool, task_id, **upd)

        # Immediate sync to Reminders
        try:
            from core.icloud import sync_tasks_to_reminders

            asyncio.create_task(sync_tasks_to_reminders(pool))
        except Exception as e:
            print(f"Error triggering task sync: {e}")

        # Procrastination Check
        procrastination_msg = ""
        if "due_date" in upd and old_task:
            old_due = old_task.get("due_date")
            new_due = upd["due_date"]
            if new_due and (not old_due or new_due > old_due):
                # User is pushing the task further
                from db.queries.profile import get_user_profile
                from core.config import TELEGRAM_USER_ID
                target_uid = user_id or TELEGRAM_USER_ID
                profile = await get_user_profile(pool, target_uid)
                tone = profile.get("tone", "warm")
                if tone == "direct":
                    procrastination_msg = "\n\n🔥 *TAXĂ PE PROCRASTINARE\!* Amâni iar? Amânarea e eșec cu încetinitorul\. Sper că ai o scuză incredibilă, altfel ești doar leneș\."
                else:
                    procrastination_msg = "\n\n⚠️ Amânarea task-urilor importante poate duce la stres mai târziu. Ești sigur?"
        
        task = await task_queries.get_task(pool, task_id)
        from bot.keyboards import task_keyboard

        return (
            f"Actualizat ✅ *{escape_md(task['title'])}*{procrastination_msg}",
            task_keyboard(task_id),
            task_id,
        )

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
                        f"Am găsit mai multe task-uri cu *{escape_md(title)}*. Pe care vrei să-l șterg?",
                        task_list_keyboard(matches, back_callback="tasks:main"),
                        None,
                    )
            # if 0 matches, we'll fall through to "Which task..."

        if not task_id:
            return "Ce task vrei să șterg?", None, None

        task = await task_queries.get_task(pool, task_id)
        if not task:
            return "Nu am găsit task-ul.", None, None

        from core.state import set_state

        await set_state(pool, "awaiting_confirmation", "tasks", "delete", task_id)
        from bot.keyboards import confirmation_keyboard

        return (
            f"Sigur vrei să ștergi task-ul *{escape_md(task['title'])}*?",
            confirmation_keyboard("tasks", "delete", task_id),
            task_id,
        )

    return "Modulul de task-uri funcționează corect.", None, None


def _build_urgency_suggestion(tasks: list, today: date) -> str | None:
    """Build a contextual suggestion for the most urgent task."""
    if not tasks:
        return None

    overdue = [t for t in tasks if t.get("due_date") and t["due_date"] < today]
    due_today = [t for t in tasks if t.get("due_date") and t["due_date"] == today]
    due_tomorrow = [
        t
        for t in tasks
        if t.get("due_date")
        and t["due_date"] == today + timedelta(days=1)
        and t.get("priority") == "high"
    ]
    high_priority = [
        t for t in tasks if t.get("priority") == "high" and not t.get("due_date")
    ]

    if overdue:
        t = overdue[0]
        return f"🔴 *Task restant:* {escape_md(t['title'])}"
    if due_today:
        t = due_today[0]
        return f"⚠️ *Scadent azi:* {escape_md(t['title'])}"
    if due_tomorrow:
        t = due_tomorrow[0]
        return f"⚡ *Prioritate înaltă — mâine:* {escape_md(t['title'])}"
    if high_priority:
        t = high_priority[0]
        return f"📌 *Prioritate mare:* {escape_md(t['title'])}"

    return None


async def get_tasks_dashboard(pool) -> Tuple[str, Any]:
    """Returns a high-level overview of pending tasks grouped by project."""
    tasks = await task_queries.list_tasks(pool, status="pending")
    today = datetime.now().date()

    if not tasks:
        from bot.keyboards import tasks_main_keyboard

        return (
            r"Nu ai niciun task activ în acest moment\! 🎉\nPoți adăuga unul nou prin limbaj natural sau folosind butonul de mai jos\.",
            tasks_main_keyboard(),
        )

    # Simple count
    total = len(tasks)
    overdue = sum(1 for t in tasks if t.get("due_date") and t["due_date"] < today)

    # Grouping for the summary
    from collections import Counter

    projects = Counter(t.get("project_name") or "Fără proiect" for t in tasks)

    lines = ["📋 *Tasks Overview*\n"]

    suggestion = _build_urgency_suggestion(tasks, today)
    if suggestion:
        lines.append(f"{suggestion}\n")

    lines.append(rf"✅ *{total}* task\-uri active pe *{len(projects)}* proiecte\.")
    if overdue > 0:
        lines.append(rf"🔴 *{overdue}* sunt restante\!")

    # Decomposition Suggestion (Anti-Overwhelm/Procrastination)
    from datetime import datetime, timedelta
    now = datetime.now()
    stale_tasks = [t for t in tasks if t.get("priority") == "high" and t.get("created_at") and t["created_at"].replace(tzinfo=None) < now.replace(tzinfo=None) - timedelta(days=2)]
    if stale_tasks:
        t = stale_tasks[0]
        lines.append(f"\n💡 *DECOMPUNERE OBLIGATORIE:* Task-ul *{escape_md(t['title'])}* stă de 2 zile la prioritate mare. E clar că e prea greu. Sparge-l în 3 sub-task-uri acum!")

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
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    markup = task_list_keyboard(tasks, back_callback="tasks:projects_list")

    project_keyboard = [
        [
            InlineKeyboardButton(
                "✏️ Editează",
                callback_data=make_callback_data("projects", "edit", project_id),
            )
        ],
        [
            InlineKeyboardButton(
                "🗑️ Șterge",
                callback_data=make_callback_data("projects", "delete", project_id),
            )
        ],
        [
            InlineKeyboardButton(
                "◀️ Înapoi la proiecte",
                callback_data=make_callback_data("tasks", "projects", "list"),
            )
        ],
    ]
    combined_keyboard = list(markup.inline_keyboard) + project_keyboard
    return "\n".join(lines), InlineKeyboardMarkup(combined_keyboard)


async def _save_prompt_to_conversation(pool, prompt: str) -> None:
    """Saves the assistant's prompt to the history table for Gemini context."""
    from db.queries.history import save_message
    from core.config import TELEGRAM_USER_ID

    await save_message(pool, TELEGRAM_USER_ID, "assistant", prompt)


async def undo_last_action(pool, intent: str, item_id: int) -> Tuple[bool, str]:
    """Rolls back the last task action (add or complete)."""
    if not item_id:
        return False, "ID invalid."

    task = await task_queries.get_task(pool, item_id)
    if not task:
        return False, "Task-ul nu mai există."

    try:
        if intent == "add_task":
            # Physically delete or mark as deleted? Query has deleted_at.
            await task_queries.delete_task(pool, item_id)
            return True, f"task adăugat: '{task['title']}'"
        
        elif intent == "complete_task":
            # Restore to pending
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE tasks SET status = 'pending', completed_at = NULL, updated_at = NOW() WHERE id = $1",
                    item_id
                )
            return True, f"completarea task-ului: '{task['title']}'"
            
        return False, f"Intent-ul '{intent}' nu suportă undo."
    except Exception as e:
        return False, str(e)

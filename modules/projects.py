from typing import Dict, Any, Tuple, Optional
from datetime import date
import db.queries.projects as project_queries
from bot.formatter import escape_md


async def handle_project_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any, Optional[int]]:
    if intent == "add_project":
        name = data.get("name")
        if not name:
            from core.state import set_state

            await set_state(
                pool, "awaiting_project_name", "projects", "add_project", None
            )
            return "Cum vrei să se numească proiectul?", None

        deadline = None
        if data.get("deadline"):
            try:
                deadline = date.fromisoformat(data["deadline"])
            except (ValueError, TypeError):
                pass

        project_id = await project_queries.add_project(
            pool,
            name=name,
            description=data.get("description"),
            status=data.get("status", "active"),
            deadline=deadline,
            priority=data.get("priority", "medium"),
            category=data.get("category"),
        )

        meta_parts = []
        if deadline:
            meta_parts.append(f"📅 deadline: {data['deadline']}")
        if data.get("priority") == "high":
            meta_parts.append("🔥 prioritate mare")
        if data.get("category"):
            meta_parts.append(f"📁 {data['category']}")

        meta_str = f" ({', '.join(meta_parts)})" if meta_parts else ""
        return (
            f"✅ Proiectul *{escape_md(name)}* a fost adăugat cu succes.",
            None,
            project_id,
        )

    elif intent == "view_project":
        name = data.get("name")
        project = None

        if name:
            project = await project_queries.get_project_by_name(pool, name)
        elif data.get("id"):
            project = await project_queries.get_project(pool, data["id"])

        if not project:
            return (
                "⚠️ Atenție: Specifică un proiect pe care vrei să-l vizualizezi.",
                None,
            )

        detail = await project_queries.get_project_detail(pool, project["id"])
        if not detail:
            return (
                f"❌ Eroare: Nu am putut găsi proiectul *{escape_md(project['name'])}*.",
                None,
            )

        lines = [f"📂 *{escape_md(detail['name'])}*"]
        if detail.get("description"):
            lines.append(f"_{escape_md(detail['description'])}_")

        meta = []
        if detail.get("deadline"):
            meta.append(f"📅 {detail['deadline']}")
        if detail.get("priority"):
            priority_emoji = (
                "🔴"
                if detail["priority"] == "high"
                else "🟡"
                if detail["priority"] == "medium"
                else "🟢"
            )
            meta.append(f"{priority_emoji} {detail['priority']}")
        if detail.get("category"):
            meta.append(f"📁 {detail['category']}")
        if detail.get("progress_pct", 0) > 0:
            meta.append(f"📊 {detail['progress_pct']}%")

        if meta:
            lines.append(" | ".join(meta))

        # Escalation in Detail View
        if detail.get("deadline") and detail.get("status") == "active":
            today_val = date.today()
            days_left = (detail["deadline"] - today_val).days
            progress = detail.get("progress_pct", 0)

            import db.queries.profile as profile_queries
            from core.config import TELEGRAM_USER_ID

            profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
            tone = profile.get("tone", "warm")

            if days_left <= 3 and progress < 80 and tone == "direct":
                lines.append(
                    "\n🚨 *STATUS CRITIC:* Deadline-ul e peste 3 zile și ești la doar "
                    + str(progress)
                    + "%! Ești pe cale să eșuezi lamentabil. Începe să lucrezi ACUM!"
                )
            elif days_left <= 7 and progress < 50 and tone == "direct":
                lines.append(
                    "\n⚠️ *STATUS ALERTĂ:* Progres mult prea lent pentru deadline-ul de săptămâna viitoare. Mișcă-te!"
                )

        pending = detail.get("pending_count", 0)
        total = detail.get("task_count", 0)
        if total > 0:
            lines.append(f"\n📋 Tasks: *{pending}* pending / *{total}* total")

            for task in detail.get("tasks", [])[:5]:
                status_icon = "✅" if task["status"] == "done" else "⏳"
                due = f" (due: {task['due_date']})" if task.get("due_date") else ""
                lines.append(f"{status_icon} {escape_md(task['title'])}{due}")
            if len(detail["tasks"]) > 5:
                lines.append(f"... and *{len(detail['tasks']) - 5}* more")

        if detail.get("notes"):
            lines.append(f"\n📝 *{len(detail['notes'])}* linked notes")
            for note in detail["notes"][:2]:
                content = (
                    note["content"][:50] + "..."
                    if len(note["content"]) > 50
                    else note["content"]
                )
                lines.append(f"• {content}")

        return "\n".join(lines), None, None

    elif intent == "list_projects":
        status_filter = data.get("status")
        projects = await project_queries.get_projects_with_counts(pool)

        if status_filter:
            projects = [p for p in projects if p.get("status") == status_filter]

        if not projects:
            msg = (
                f"✅ Nu ai niciun proiect *{escape_md(status_filter)}*."
                if status_filter
                else "✅ Nu ai proiecte active."
            )
            return msg, None, None

        header = (
            "📂 *Toate Proiectele*\n━━━━━━━━━━━━━━━━━━━━"
            if not status_filter
            else f"📂 *Proiecte {status_filter.title()}*\n━━━━━━━━━━━━━━━━━━━━"
        )
        lines = [header]
        today_val = date.today()
        for p in projects:
            status_str = f" ({p['status']})" if p["status"] != "active" else ""
            pending = p.get("pending_tasks", 0)
            overdue = p.get("overdue_tasks", 0)
            progress = p.get("progress_pct", 0)
            deadline = p.get("deadline")

            # Escalation Logic
            escalation = ""
            if deadline and p["status"] == "active":
                days_left = (deadline - today_val).days
                if days_left <= 3 and progress < 80:
                    escalation = " 🚨 *URGENT/EȘEC IMINENT\!*"
                elif days_left <= 7 and progress < 50:
                    escalation = " ⚠️ *ÎN PERICOL\!*"

            task_info = f" 📋{pending}" if pending else ""
            if overdue > 0:
                task_info += f" ⚠️{overdue}"
            if progress > 0:
                task_info += f" 📊{progress}%"

            lines.append(
                f"• *{escape_md(p['name'])}*{status_str}{task_info}{escalation}"
            )
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines), None, None

    elif intent == "update_project":
        project_id = data.get("id")
        name = data.get("name")

        if not project_id and name:
            project = await project_queries.get_project_by_name(pool, name)
            if project:
                project_id = project["id"]

        if not project_id:
            return "⚠️ Atenție: Specifică un proiect pentru actualizare.", None

        update_data = {}
        if data.get("name"):
            update_data["name"] = data["name"]
        if data.get("description"):
            update_data["description"] = data["description"]
        if data.get("status"):
            update_data["status"] = data["status"]
        if data.get("priority"):
            update_data["priority"] = data["priority"]
        if data.get("category"):
            update_data["category"] = data["category"]
        if data.get("deadline"):
            try:
                update_data["deadline"] = date.fromisoformat(data["deadline"])
            except (ValueError, TypeError):
                pass

        if update_data:
            await project_queries.update_project(pool, project_id, **update_data)
            return (
                f"✏️ Proiectul *{escape_md(name or str(project_id))}* a fost actualizat.",
                None,
                project_id,
            )
        return "⚠️ Atenție: Nicio modificare specificată.", None, None

    elif intent == "update_progress":
        project_id = data.get("id")
        name = data.get("name")
        progress = data.get("progress_pct")

        if not project_id and name:
            project = await project_queries.get_project_by_name(pool, name)
            if project:
                project_id = project["id"]

        if not project_id:
            return "⚠️ Atenție: Specifică un proiect.", None, None

        if progress is not None:
            progress = max(0, min(100, int(progress)))
            await project_queries.update_project(
                pool, project_id, progress_pct=progress
            )
            return f"✏️ Progresul a fost actualizat la *{progress}%*.", None, project_id

        current = await project_queries.get_project(pool, project_id)
        if current:
            auto_progress = current.get("progress_pct", 0)
            return (
                f"Current progress: *{auto_progress}%* (auto\\-calculated from tasks)",
                None,
                None,
            )
        return "Project not found.", None, None

    elif intent == "archive_project":
        project_id = data.get("id")
        name = data.get("name")

        if not project_id and name:
            project = await project_queries.get_project_by_name(pool, name)
            if project:
                project_id = project["id"]

        if not project_id:
            return "Ce proiect vrei să arhivezi?", None

        project = await project_queries.get_project(pool, project_id)
        if not project:
            return "❌ Eroare: Nu am putut găsi proiectul.", None, None

        await project_queries.archive_project(pool, project_id)
        return (
            f"📦 Proiectul *{escape_md(project['name'])}* a fost arhivat.",
            None,
            project_id,
        )

    elif intent == "delete_project":
        project_id = data.get("id")
        project_name = data.get("name")

        if not project_id and project_name:
            project = await project_queries.get_project_by_name(pool, project_name)
            if project:
                project_id = project["id"]

        if not project_id:
            return "⚠️ Atenție: Specifică un proiect pe care vrei să-l ștergi.", None

        project = await project_queries.get_project(pool, project_id)
        if not project:
            return "❌ Eroare: Nu am putut găsi proiectul.", None, None

        from core.state import set_state

        await set_state(pool, "awaiting_confirmation", "projects", "delete", project_id)

        from bot.keyboards import confirmation_keyboard

        return (
            f"⚠️ Sigur vrei să ștergi proiectul *{escape_md(project['name'])}*?\nTask-urile asociate nu vor fi șterse.",
            confirmation_keyboard("projects", "delete", project_id),
            project_id,
        )

    elif intent == "delete_project_confirmed":
        project_id = data.get("id")
        if not project_id:
            return "❌ Eroare: Nu am putut găsi proiectul.", None, None

        project = await project_queries.get_project(pool, project_id)
        if project:
            await project_queries.delete_project(pool, project_id)
            return (
                f"🗑️ Proiectul *{escape_md(project['name'])}* a fost șters.",
                None,
                project_id,
            )
        return "❌ Eroare: Proiectul a fost deja șters sau nu există.", None, None

    return "Modulul de proiecte funcționează corect.", None, None


async def get_projects_dashboard(pool) -> Tuple[str, Any]:
    """Returns a high-level overview of projects and their activity."""
    projects = await project_queries.get_projects_with_counts(pool)

    total_active = len(projects)
    total_pending = sum(p.get("pending_tasks", 0) for p in projects)
    total_overdue = sum(p.get("overdue_tasks", 0) for p in projects)

    lines = ["🏗 *Dashboard Proiecte*\n"]
    lines.append(f"📊 Total proiecte active: *{total_active}*")
    lines.append(f"📋 Total task\\-uri active: *{total_pending}*")
    if total_overdue > 0:
        lines.append(f"⚠️ Task\\-uri overdue: *{total_overdue}*")

    priority_high = [p for p in projects if p.get("priority") == "high"]
    if priority_high:
        lines.append("\n🔥 *High Priority:*")
        for p in priority_high[:3]:
            pending = p.get("pending_tasks", 0)
            progress = p.get("progress_pct", 0)
            lines.append(f"• {escape_md(p['name'])}: {pending} tasks, {progress}%")

    deadline_soon = [p for p in projects if p.get("deadline")]
    if deadline_soon:
        lines.append("\n📅 *Cu deadline:*")
        for p in deadline_soon[:3]:
            lines.append(f"• {escape_md(p['name'])}: {p['deadline']}")

    from bot.keyboards import projects_main_keyboard

    return "\n".join(lines), projects_main_keyboard(projects)

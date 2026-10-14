"""One-way, local Markdown export from Lora to an Obsidian vault.

The exporter is deliberately independent of Obsidian internals: a vault is
just a directory of Markdown files. Existing note bodies are preserved and
only the generated frontmatter is refreshed, so manual additions survive a
later sync.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv

logger = logging.getLogger("lora.obsidian")

load_dotenv()

VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", str(Path.cwd() / "obsidian"))).expanduser().resolve()
SYNC_ENABLED = os.getenv("OBSIDIAN_SYNC_ENABLED", "true").lower() == "true"
INCLUDE_FINANCE = os.getenv("OBSIDIAN_SYNC_INCLUDE_FINANCE", "true").lower() == "true"
INCLUDE_PERSONAL_NOTES = os.getenv("OBSIDIAN_SYNC_INCLUDE_PERSONAL_NOTES", "true").lower() == "true"

FOLDERS = (
    "00 Dashboard", "01 Daily", "02 Tasks", "03 Projects", "04 Finance",
    "05 University/Subjects", "05 University/_Data/Exams", "05 University/_Data/Grades",
    "05 University/_Data/Attendance", "06 Calendar", "07 Notes", "08 Goals",
    "08 Memory", "Templates", "Attachments",
)


def _safe_filename(value: Any, fallback: str) -> str:
    text = re.sub(r"[^\w\-. ]+", "", str(value or fallback), flags=re.UNICODE).strip()
    return (text or fallback).replace("/", "-")[:120]


def _scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).replace("\n", " ").strip()


def _frontmatter(fields: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            rendered = '""'
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            rendered = str(value)
        elif isinstance(value, (datetime, date)):
            rendered = value.isoformat()
        else:
            scalar = _scalar(value).replace('"', '\\"')
            rendered = f'"{scalar}"'
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    return "\n".join(lines)


def _body(existing: str, generated: str) -> str:
    """Keep manual content while refreshing the generated section."""
    marker = "<!-- LORA:CONTENT -->"
    end_marker = "<!-- LORA:END -->"
    if marker in existing:
        tail = existing.split(marker, 1)[1]
        manual = tail.split(end_marker, 1)[1] if end_marker in tail else ""
        return f"{marker}\n{generated.rstrip()}\n{end_marker}\n{manual.lstrip()}"
    return f"{marker}\n{generated.rstrip()}\n{end_marker}\n"


def _write_note(relative: str, fields: dict[str, Any], generated: str) -> bool:
    path = (VAULT_PATH / relative).resolve()
    if VAULT_PATH not in path.parents:
        raise ValueError("Obsidian path escaped the configured vault")
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    content = f"{_frontmatter(fields)}\n\n{_body(existing, generated)}"
    if existing == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def _iso(value: Any) -> str:
    return _scalar(value) or ""


def _subject_folder(name: Any, identifier: Any) -> str:
    return f"05 University/Subjects/{_safe_filename(name, 'Subject')}"


def _subject_meta_path(name: Any, identifier: Any) -> str:
    safe = _safe_filename(name, 'Subject')
    return f"05 University/Subjects/{safe}/{safe}.md"


async def _rows(pool, query: str) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        return [dict(row) for row in await conn.fetch(query)]


async def sync_vault(pool) -> dict[str, int]:
    """Export supported Lora entities and return created/updated counts."""
    if not SYNC_ENABLED:
        return {"written": 0, "skipped": 0}
    VAULT_PATH.mkdir(parents=True, exist_ok=True)
    for folder in FOLDERS:
        (VAULT_PATH / folder).mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0

    async def export(rows: Iterable[dict[str, Any]], folder: str, kind: str, title_key: str, body_keys: tuple[str, ...]) -> None:
        nonlocal written, skipped
        for row in rows:
            identifier = row.get("id")
            title = row.get(title_key) or f"{kind}-{identifier}"
            filename = f"{_safe_filename(title, kind)} [{identifier}].md"
            fields = {"cssclasses": "lora-entity", "type": kind, "lora_id": identifier, "source": "lora", "updated_at": row.get("updated_at")}
            fields.update({key: row.get(key) for key in body_keys if key in row})
            if kind == "task":
                fields["project_id"] = row.get("project_id")
                fields["university_subject_id"] = row.get("university_subject_id")
            body = f"# {title}\n\n"
            for key in body_keys:
                if row.get(key) is not None:
                    body += f"**{key.replace('_', ' ').title()}:** {_iso(row[key])}\n\n"
            links: list[str] = []
            if row.get("project_id") and row.get("project_name"):
                links.append(f"[[03 Projects/{_safe_filename(row['project_name'], 'Project')} [{row['project_id']}]]]")
            if row.get("university_subject_id") and row.get("university_subject_name"):
                links.append(f"[[{_subject_meta_path(row['university_subject_name'], row['university_subject_id'])[:-3]}]]")
            if row.get("subject_id") and row.get("subject_name") and kind != "university_subject":
                links.append(f"[[{_subject_meta_path(row['subject_name'], row['subject_id'])[:-3]}]]")
            if links:
                body += "## Relații\n\n" + " · ".join(links) + "\n"
            if kind == "project":
                body += (
                    "## Taskuri asociate\n\n"
                    "```dataview\n"
                    "TABLE status AS \"Status\", priority AS \"Prioritate\", due_date AS \"Deadline\", description AS \"Descriere\"\n"
                    "FROM \"02 Tasks\"\n"
                    "WHERE project_id = this.lora_id\n"
                    "SORT status ASC, due_date ASC, priority DESC\n"
                    "```\n"
                )
            if _write_note(f"{folder}/{filename}", fields, body):
                written += 1
            else:
                skipped += 1

    tasks = await _rows(pool, """
        SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date,
               t.project_id, t.university_subject_id,
               p.name AS project_name, s.name AS university_subject_name,
               t.updated_at
        FROM tasks t
        LEFT JOIN projects p ON p.id = t.project_id
        LEFT JOIN subjects s ON s.id = t.university_subject_id
        WHERE t.deleted_at IS NULL
    """)
    await export(tasks, "02 Tasks/_Active", "task", "title", ("description", "status", "priority", "due_date"))
    projects = await _rows(pool, """
        SELECT p.id, p.name, p.description, p.status, p.priority, p.deadline,
               p.university_subject_id, s.name AS university_subject_name,
               p.updated_at
        FROM projects p
        LEFT JOIN subjects s ON s.id = p.university_subject_id
        WHERE p.deleted_at IS NULL
    """)
    await export(projects, "03 Projects", "project", "name", ("description", "status", "priority", "deadline"))
    goals = await _rows(pool, "SELECT id, title, description, status, progress, category, time_horizon, updated_at FROM goals")
    await export(goals, "08 Goals", "goal", "title", ("description", "status", "progress", "category", "time_horizon"))
    subjects = await _rows(pool, "SELECT id, name, professor, credits, created_at AS updated_at FROM subjects WHERE is_active = TRUE")
    for row in subjects:
        subject_folder = _subject_folder(row.get("name"), row.get("id"))
        for child in ("Cursuri", "Seminarii", "Exams", "Projects"):
            child_path = VAULT_PATH / subject_folder / child
            child_path.mkdir(parents=True, exist_ok=True)
            if child in {"Cursuri", "Seminarii"}:
                subfolders = ("Notițe", "Idei", "Calcule", "Resources", "Lora/Summaries")
            else:
                subfolders = ()
            for subfolder in subfolders:
                subfolder_path = child_path / subfolder
                subfolder_path.mkdir(parents=True, exist_ok=True)
                sub_readme = subfolder_path / "README.md"
                if not sub_readme.exists():
                    sub_readme.write_text(
                        f"# {subfolder}\n\nFolder pentru materia **{row.get('name') or 'Subject'}**.\n",
                        encoding="utf-8",
                    )
            readme = child_path / "README.md"
            if not readme.exists():
                readme.write_text(
                    f"# {child}\n\nMateria: **{row.get('name') or 'Subject'}**\n\n"
                    "- `Notițe`: ce scrii în timpul cursului sau seminarului.\n"
                    "- `Idei`: rezumatul și explicațiile tale de acasă.\n"
                    "- `Calcule`: probleme, formule și rezolvări.\n"
                    "- `Resources`: PDF-uri, PowerPoint-uri, documente Word și alte materiale primite.\n"
                    "- `Lora/Summaries`: rezumate generate local de Lora, organizate după material.\n",
                    encoding="utf-8",
                )
        for filename in ("Questions.md", "Resources.md"):
            (VAULT_PATH / subject_folder / filename).touch(exist_ok=True)
        fields = {
            "cssclasses": "lora-entity", "type": "university_subject", "lora_id": row.get("id"),
            "name": row.get("name"),
            "source": "lora", "updated_at": row.get("updated_at"), "professor": row.get("professor"),
            "credits": row.get("credits"),
        }
        body = f"# {row.get('name') or 'Subject'}\n\n**Professor:** {_iso(row.get('professor'))}\n\n**Credits:** {_iso(row.get('credits'))}\n\n## Workspace\n\n- [[Cursuri/Notițe]] · [[Cursuri/Idei]] · [[Cursuri/Calcule]] · [[Cursuri/Resources]] · [[Cursuri/Lora/Summaries]]\n- [[Seminarii/Notițe]] · [[Seminarii/Idei]] · [[Seminarii/Calcule]] · [[Seminarii/Resources]] · [[Seminarii/Lora/Summaries]]\n- [[Exams]]\n- [[Projects]]\n- [[Questions]]\n- [[Resources]]\n"
        if _write_note(_subject_meta_path(row.get("name"), row.get("id")), fields, body):
            written += 1
        else:
            skipped += 1
    exams = await _rows(pool, "SELECT id, subject_id, subject_name, exam_date, exam_type, room, notes, created_at AS updated_at FROM exams ORDER BY exam_date")
    await export(exams, "05 University/_Data/Exams", "exam", "subject_name", ("exam_date", "exam_type", "room", "notes"))
    grades = await _rows(pool, """SELECT g.id, g.subject_id, s.name AS subject_name, g.grade, g.grade_type, g.class_type,
        g.notes, g.graded_at AS updated_at
        FROM grades g LEFT JOIN subjects s ON s.id = g.subject_id
        ORDER BY g.graded_at DESC""")
    await export(grades, "05 University/_Data/Grades", "grade", "grade", ("subject_id", "subject_name", "grade_type", "class_type", "notes"))
    attendance = await _rows(pool, """SELECT a.id, a.subject_id, a.schedule_id, a.class_date, a.attended, a.notes,
        COALESCE(s.class_type, 'seminar') AS class_type, s.subject_name,
        a.created_at AS updated_at
        FROM attendances a LEFT JOIN schedule s ON s.id = a.schedule_id
        ORDER BY a.class_date DESC""")
    await export(attendance, "05 University/_Data/Attendance", "attendance", "class_date", ("subject_id", "schedule_id", "attended", "class_type", "subject_name", "notes"))
    schedule = await _rows(pool, "SELECT id, subject_name, day_of_week, start_time, end_time, room, class_type, week_type, created_at AS updated_at FROM schedule WHERE is_active = TRUE ORDER BY day_of_week, start_time")
    await export(schedule, "06 Calendar/_Schedule", "schedule", "subject_name", ("day_of_week", "start_time", "end_time", "room", "class_type", "week_type"))
    academic_periods = await _rows(pool, """
        SELECT id, academic_year, semester, period_type, start_date, end_date,
               description, created_at AS updated_at
        FROM academic_periods
        ORDER BY start_date, period_type, id
    """)
    await export(
        academic_periods,
        "06 Calendar/_Academic Periods",
        "academic_period",
        "description",
        ("academic_year", "semester", "period_type", "start_date", "end_date", "description"),
    )
    events = await _rows(pool, "SELECT id, title, description, event_date, event_time, event_type, created_at AS updated_at FROM events ORDER BY event_date, event_time NULLS LAST")
    await export(events, "06 Calendar/_Events", "event", "title", ("description", "event_date", "event_time", "event_type"))

    if INCLUDE_FINANCE:
        finances = await _rows(pool, "SELECT id, description, amount, currency, category, type, tx_date, updated_at FROM finances ORDER BY tx_date DESC")
        for row in finances:
            kind = "expense" if row.get("type") == "expense" else "income"
            await export([row], "04 Finance/_Transactions", kind, "description", ("description", "amount", "currency", "category", "type", "tx_date"))
    if INCLUDE_PERSONAL_NOTES:
        notes = await _rows(pool, """
            SELECT n.id, n.content, n.type, n.project_id,
                   p.name AS project_name, n.created_at, n.updated_at
            FROM notes n
            LEFT JOIN projects p ON p.id = n.project_id
        """)
        await export(notes, "07 Notes", "note", "content", ("type", "created_at"))
        memories = await _rows(pool, "SELECT id, category, fact, source, confidence, created_at AS updated_at FROM memory_facts ORDER BY created_at DESC")
        await export(memories, "08 Memory", "memory", "fact", ("category", "source", "confidence"))

    await _write_dashboards()
    logger.info("Obsidian sync complete: written=%d skipped=%d", written, skipped)
    return {"written": written, "skipped": skipped}


async def _write_dashboards() -> None:
    dashboards = {
        "Home.md": "# Lora\n\n## Astăzi\n```dataview\nLIST FROM \"02 Tasks\" WHERE status = \"pending\" AND due_date = date(today)\nSORT priority DESC\n```\n\n## Taskuri active\n```dataview\nTABLE priority, due_date\nFROM \"02 Tasks\"\nWHERE status = \"pending\"\nSORT due_date ASC, priority DESC\n```\n\n## Proiecte active\n```dataview\nTABLE status, priority, deadline\nFROM \"03 Projects\"\nWHERE status = \"active\"\nSORT deadline ASC\n```\n",
        "Today.md": "# Astăzi\n\n## Taskuri\n```tasks\nnot done\ndue today\npath includes 02 Tasks\n```\n\n## Note zilnică\n[[../01 Daily/" + date.today().isoformat() + "]]\n",
        "Finance.md": "# Finanțe\n\n```dataview\nTABLE amount, category, tx_date\nFROM \"04 Finance\"\nWHERE type = \"expense\"\nSORT tx_date DESC\nLIMIT 30\n```\n",
        "University.md": "# University\n\n## Materii\n```dataview\nTABLE professor, credits, semester\nFROM \"05 University/Subjects\"\nSORT name ASC\n```\n\n## Examene și note\nAdaugă aici view-urile Bases/Dataview pentru examene și note.\n",
        "Projects.md": "# Proiecte\n\n```dataview\nTABLE status, priority, deadline\nFROM \"03 Projects\"\nSORT deadline ASC\n```\n",
    }
    for name, content in dashboards.items():
        path = VAULT_PATH / "00 Dashboard" / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")


async def sync_vault_safe(pool) -> dict[str, int]:
    try:
        return await sync_vault(pool)
    except Exception:
        logger.exception("Obsidian sync failed")
        return {"written": 0, "skipped": 0}


def run_sync(pool) -> dict[str, int]:
    return asyncio.run(sync_vault_safe(pool))


if __name__ == "__main__":
    async def _main() -> None:
        from db.connection import close_pool, get_pool

        pool = await get_pool()
        try:
            print(await sync_vault_safe(pool))
        finally:
            await close_pool()

    asyncio.run(_main())

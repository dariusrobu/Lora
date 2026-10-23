"""Small read-only answers for frequent Telegram questions."""

import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg

from lora_v2.config import Settings
from lora_v2.finance_balance import read_balance


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in value if unicodedata.category(char) != "Mn")


def read_intent(text: str) -> str | None:
    """Only intercept clear questions; possible writes continue to the capture pipeline."""
    cleaned = re.sub(r"\s+", " ", _plain(text).strip(" ?.!,"))
    if cleaned in {"azi", "ce am azi", "ce fac azi", "cum arata ziua de azi", "programul de azi"}:
        return "today"
    if cleaned in {"maine", "ce am maine", "ce fac maine", "programul de maine"}:
        return "tomorrow"
    if cleaned in {"taskuri", "ce taskuri am", "ce am de facut", "ce trebuie sa fac", "lista de taskuri"}:
        return "tasks"
    if cleaned in {"cheltuieli", "cat am cheltuit luna asta", "ce am cheltuit luna asta"}:
        return "expenses"
    if cleaned in {"sold", "ce sold am", "cat mai am", "cati bani mai am", "ce sold am acum"}:
        return "balance"
    if cleaned in {"facultate", "ce am la facultate azi", "orarul de azi", "ce cursuri am azi"}:
        return "university"
    if cleaned in {"calendar", "ce am saptamana asta", "programul saptamanii"}:
        return "calendar"
    if cleaned in {"remindere", "ce remindere am", "ce trebuie sa imi amintesc"}:
        return "reminders"
    if cleaned in {"noutati", "noutati facultate", "anunturi facultate"}:
        return "news"
    if cleaned in {"bani", "situatia banilor", "situatia financiara"}:
        return "money"
    if cleaned in {"antrenament", "antrenamente", "ce antrenamente am facut"}:
        return "workout"
    return None


async def answer_read_intent(
    pool: asyncpg.Pool, settings: Settings, owner_id: int, intent: str,
    now: datetime | None = None,
) -> str:
    local_now = now or datetime.now(ZoneInfo(settings.timezone))
    local_now = local_now.astimezone(ZoneInfo(settings.timezone))
    if intent == "balance":
        balance = await read_balance(pool, owner_id)
        if balance["balance"] is None:
            return "Nu știu încă soldul actual. Setează suma pe care o ai acum în Mini App → Jurnal → Sold."
        return (f"Sold estimat: {balance['balance']:.2f} RON. "
                "Pornește de la suma introdusă de tine și tranzacțiile salvate după aceea.")
    balance = await read_balance(pool, owner_id) if intent in {"expenses", "money"} else None
    day = local_now.date() + timedelta(days=1 if intent == "tomorrow" else 0)
    start = datetime.combine(day, datetime.min.time(), ZoneInfo(settings.timezone))
    end = start + timedelta(days=1)
    async with pool.acquire() as conn:
        if intent == "calendar":
            rows = await conn.fetch(
                """SELECT kind,title,starts_at FROM calendar_entries
                WHERE owner_id=$1 AND status='active' AND starts_at >= $2 AND starts_at < $3
                ORDER BY starts_at LIMIT 30""",
                owner_id, start, start + timedelta(days=7),
            )
            if not rows:
                return "Nu ai evenimente, remindere sau cursuri în următoarele 7 zile."
            labels = {"event": "Eveniment", "reminder": "Reminder", "academic": "Facultate"}
            lines = ["Calendar · următoarele 7 zile:"]
            current_day = None
            for row in rows:
                at = row["starts_at"].astimezone(ZoneInfo(settings.timezone))
                if at.date() != current_day:
                    current_day = at.date()
                    lines.append(f"{at:%a %d.%m}:")
                lines.append(f"• {at:%H:%M} · {labels.get(row['kind'], row['kind'])}: {row['title']}")
            return "\n".join(lines)
        if intent == "reminders":
            overdue = await conn.fetch(
                """SELECT title,starts_at FROM calendar_entries
                WHERE owner_id=$1 AND kind='reminder' AND status='active' AND starts_at < $2
                ORDER BY starts_at DESC LIMIT 5""", owner_id, local_now,
            )
            upcoming = await conn.fetch(
                """SELECT title,starts_at FROM calendar_entries
                WHERE owner_id=$1 AND kind='reminder' AND status='active' AND starts_at >= $2
                ORDER BY starts_at LIMIT 10""", owner_id, local_now,
            )
            if not overdue and not upcoming:
                return "Nu ai remindere deschise."
            lines = ["Remindere:"]
            for label, rows in (("De verificat", overdue), ("Urmează", upcoming)):
                if rows:
                    lines.append(label + ":")
                    lines.extend(
                        f"• {row['starts_at'].astimezone(ZoneInfo(settings.timezone)):%d.%m %H:%M} · {row['title']}"
                        for row in rows
                    )
            return "\n".join(lines)
        if intent == "news":
            rows = await conn.fetch(
                """SELECT course_title,kind,title,updated_at FROM moodle_posts
                WHERE owner_id=$1 AND archived_at IS NULL AND filtered_out=false AND is_read=false
                ORDER BY updated_at DESC LIMIT 8""", owner_id,
            )
            if not rows:
                return "Nu ai anunțuri sau mesaje noi de pe forum."
            lines = ["Noutăți necitite de la facultate:"]
            lines.extend(
                f"• {row['course_title']} · {'Anunț' if row['kind'] == 'announcement' else 'Forum'}: {row['title']}"
                for row in rows
            )
            return "\n".join(lines)
        if intent == "workout":
            week_start = start - timedelta(days=start.weekday())
            last = await conn.fetchrow(
                """SELECT activity,started_at,duration_minutes FROM workouts
                WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY started_at DESC LIMIT 1""", owner_id,
            )
            count = await conn.fetchval(
                """SELECT count(*) FROM workouts WHERE owner_id=$1 AND deleted_at IS NULL
                AND started_at >= $2 AND started_at < $3""", owner_id, week_start, local_now,
            )
            if not last:
                return "Nu ai antrenamente înregistrate încă."
            at = last["started_at"].astimezone(ZoneInfo(settings.timezone))
            duration = f" · {last['duration_minutes']} min" if last["duration_minutes"] else ""
            return (f"Antrenamente săptămâna aceasta: {count}.\n"
                    f"Ultimul: {at:%d.%m %H:%M} · {last['activity']}{duration}.")
        if intent == "money":
            month_start = start.replace(day=1)
            totals = await conn.fetch(
                """SELECT currency,SUM(amount) AS amount FROM expenses
                WHERE owner_id=$1 AND deleted_at IS NULL AND spent_at >= $2 AND spent_at < $3
                GROUP BY currency ORDER BY currency""", owner_id, month_start, local_now,
            )
            recent = await conn.fetch(
                """SELECT amount,currency,category,merchant,spent_at FROM expenses
                WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY spent_at DESC LIMIT 3""", owner_id,
            )
            lines = ["Bani:"]
            lines.append(f"Sold estimat: {balance['balance']:.2f} RON." if balance and balance["balance"] is not None
                         else "Sold estimat: încă nesetat.")
            lines.append("Cheltuieli luna aceasta: " + (
                ", ".join(f"{row['amount']} {row['currency']}" for row in totals) if totals else "niciuna"))
            if recent:
                lines.append("Ultimele cheltuieli:")
                lines.extend(
                    f"• {row['amount']} {row['currency']} · {row['merchant'] or row['category']}"
                    for row in recent
                )
            return "\n".join(lines)
        if intent in {"today", "tomorrow", "university"}:
            entries = await conn.fetch(
                """SELECT kind,title,starts_at FROM calendar_entries
                WHERE owner_id=$1 AND status='active' AND starts_at >= $2 AND starts_at < $3
                AND ($4::boolean=false OR kind='academic') ORDER BY starts_at LIMIT 30""",
                owner_id, start, end, intent == "university",
            )
            if intent == "university":
                unread = await conn.fetchval(
                    """SELECT count(*) FROM moodle_posts WHERE owner_id=$1 AND archived_at IS NULL
                    AND filtered_out=false AND is_read=false""", owner_id,
                )
                lines = ["Facultate azi:"] + [
                    f"• {row['starts_at'].astimezone(ZoneInfo(settings.timezone)):%H:%M} {row['title']}"
                    for row in entries
                ]
                if not entries:
                    lines.append("• Nu ai cursuri sau seminare în calendar.")
                if unread:
                    lines.append(f"Noutăți necitite: {unread}.")
                return "\n".join(lines)
            tasks = await conn.fetch(
                """SELECT t.title,t.due_at,p.name AS project_name FROM tasks t
                LEFT JOIN projects p ON p.id=t.project_id
                WHERE t.owner_id=$1 AND t.status='pending' AND (t.due_at < $2 OR t.due_at IS NULL)
                ORDER BY t.due_at NULLS LAST,t.created_at LIMIT 20""",
                owner_id, end,
            )
            label = "Mâine" if intent == "tomorrow" else "Azi"
            lines = [f"{label}, {day:%d.%m}:"]
            if entries:
                labels = {"event": "Eveniment", "reminder": "Reminder", "academic": "Facultate"}
                lines.extend(
                    f"• {row['starts_at'].astimezone(ZoneInfo(settings.timezone)):%H:%M} "
                    f"{labels.get(row['kind'], row['kind'])}: {row['title']}"
                    for row in entries
                )
            else:
                lines.append("• Nimic în calendar.")
            if tasks:
                lines.append("Taskuri deschise:")
                for row in tasks:
                    project = f" · {row['project_name']}" if row["project_name"] else ""
                    lines.append(f"• {row['title']}{project}")
            return "\n".join(lines)
        if intent == "tasks":
            rows = await conn.fetch(
                """SELECT t.title,t.due_at,p.name AS project_name FROM tasks t
                LEFT JOIN projects p ON p.id=t.project_id
                WHERE t.owner_id=$1 AND t.status='pending'
                ORDER BY p.name NULLS FIRST,t.due_at NULLS LAST,t.created_at LIMIT 30""",
                owner_id,
            )
            if not rows:
                return "Nu ai taskuri deschise."
            lines = ["Taskuri pe proiecte:"]
            current_project = None
            for row in rows:
                project = row["project_name"] or "Fără proiect"
                if project != current_project:
                    lines.append(project + ":")
                    current_project = project
                due = row["due_at"]
                when = f" · {due.astimezone(ZoneInfo(settings.timezone)):%d.%m %H:%M}" if due else ""
                lines.append(f"• {row['title']}{when}")
            return "\n".join(lines)
        if intent == "expenses":
            month_start = start.replace(day=1)
            rows = await conn.fetch(
                """SELECT category,SUM(amount) AS amount,currency FROM expenses
                WHERE owner_id=$1 AND deleted_at IS NULL AND spent_at >= $2 AND spent_at < $3
                GROUP BY category,currency ORDER BY amount DESC""",
                owner_id, month_start, local_now,
            )
            balance_line = (f"Sold estimat: {balance['balance']:.2f} RON.\n"
                            if balance and balance["balance"] is not None else "")
            if not rows:
                return balance_line + "Nu ai cheltuieli înregistrate luna aceasta."
            return balance_line + "Cheltuieli luna aceasta:\n" + "\n".join(
                f"• {row['category']}: {row['amount']} {row['currency']}" for row in rows
            )
    raise ValueError(f"Unknown read intent: {intent}")

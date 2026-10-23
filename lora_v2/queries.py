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
    balance = await read_balance(pool, owner_id) if intent == "expenses" else None
    day = local_now.date() + timedelta(days=1 if intent == "tomorrow" else 0)
    start = datetime.combine(day, datetime.min.time(), ZoneInfo(settings.timezone))
    end = start + timedelta(days=1)
    async with pool.acquire() as conn:
        if intent in {"today", "tomorrow", "university"}:
            entries = await conn.fetch(
                """SELECT kind,title,starts_at FROM calendar_entries
                WHERE owner_id=$1 AND status='active' AND starts_at >= $2 AND starts_at < $3
                AND ($4::boolean=false OR kind='academic') ORDER BY starts_at LIMIT 30""",
                owner_id, start, end, intent == "university",
            )
            if intent == "university":
                if not entries:
                    return "Nu am cursuri sau seminare în calendar pentru azi."
                return "Facultate azi:\n" + "\n".join(
                    f"• {row['starts_at'].astimezone(ZoneInfo(settings.timezone)):%H:%M} {row['title']}"
                    for row in entries
                )
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
                lines.extend(
                    f"• {row['starts_at'].astimezone(ZoneInfo(settings.timezone)):%H:%M} {row['title']}"
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
                ORDER BY t.due_at NULLS LAST,t.created_at LIMIT 20""",
                owner_id,
            )
            if not rows:
                return "Nu ai taskuri deschise."
            lines = ["Taskuri deschise:"]
            for row in rows:
                due = row["due_at"]
                when = f" · {due.astimezone(ZoneInfo(settings.timezone)):%d.%m %H:%M}" if due else ""
                project = f" · {row['project_name']}" if row["project_name"] else ""
                lines.append(f"• {row['title']}{project}{when}")
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

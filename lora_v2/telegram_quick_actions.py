"""Owner-scoped item pickers behind the eight Telegram daily-driver commands."""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from lora_v2.academic_calendar import ACADEMIC_NAMESPACE
from lora_v2.config import Settings
from lora_v2.telegram_navigation import READ_INTENTS


_ADD_PROMPTS = {
    "today": ("Adaugă", "Scrie-mi ce vrei să notez pentru azi, cu ora dacă trebuie să te anunț."),
    "tomorrow": ("Adaugă", "Scrie-mi ce vrei să notez pentru mâine, cu ora dacă trebuie să te anunț."),
    "calendar": ("Eveniment nou", "Scrie evenimentul, data și ora. De exemplu: duminică la 20 am fotbal, amintește-mi la 19:30."),
    "tasks": ("Task nou", "Scrie ce ai de făcut și, dacă vrei, proiectul și termenul."),
    "reminders": ("Reminder nou", "Scrie-mi exact ce să-ți amintesc și când. De exemplu: amintește-mi mâine la 13:30 să iau geanta."),
    "university": ("Notează pentru facultate", "Scrie materia și ce vrei să notez: task, examen, notă sau prezență."),
    "news": ("Întreabă despre noutăți", "Spune-mi ce anunț sau materie cauți; poți deschide și noutatea din listă."),
    "money": ("Cheltuială nouă", "Scrie suma, locul și ce ai cumpărat. Dacă nu este clară categoria, te întreb înainte de salvare."),
    "income": ("Venit nou", "Scrie suma, sursa și data venitului. De exemplu: azi am primit 200 lei de la client."),
    "balance": ("Cheltuială nouă", "Scrie suma, locul și ce ai cumpărat."),
    "expenses": ("Cheltuială nouă", "Scrie suma, locul și ce ai cumpărat."),
    "workout": ("Antrenament nou", "Scrie ce ai antrenat, durata și exercițiile dacă le știi. Exemplu: azi am făcut piept 45 min."),
}


def add_prompt(intent: str) -> str | None:
    item = _ADD_PROMPTS.get(intent)
    return item[1] if item else None


async def action_menu(
    pool: asyncpg.Pool, settings: Settings, owner_id: int, intent: str, page: int = 0,
) -> tuple[str, InlineKeyboardMarkup]:
    if (intent not in READ_INTENTS or page < 0 or page > 20
            or (intent in {"today", "tomorrow"} and page != 0)):
        raise ValueError("Unknown action menu")
    now = datetime.now(ZoneInfo(settings.timezone))
    end = now + timedelta(days=7)
    rows: list[asyncpg.Record] = []
    offset = page * 8
    async with pool.acquire() as conn:
        if intent in {"today", "tomorrow"}:
            day = now.date() + timedelta(days=int(intent == "tomorrow"))
            day_start = datetime.combine(day, datetime.min.time(), ZoneInfo(settings.timezone))
            day_end = day_start + timedelta(days=1)
            tasks = await conn.fetch(
                """SELECT id,title,version,'t' AS item_kind FROM tasks
                WHERE owner_id=$1 AND status='pending' AND (due_at < $2 OR due_at IS NULL)
                ORDER BY due_at NULLS LAST,created_at LIMIT 4""", owner_id, day_end,
            )
            entries = await conn.fetch(
                """SELECT id,title,version,'e' AS item_kind FROM calendar_entries
                WHERE owner_id=$1 AND status='active' AND kind IN ('event','reminder')
                AND starts_at >= $2 AND starts_at < $3 ORDER BY starts_at LIMIT 4""",
                owner_id, day_start, day_end,
            )
            rows = [*entries, *tasks]
        elif intent == "tasks":
            rows = await conn.fetch(
                """SELECT id,title,version,'t' AS item_kind FROM tasks
                WHERE owner_id=$1 AND status='pending'
                ORDER BY due_at NULLS LAST,created_at LIMIT 9 OFFSET $2""", owner_id, offset,
            )
        elif intent == "reminders":
            rows = await conn.fetch(
                """SELECT id,title,version,'e' AS item_kind FROM calendar_entries
                WHERE owner_id=$1 AND status='active' AND kind='reminder'
                ORDER BY starts_at LIMIT 9 OFFSET $2""", owner_id, offset,
            )
        elif intent in {"calendar", "university"}:
            range_start = (datetime.combine(now.date(), datetime.min.time(), ZoneInfo(settings.timezone))
                           if intent == "university" else now)
            rows = await conn.fetch(
                """SELECT id,title,version,'e' AS item_kind FROM calendar_entries
                WHERE owner_id=$1 AND status='active' AND starts_at >= $2 AND starts_at < $3
                AND ($4::boolean=false OR kind='academic')
                ORDER BY starts_at LIMIT 9 OFFSET $5""", owner_id, range_start, end,
                intent == "university", offset,
            )
        elif intent == "news":
            rows = await conn.fetch(
                """SELECT id,title,1 AS version,'n' AS item_kind FROM moodle_posts
                WHERE owner_id=$1 AND archived_at IS NULL AND filtered_out=false AND is_read=false
                ORDER BY updated_at DESC LIMIT 9 OFFSET $2""", owner_id, offset,
            )
        elif intent in {"money", "balance", "expenses"}:
            rows = await conn.fetch(
                """SELECT id,COALESCE(description,merchant,category,'Cheltuială') AS title,
                version,'x' AS item_kind FROM expenses
                WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY spent_at DESC LIMIT 9 OFFSET $2""",
                owner_id, offset,
            )
        elif intent == "workout":
            rows = await conn.fetch(
                """SELECT id,activity AS title,version,'w' AS item_kind FROM workouts
                WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY started_at DESC LIMIT 9 OFFSET $2""",
                owner_id, offset,
            )
    has_more = len(rows) > 8
    buttons: list[list[InlineKeyboardButton]] = []
    for row in rows[:8]:
        title = str(row["title"])
        buttons.append([InlineKeyboardButton(
            title[:52] + ("…" if len(title) > 52 else ""),
            callback_data=f"v2:i:{row['item_kind']}:{row['id']}",
        )])
    paging: list[InlineKeyboardButton] = []
    if page > 0:
        paging.append(InlineKeyboardButton("◀ Înapoi", callback_data=f"v2:a:{intent}:{page - 1}"))
    if has_more:
        paging.append(InlineKeyboardButton("Mai multe ▶", callback_data=f"v2:a:{intent}:{page + 1}"))
    if paging:
        buttons.append(paging)
    if intent in {"money", "balance", "expenses"}:
        buttons.append([
            InlineKeyboardButton("Cheltuială nouă", callback_data="v2:new:money"),
            InlineKeyboardButton("Venit nou", callback_data="v2:new:income"),
        ])
    else:
        buttons.append([InlineKeyboardButton(_ADD_PROMPTS[intent][0], callback_data=f"v2:new:{intent}")])
    buttons.append([InlineKeyboardButton("Înapoi", callback_data=f"v2:n:{intent}")])
    heading = f"Alege un element · pagina {page + 1}:" if rows else "Nu am elemente de afișat aici."
    return heading, InlineKeyboardMarkup(buttons)


async def item_detail(
    pool: asyncpg.Pool, settings: Settings, owner_id: int, kind: str, item_id: uuid.UUID,
) -> tuple[str, InlineKeyboardMarkup] | None:
    async with pool.acquire() as conn:
        if kind == "t":
            row = await conn.fetchrow(
                """SELECT title,notes,due_at,version FROM tasks
                WHERE id=$1 AND owner_id=$2 AND status='pending'""", item_id, owner_id,
            )
            if not row:
                return None
            text = f"Task: {row['title']}"
            if row["due_at"]:
                text += f"\nTermen: {row['due_at'].astimezone(ZoneInfo(settings.timezone)):%d.%m %H:%M}"
            if row["notes"]:
                text += f"\n{row['notes']}"
            buttons = [[
                InlineKeyboardButton("Gata", callback_data=f"v2:t:{item_id}:{row['version']}:done"),
                InlineKeyboardButton("Mâine 09:00", callback_data=f"v2:q:t:{item_id}:{row['version']}:tomorrow"),
            ]]
        elif kind == "e":
            row = await conn.fetchrow(
                """SELECT title,notes,starts_at,kind,legacy_source,version FROM calendar_entries
                WHERE id=$1 AND owner_id=$2 AND status='active'""", item_id, owner_id,
            )
            if not row:
                return None
            text = f"{row['kind'].capitalize()}: {row['title']}\n{row['starts_at'].astimezone(ZoneInfo(settings.timezone)):%d.%m %H:%M}"
            if row["notes"]:
                text += f"\n{row['notes']}"
            buttons = []
            if row["kind"] == "reminder":
                buttons.append([
                    InlineKeyboardButton("Gata", callback_data=f"v2:e:{item_id}:{row['version']}:done"),
                    InlineKeyboardButton("+1 oră", callback_data=f"v2:q:e:{item_id}:{row['version']}:hour"),
                    InlineKeyboardButton("Mâine", callback_data=f"v2:e:{item_id}:{row['version']}:tomorrow"),
                ])
            elif (row["kind"] == "academic" and row["legacy_source"] == "academic_rule"
                  and row["starts_at"] <= datetime.now(ZoneInfo(settings.timezone))):
                buttons.append([
                    InlineKeyboardButton("Am fost", callback_data=f"v2:q:a:{item_id}:{row['version']}:yes"),
                    InlineKeyboardButton("Am lipsit", callback_data=f"v2:q:a:{item_id}:{row['version']}:no"),
                ])
        elif kind == "n":
            row = await conn.fetchrow(
                """SELECT title,course_title,body,discussion_url,content_hash FROM moodle_posts
                WHERE id=$1 AND owner_id=$2 AND archived_at IS NULL AND filtered_out=false""", item_id, owner_id,
            )
            if not row:
                return None
            text = f"{row['course_title']} · {row['title']}\n\n{row['body'][:3000]}"
            buttons = [[
                InlineKeyboardButton("Citit", callback_data=f"v2:q:n:{item_id}:{row['content_hash'][:8]}:read"),
                InlineKeyboardButton("Arhivează", callback_data=f"v2:q:n:{item_id}:{row['content_hash'][:8]}:archive"),
            ]]
            if row["discussion_url"].startswith("https://"):
                buttons.append([InlineKeyboardButton("Deschide forumul", url=row["discussion_url"])])
        elif kind == "x":
            row = await conn.fetchrow(
                """SELECT description,merchant,amount,currency,category,spent_at,version FROM expenses
                WHERE id=$1 AND owner_id=$2 AND deleted_at IS NULL""", item_id, owner_id,
            )
            if not row:
                return None
            text = (f"Cheltuială: {row['amount']} {row['currency']} · {row['category']}\n"
                    f"{row['description'] or row['merchant'] or ''}\n"
                    f"{row['spent_at'].astimezone(ZoneInfo(settings.timezone)):%d.%m %H:%M}\n"
                    "Pentru alte editări sau ștergere, deschide Mini App → Jurnal.")
            buttons = [[InlineKeyboardButton(
                "Schimbă categoria", callback_data=f"v2:c:{item_id}:{row['version']}",
            )]]
        elif kind == "w":
            row = await conn.fetchrow(
                """SELECT activity,duration_minutes,started_at,notes FROM workouts
                WHERE id=$1 AND owner_id=$2 AND deleted_at IS NULL""", item_id, owner_id,
            )
            if not row:
                return None
            text = (f"Antrenament: {row['activity']} · {row['duration_minutes']} min\n"
                    f"{row['started_at'].astimezone(ZoneInfo(settings.timezone)):%d.%m %H:%M}")
            if row["notes"]:
                text += f"\n{row['notes']}"
            buttons = []
        else:
            return None
    parent = {"t": "tasks", "e": "calendar", "n": "news", "x": "money", "w": "workout"}[kind]
    buttons.append([InlineKeyboardButton("Înapoi la listă", callback_data=f"v2:a:{parent}")])
    return text[:3900], InlineKeyboardMarkup(buttons)


async def category_menu(
    pool: asyncpg.Pool, owner_id: int, expense_id: uuid.UUID, version: int,
) -> tuple[str, InlineKeyboardMarkup] | None:
    async with pool.acquire() as conn:
        expense = await conn.fetchrow(
            """SELECT amount,currency,category FROM expenses WHERE id=$1 AND owner_id=$2
            AND version=$3 AND deleted_at IS NULL""", expense_id, owner_id, version,
        )
        if not expense:
            return None
        categories = await conn.fetch(
            """SELECT id,name FROM expense_categories WHERE owner_id=$1 AND is_active=true
            ORDER BY name LIMIT 30""", owner_id,
        )
    rows = [[InlineKeyboardButton(
        str(row["name"])[:40],
        callback_data=f"v2:k:{expense_id}:{version}:{row['id'].hex[:8]}",
    )] for row in categories if row["name"] != expense["category"]]
    rows.append([InlineKeyboardButton("Înapoi", callback_data=f"v2:i:x:{expense_id}")])
    text = (f"Alege categoria pentru {expense['amount']} {expense['currency']}.\n"
            f"Acum: {expense['category']}.")
    if not categories:
        text += "\nNu ai categorii active. Adaugă-le în Mini App → Jurnal."
    return text, InlineKeyboardMarkup(rows)


async def change_expense_category(
    pool: asyncpg.Pool, owner_id: int, expense_id: uuid.UUID,
    version: int, category_prefix: str,
) -> str | None:
    if len(category_prefix) != 8 or any(char not in "0123456789abcdef" for char in category_prefix):
        return None
    async with pool.acquire() as conn:
        async with conn.transaction():
            categories = await conn.fetch(
                """SELECT name FROM expense_categories WHERE owner_id=$1 AND is_active=true
                AND left(replace(id::text,'-',''),8)=$2""", owner_id, category_prefix,
            )
            if len(categories) != 1:
                return None
            row = await conn.fetchrow(
                """UPDATE expenses SET category=$4,version=version+1,updated_at=now()
                WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL
                RETURNING amount,currency""",
                expense_id, owner_id, version, categories[0]["name"],
            )
            if not row:
                return None
            return f"Categoria pentru {row['amount']} {row['currency']} este acum {categories[0]['name']}."


async def record_class_attendance(
    pool: asyncpg.Pool, settings: Settings, owner_id: int, entry_id: uuid.UUID,
    version: int, attended: bool,
) -> str | None:
    """Write one attendance row per materialized class, even after repeated taps."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            entry = await conn.fetchrow(
                """SELECT title,starts_at FROM calendar_entries
                WHERE id=$1 AND owner_id=$2 AND version=$3 AND status='active'
                AND kind='academic' AND legacy_source='academic_rule' AND starts_at <= now()""",
                entry_id, owner_id, version,
            )
            if not entry:
                return None
            day = entry["starts_at"].astimezone(ZoneInfo(settings.timezone)).date()
            rules = await conn.fetch(
                "SELECT id,subject_id FROM academic_schedule_rules WHERE owner_id=$1 AND is_active=true",
                owner_id,
            )
            rule = next((item for item in rules if uuid.uuid5(
                ACADEMIC_NAMESPACE, f"{owner_id}:{item['id']}:{day.isoformat()}"
            ) == entry_id), None)
            if not rule:
                return None
            attendance_id = uuid.uuid5(ACADEMIC_NAMESPACE, f"{owner_id}:attendance:{entry_id}")
            existing = await conn.fetchrow(
                """SELECT id,attended FROM academic_attendance WHERE owner_id=$1
                AND schedule_rule_id=$2 AND class_date=$3 AND deleted_at IS NULL
                ORDER BY id LIMIT 1 FOR UPDATE""", owner_id, rule["id"], day,
            )
            if existing:
                if existing["attended"] != attended:
                    await conn.execute(
                        """UPDATE academic_attendance SET attended=$3,version=version+1
                        WHERE id=$1 AND owner_id=$2""", existing["id"], owner_id, attended,
                    )
            else:
                await conn.execute(
                    """INSERT INTO academic_attendance
                    (id,owner_id,subject_id,schedule_rule_id,class_date,attended)
                    VALUES ($1,$2,$3,$4,$5,$6)
                    ON CONFLICT (id) DO UPDATE SET attended=EXCLUDED.attended,
                    version=academic_attendance.version+1,deleted_at=NULL
                    WHERE academic_attendance.owner_id=EXCLUDED.owner_id
                    AND (academic_attendance.attended IS DISTINCT FROM EXCLUDED.attended
                         OR academic_attendance.deleted_at IS NOT NULL)""",
                    attendance_id, owner_id, rule["subject_id"], rule["id"], day, attended,
                )
            return f"{'Prezență' if attended else 'Absență'} salvată: {entry['title']} · {day:%d.%m}."

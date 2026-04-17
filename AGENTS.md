# AGENTS.md — Lora Development Guide

> For AI coding agents. Read before making changes.

## Project Overview

Personal Telegram bot ("second brain") for one user:
- **Python** 3.11+ with required type hints
- **Telegram**: `python-telegram-bot==22.6` (async, long polling)
- **LLM**: `google-genai` SDK with `gemini-2.0-flash`
- **Database**: Neon PostgreSQL via `asyncpg` — **no ORM**
- **Scheduler**: `apscheduler==3.10.4`

**Flow**: `message → core/gemini.py → core/router.py → modules/{module}.py → db/queries/{module}.py`

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python main.py

# Lint (required before commit)
ruff check .

# Format code
ruff format .

# Database init (fresh)
psql $DATABASE_URL -f db/schema.sql

# Apply migrations (existing DB)
psql $DATABASE_URL -f db/migrations/001_schema_fixes.sql
```

## Code Style

### Type Hints (Required)
```python
def foo(pool, user_id: int) -> Tuple[str, Any]:
    data: Dict[str, Any] = {}
    value: int | None = None

async def get_user(pool, user_id: int) -> Optional[Dict[str, Any]]:
```

### Imports (Ordered)
```python
# stdlib
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

# third-party
import asyncpg

# local (absolute imports, no relative)
from db.queries.tasks import add_task
from bot.formatter import escape_md
```

### Naming
| Type | Convention | Example |
|------|------------|---------|
| Files | `snake_case.py` | `task_queries.py` |
| Functions | `snake_case` | `async def get_user_profile` |
| Classes | `PascalCase` | `MyValidator` |
| Constants | `UPPER_SNAKE_CASE` | `TELEGRAM_BOT_TOKEN` |

### Docstrings (Google Style)
```python
async def get_user(pool, user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user by ID from database.
    
    Args:
        pool: Database connection pool.
        user_id: The user's Telegram ID.
    
    Returns:
        User dict or None if not found.
    """
```

## Error Handling

```python
async def my_handler(update, context):
    try:
        # ... logic ...
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        await update.message.reply_text("A apărut o eroare.")
```

- Wrap every handler in try/except
- Log with `print(f"ERROR: {e}")` + `traceback.print_exc()`
- User errors in Romanian, system comments in English

## Database (asyncpg)

```python
async def get_user(pool, user_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(row) if row else None
```

**Rules**:
- Use `$1, $2` placeholders — never f-strings or string interpolation
- Keep queries in `db/queries/{module}.py`
- Use `json.loads()` for JSON columns

## Modules Pattern

Modules return `(reply_text, keyboard_or_none)`:

```python
async def handle_module_intent(
    pool,
    intent: str,
    data: Dict[str, Any]
) -> Tuple[str, InlineKeyboardMarkup | None]:
    if intent == "add_item":
        return "Adăugat!", None
    return "Intent not handled", None
```

**Never call Telegram directly** — return data, let `handler.py` send.

## MarkdownV2 Formatting

Use `bot/formatter.py`:

| Function | Use for |
|----------|---------|
| `escape_md(text)` | User input, titles, untrusted text |
| `safe_markdown(text)` | Gemini output, formatted strings |
| `split_message(text)` | Messages over 4096 chars |

**Characters to escape**: `_` `*` `[` `]` `(` `)` `~` `` ` `` `>` `#` `+` `-` `=` `|` `{` `}` `.` `!`

**Date strings should NOT be escape_md'd** — `escape_md("2026-03-26")` produces `2026\\-03\\-26` which breaks MarkdownV2.

## State Machine (`core/state.py`)

```python
await set_state(pool, "awaiting_confirmation", module, action, entity_id)
state = await get_state(pool)
await clear_state(pool)
```

**States**: `awaiting_confirmation`, `awaiting_edit_field`, `null`

## Folder Structure

```
lora/
├── main.py                    # Entry point — asyncio loop, handlers, scheduler, web server
├── requirements.txt
├── railway.json               # Railway deployment (numReplicas: 1)
├── api/routes.py              # HTTP API routes
│
├── bot/
│   ├── handler.py             # Message routing, security, dispatch
│   ├── keyboards.py           # InlineKeyboardMarkup builders
│   ├── formatter.py           # MarkdownV2 utilities
│   ├── voice.py               # STT transcription
│   ├── tts.py                # edge-tts wrapper
│   └── onboarding.py          # First-run wizard
│
├── core/
│   ├── gemini.py              # LLM calls, system prompt, IntentResponse
│   ├── router.py              # Intent → module routing
│   ├── context.py             # build_context() for prompts
│   ├── state.py               # State machine
│   ├── config.py              # Env var loading + startup validation
│   ├── memory.py              # Long-term fact extraction
│   └── ical.py               # Calendar generation
│
├── modules/                   # Business logic (no Telegram calls)
│   ├── tasks.py              ├── habits.py             ├── projects.py
│   ├── notes.py              ├── finance.py            ├── events.py
│   ├── shopping.py           ├── goals.py              ├── skills.py
│   ├── health.py             ├── nutrition.py          ├── workout.py
│   ├── university.py         ├── schedule.py           ├── reading.py
│   ├── focus.py              ├── planner.py            ├── mood.py
│   ├── insights.py           ├── memory.py             ├── news.py
│   └── weather.py
│
├── scheduler/
│   └── jobs.py               # APScheduler jobs (morning briefing, EOD, etc.)
│
├── db/
│   ├── connection.py         # asyncpg pool
│   ├── schema.sql            # Table definitions
│   └── queries/              # Raw SQL per module
└── api/
    └── routes.py             # HTTP endpoints
```

## Key Files

| File | Purpose |
|------|---------|
| `core/gemini.py` | LLM calls, system prompt, IntentResponse |
| `core/router.py` | Routes intents to modules |
| `bot/handler.py` | Message routing, security, dispatch |
| `bot/formatter.py` | MarkdownV2 escaping |
| `db/schema.sql` | All table definitions |

## Language

- **Romglish**: Romanian base, English tech terms
- User errors in Romanian: "A apărut o eroare"
- Avoid filler: "Sigur!", "Cu plăcere!"
- Max 1 sentence for simple actions

## Gotchas

- SDK: `from google import genai` — NOT `google-generativeai`
- `/reload` uses `os.execl()` — hard restart
- Railway: `numReplicas: 1` for long polling
- `bot.log` not rotated
- No test suite exists

## Deploy

```bash
ruff check .                    # Must pass
git add -A
git commit -m "description"
git push                        # Railway auto-deploys
```

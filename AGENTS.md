# AGENTS.md — Development Guide for Lora

> For AI coding agents. Read before making any changes.

---

## Project Overview

**Lora** is a personal Telegram bot (single-user) acting as a "second brain":
- **Language**: Python 3.11+ with required type hints
- **Telegram**: `python-telegram-bot==22.6` (async, long polling)
- **LLM**: `google-genai` SDK with `gemini-2.0-flash`
- **Database**: Neon PostgreSQL via `asyncpg` — **no ORM**
- **Scheduler**: `apscheduler==3.10.4`

**Architecture**: `message → core/gemini.py → core/router.py → modules/{module}.py → db/queries/{module}.py`

---

## Commands

### Run the bot
```bash
pip install -r requirements.txt
python main.py
```

### Lint (required before committing)
```bash
ruff check .
```

### Typecheck (if mypy configured)
```bash
ruff check . --select=ANN  # If type annotations enabled
```

### Test
No test framework exists. To add tests:
```bash
pip install pytest pytest-asyncio
pytest tests/                    # Run all tests
pytest tests/test_tasks.py     # Run single test file
pytest tests/ -v               # Verbose output
```

### Database
```bash
psql $DATABASE_URL -f db/schema.sql  # Initialize (run once)
```

---

## Code Style

### Type Hints (Required)
```python
# Use Python 3.9+ syntax
def foo(pool, user_id: int) -> Tuple[str, Any]:
    data: Dict[str, Any] = {}
    items: list[dict[str, Any]] = []
    value: int | None = None

# All async functions
async def get_user(pool, user_id: int) -> Optional[Dict[str, Any]]:
```

### Imports (Ordered)
```python
# stdlib
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
import json

# third-party
import asyncpg

# local (absolute imports, no relative)
from db.queries.tasks import add_task
from bot.formatter import escape_md

# NEVER: from .module import * or from module import *
```

### Naming Conventions
| Type | Convention | Example |
|------|------------|---------|
| Files | `snake_case.py` | `task_queries.py` |
| Functions | `snake_case` | `async def get_user_profile` |
| Classes | `PascalCase` | `MyValidator` |
| Constants | `UPPER_SNAKE_CASE` | `TELEGRAM_BOT_TOKEN` |
| Async | `async def` + `await` | Always use both |

### Formatting
- Ruff configured (no explicit `pyproject.toml` needed)
- No line length limit enforced, keep under 120 chars
- **Escape f-string parens for Markdown**: `\\(` not `\(` (Python 3.13)

---

## Error Handling

```python
async def my_handler(update, context):
    try:
        # ... logic ...
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        await update.message.reply_text("A apărut o eroare. Te rog să încerci din nou.")
```

Rules:
- Wrap every handler/job in try/except
- Log with `print(f"ERROR: {e}")` + `traceback.print_exc()`
- Send friendly message in Romanian
- Never expose raw exceptions to user

---

## Database (asyncpg Raw SQL)

### Query Pattern
```python
async def get_user(pool, user_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1",
            user_id
        )
        return dict(row) if row else None
```

### Rules
- **Use `$1, $2` placeholders** — never f-strings or `%` formatting
- Keep queries in `db/queries/{module}.py`
- Never create/alter tables in application code
- Use `json.loads()` to parse JSON columns

---

## Modules Pattern

Every module (`modules/{module}.py`) must:

1. **Accept** `(pool, intent: str, data: Dict[str, Any])` or `(query, pool, data: str)`
2. **Return** `Tuple[str, InlineKeyboardMarkup | None]`
3. **Never call Telegram directly** — return data, let `bot/handler.py` send

```python
async def handle_module_intent(
    pool,
    intent: str,
    data: Dict[str, Any]
) -> Tuple[str, InlineKeyboardMarkup | None]:
    if intent == "add_item":
        # ... logic ...
        return "Adăugat!", None
    return "Intent not handled", None
```

---

## MarkdownV2 Formatting

**Use `bot/formatter.py`** — never escape manually:

| Function | Use for |
|----------|---------|
| `escape_md(text)` | User input, titles, any untrusted text |
| `safe_markdown(text)` | Gemini output, formatted strings |
| `split_message(text)` | Messages over 4096 chars |

**Common escapes**: `_` `*` `[` `]` `(` `)` `~` `` ` `` `>` `#` `+` `-` `=` `|` `{` `}` `.` `!` `/`

```python
# Bad
"Book: *{title}*"        # title might have *

# Good
f"Book: *{escape_md(title)}*"
```

**Rating in bold** (escapes the dot):
```python
f"*\\{escape_md(str(avg_rating))}\\*"  # produces *5\.0*
```

---

## State Machine (`core/state.py`)

```python
from core.state import set_state, get_state, clear_state

# Set state
await set_state(pool, "awaiting_confirmation", module, action, entity_id)

# Check state
state = await get_state(pool)
if state and state.get("state") == "awaiting_confirmation":
    # handle...

# Clear after completion
await clear_state(pool)
```

**States**: `awaiting_confirmation`, `awaiting_edit_field`, `awaiting_journal_response`, `in_focus_session`, `null`

---

## Gemini Response Contract

```json
{
  "intent": "add_task",
  "data": {"title": "Buy milk", "priority": "high"},
  "reply": "✓ Adăugat: *Buy milk*"
}
```

- `reply` field: **raw MarkdownV2** — no backslashes
- Parse with `json.loads()`, retry once on failure
- `reply` can contain `\"` — handle in JSON parsing

---

## Scheduler Jobs (`scheduler/jobs.py`)

```python
async def send_morning_briefing(app: Application):
    try:
        pool = app.bot_data["pool"]
        last = await get_last_briefing_date(pool)
        if last == today:
            return  # idempotent
        
        # ... logic ...
        await set_last_briefing_date(pool, today)
    except Exception as e:
        print(f"ERROR in send_morning_briefing: {e}")
        traceback.print_exc()
```

- Wrap in try/except
- Check `last_*_date` for idempotency
- Use `misfire_grace_time=3600`

---

## Voice/TTS

**Incoming voice**: `bot/voice.py` → transcribe → rejoin pipeline

**Outgoing TTS**:
```python
from bot.tts import generate_voice
mp3_path = await generate_voice(text)
await update.message.reply_voice(voice=open(mp3_path, 'rb'))
```

- Strip Markdown before edge-tts
- Use `ro-RO-AlinaNeural` voice

---

## Language

- **Romglish**: Romanian base, English tech terms mixed naturally
- User errors in Romanian: "A apărut o eroare"
- System comments in English
- Avoid filler: "Sigur!", "Cu plăcere!", "Bineînțeles!"
- Max 1 sentence for simple actions (add_task, log_habit)

---

## Folder Structure

```
lora/
├── main.py                    # Entry point, ApplicationBuilder
├── bot/
│   ├── handler.py             # Main router, security, dispatch
│   ├── keyboards.py           # InlineKeyboardMarkup builders
│   ├── formatter.py           # MarkdownV2 utilities
│   ├── onboarding.py          # First-run wizard
│   ├── tts.py                 # edge-tts wrapper
│   └── voice.py               # STT transcription
├── core/
│   ├── gemini.py              # LLM integration, IntentResponse
│   ├── config.py              # Env var loading
│   ├── context.py             # build_context() for prompts
│   ├── router.py              # Maps intent → module
│   └── state.py               # Conversation state machine
├── modules/                   # Pure business logic
│   ├── tasks.py, habits.py, projects.py, ...
├── scheduler/
│   └── jobs.py                # APScheduler jobs
└── db/
    ├── connection.py          # asyncpg pool
    ├── schema.sql             # Table definitions
    └── queries/               # Raw SQL per module
```

---

## Key Files

| File | Purpose |
|------|---------|
| `core/gemini.py` | LLM calls, system prompt, IntentResponse parsing |
| `core/router.py` | Routes intents to correct module |
| `core/state.py` | Conversation state machine |
| `bot/handler.py` | Message routing, security check, dispatch |
| `bot/formatter.py` | MarkdownV2 escaping utilities |
| `bot/keyboards.py` | All inline keyboard builders |
| `db/schema.sql` | All table definitions (source of truth) |

---

## Quirks & Gotchas

- SDK: `from google import genai` — NOT `google-generativeai`
- `conversation_state` table has exactly one row (`state_key='current'`)
- `/reload` uses `os.execl()` — hard process restart, drops in-flight requests
- `bot.log` grows indefinitely (not rotated)
- Railway: `numReplicas: 1` required for long polling
- JSON parsing `reply` field: handle `\\"` escape sequences

---

## Deploy

```bash
ruff check .                    # Must pass
git add -A
git commit -m "description"
git push                        # Railway auto-deploys
```

Verify: `/start` in Telegram → send test message

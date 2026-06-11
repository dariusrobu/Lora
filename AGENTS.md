# AGENTS.md — Lora Development Guide

> For AI coding agents. Read before making changes.

## Stack

- **Python** 3.11+ with required type hints
- **LLM**: `gemini-2.5-flash` via `from google import genai` — NOT legacy `google-generativeai`
- **Telegram**: `python-telegram-bot==22.6` (long polling)
- **Database**: Neon PostgreSQL via `asyncpg` — no ORM
- **Scheduler**: `apscheduler==3.10.4`
- **Hosting**: Railway (`numReplicas: 1`)

## Core Architecture

`message → core/gemini.py → core/router.py (Confirmation Interception) → bot/handler.py (Action Keyboard/Buttons) → modules/{module}.py → db/queries/{module}.py`

**Never call Telegram directly from modules** — return `(reply_text, keyboard_or_none)` and let `handler.py` send.

### IntentResponse Schema

Gemini must return valid JSON with these fields:

```json
{
  "intent": "add_task | chat | clarify | ...",
  "module": "tasks | skills | null | ...",
  "data": { ... },
  "reply": "MarkdownV2 text — RAW characters, NO backslash escaping",
  "needs_confirmation": false,
  "needs_agent": false,
  "agent_tools_needed": ["tool_get_tasks", ...]
}
```

**Date strings must NOT be escape_md'd** — produces `2026\-03\-26` which breaks MarkdownV2.

## Key Files

| File | Purpose |
|------|---------|
| `core/gemini.py` | System prompt (~450 lines), LLM calls, IntentResponse contract |
| `core/router.py` | Routes intents to modules, handles `needs_agent` |
| `core/agent.py` | Agentic mode for complex queries (`run_agent`) |
| `bot/handler.py` | Message routing, security check, dispatch |
| `bot/formatter.py` | `escape_md()` user input, `safe_markdown()` LLM output, `split_message()` |
| `db/schema.sql` | Source of truth — run `psql $DATABASE_URL -f db/schema.sql` once |

## Commands

```bash
# Run the bot
python main.py

# Lint (required before commit)
ruff check .

# Format
ruff format .

# Database init
psql $DATABASE_URL -f db/schema.sql
psql $DATABASE_URL -f db/migrations/001_schema_fixes.sql
psql $DATABASE_URL -f db/migrations/003_projects_enhanced.sql
psql $DATABASE_URL -f db/migrations/004_finance_categories.sql
```

## Required Env Vars

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`, `GEMINI_API_KEY`, `DATABASE_URL`, `TIMEZONE`, `MORNING_BRIEFING_TIME`, `EOD_REFLECTION_TIME`, `LORA_API_SECRET`, `COUNCIL_API_SECRET`

Additional (optional): `ICLOUD_USERNAME`, `ICLOUD_APP_PASSWORD`, `OPENWEATHER_API_KEY`

## Council Integration (Deprecated / Isolated)

All automatic Council integration and reporting have been disabled/isolated to prevent Lora from leaking data or triggering EOD reports to Council. The `core/council.py` module remains present but is not invoked automatically by tasks or scheduler jobs.

## Modules (23 total)

`tasks`, `skills` (replaces habits), `projects`, `notes`, `finance`, `events`, `shopping`, `goals`, `health`, `nutrition`, `workout`, `university`, `schedule`, `reading`, `focus`, `planner`, `insights`, `memory`, `weather`, `news`, `mood`, `calendar_module`, `calendar`

## Code Style

### Type hints (required)
```python
async def get_user(pool, user_id: int) -> Optional[Dict[str, Any]]:
```

### Imports (ordered)
```python
# stdlib
from typing import Dict, Any, Tuple, Optional

# third-party
import asyncpg

# local (absolute imports)
from db.queries.tasks import add_task
```

### DB queries
- Use `$1, $2` placeholders — never f-strings or string interpolation
- Keep queries in `db/queries/{module}.py`

### Error handling
```python
try:
    # ...
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
    await update.message.reply_text("A apărut o eroare.")
```
User errors in Romanian, system comments in English.

## State Machine

```python
# To request confirmation for an action
await set_state(pool, "awaiting_action_confirm", module, action, None, payload)

# To check state
state = await get_state(pool)
await clear_state(pool)
```
States: `awaiting_action_confirm` (write intent confirmation), `awaiting_confirmation` (delete confirmations), `awaiting_edit_field`, `null`

## Language

Romglish: Romanian base, English tech terms. User errors in Romanian: "A apărut o eroare." Max 1 sentence for simple actions. NO filler phrases: "Sigur!", "Cu plăcere!", "Bineînțeles!".

## Gotchas

- SDK: `from google import genai` — NOT `google-generativeai`
- `/reload` uses `os.execl()` — hard restart
- `bot.log` not rotated
- Startup: 10s delay to clear old polling instances (main.py:222)
- No test suite exists
- Calendar sync tables created in `main.py`, not `schema.sql`
- Voice input: STT → text → normal pipeline (bypasses Gemini during onboarding)
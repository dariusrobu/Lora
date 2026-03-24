# AGENTS.md — Development Guide for Lora

> This file is for AI coding agents. Read before making any changes.

---

## Project Overview

Lora is a personal Telegram bot (single-user) using:
- Python 3.11+ with type hints required everywhere
- `python-telegram-bot==22.6` (async, long polling)
- `google-genai` SDK with **gemini-2.0-flash** model
- `asyncpg` for raw SQL on Neon PostgreSQL — **no ORM**
- `apscheduler==3.10.4` for scheduled jobs

**Architecture**: message → `core/gemini.py` (IntentResponse JSON) → `core/router.py` → `modules/{module}.py` → `db/queries/{module}.py`

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

### Run a single test
No test framework currently exists. Add tests with `pytest` if needed.

### Database
```bash
psql $DATABASE_URL -f db/schema.sql  # Initialize (run once)
```

---

## Code Style Guidelines

### Type Hints
- **Required everywhere**: `def foo(pool, user_id: int) -> Tuple[str, Any]:`
- Use `list[dict[str, Any]]` (Python 3.9+ syntax), `int | None`, `Dict[str, Any]`

### Imports
- Group by: stdlib → third-party → local
- Use absolute imports: `from db.queries.tasks import add_task`
- Never use `from .module import *`

### Formatting & Linting
- Ruff is configured. Run `ruff check .` before commits.
- No line length limit enforced, but keep under 120 chars when practical.

### Naming Conventions
- **Files**: `snake_case.py` (e.g., `task_queries.py`)
- **Functions**: `snake_case` (e.g., `async def get_user_profile`)
- **Classes**: `PascalCase` (rarely used)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `TELEGRAM_BOT_TOKEN`)
- **Async**: prefix with `async def`, always `await` inside

### Error Handling
- Wrap every handler/job in try/except
- Log errors with `print(f"ERROR: {e}")` + `traceback.print_exc()`
- Send friendly error message to user in Romanian
- Never expose raw exception messages to user

### Database (asyncpg raw SQL)
- Use `$1, $2` placeholders — **never** f-strings or string interpolation
- Keep all queries in `db/queries/{module}.py` files
- Never create/alter tables in application code — use `db/schema.sql`

### Modules Pattern
Every module (`modules/{module}.py`) must:
1. Accept `(pool, intent: str, data: Dict[str, Any])` as arguments
2. Return `Tuple[str, InlineKeyboardMarkup | None]`
3. **Never call Telegram directly** — return data, let `bot/handler.py` send

### MarkdownV2 Formatting
- Always use `bot/formatter.py`: `escape_md()`, `safe_markdown()`, `split_message()`
- User input → `escape_md()` → prevents Markdown injection
- Gemini output → `safe_markdown()` → handles escaping
- Long messages → `split_message()` → respects Telegram's 4096 char limit

### State Machine (`core/state.py`)
- Use `set_state()` / `get_state()` / `clear_state()` for multi-turn flows
- Always `clear_state()` after completing a stateful flow
- States: `awaiting_confirmation`, `awaiting_edit_field`, `null`

### Gemini Response Contract
- `reply` field in JSON must be **raw MarkdownV2 characters** (no backslashes)
- The system prompt enforces: *"RAW characters in the JSON. DO NOT use backslashes to escape."*
- Parse with `json.loads()`, retry once on failure

### Scheduler Jobs (`scheduler/jobs.py`)
- Wrap in try/except, log errors
- Check `last_*_date` in user_profile for idempotency
- Use `misfire_grace_time=3600` for reliability

### Voice/TTY
- Incoming voice: `bot/voice.py` → transcribe → rejoin pipeline
- Outgoing TTS: `bot/tts.py` → returns temp `.ogg` path → send via `send_voice`
- Strip Markdown before passing to edge-tts

### Language
- **Romglish**: Romanian base, English tech terms naturally mixed
- User-facing errors in Romanian
- System/code comments in English

---

## Folder Structure

```
lora/
├── main.py              # Entry point, asyncio loop
├── bot/
│   ├── handler.py       # Message routing, security, dispatch
│   ├── keyboards.py     # Inline keyboard builders
│   ├── formatter.py     # MarkdownV2 utilities (escape_md, safe_markdown, split_message)
│   ├── onboarding.py    # First-run wizard
│   ├── tts.py           # edge-tts wrapper
│   └── voice.py         # STT (transcribe_voice)
├── core/
│   ├── gemini.py        # LLM integration (get_gemini_response, get_proactive_response)
│   ├── config.py        # Env var loading
│   ├── context.py       # build_context() — today's data snapshot
│   ├── router.py        # route_intent() — maps IntentResponse → module
│   └── state.py         # Conversation state machine
├── modules/             # Pure business logic (no Telegram calls)
│   ├── tasks.py, habits.py, projects.py, notes.py, finance.py...
├── scheduler/
│   └── jobs.py          # All APScheduler jobs
└── db/
    ├── connection.py    # asyncpg pool (get_pool, close_pool)
    ├── schema.sql       # Source of truth for all tables
    └── queries/         # One file per module (raw SQL)
```

---

## Key Files to Know

| File | Purpose |
|------|---------|
| `core/gemini.py` | LLM calls, system prompt, IntentResponse parsing |
| `core/router.py` | Routes intents to correct module |
| `bot/handler.py` | Main entry, security check, error wrapping |
| `bot/formatter.py` | MarkdownV2 escaping utilities |
| `db/schema.sql` | All table definitions |

---

## Known Quirks

- Uses `google-genai` SDK (not `google-generativeai`)
- `conversation_state` table has exactly one row (`state_key='current'`)
- `/reload` uses `os.execl()` — hard process restart
- `bot.log` grows indefinitely (not rotated)

---

## Copilot/Cursor Rules

No external rules files found. Follow this AGENTS.md and the conventions above.
# 🤖 Lora — Personal AI Second Brain (Telegram Bot)

> **For AI assistants (Claude, GPT, Gemini, etc.):** This README is your primary context document. Read it fully before suggesting any changes. The project is a **single-file-of-truth** architecture — all behaviour is driven by the system prompt in `core/gemini.py` and the routing logic in `core/router.py`. Before touching any file, understand how the intent pipeline flows (see §Architecture).

---

## What Is Lora?

Lora is a **private Telegram bot** that acts as a personal AI second brain for exactly one user. She is **not a generic chatbot** — she has persistent memory, understands natural language (including a Romanian-English mix called *Romglish*), manages nine life domains, and proactively reaches out on a daily schedule.

**Single-user design:** Security is enforced by a Telegram user ID whitelist. No auth system, no registration, no multi-tenancy.

---

## Current Stack (actual `requirements.txt`)

| Layer | Version / Package | Notes |
|---|---|---|
| Language | Python 3.11+ | Type hints required everywhere |
| Telegram | `python-telegram-bot==22.6` | Async, long polling |
| LLM | `google-genai` (latest) | **Model: `gemini-2.0-flash`** |
| Database | Neon (serverless PostgreSQL) | Cloud-hosted Postgres |
| DB driver | `asyncpg` | Raw SQL — **no ORM** |
| Scheduler | `apscheduler==3.10.4` | `AsyncIOScheduler` |
| HTTP | `httpx` | External calls |
| Config | `python-dotenv` | All secrets via `.env` |
| Hosting | Railway | Always-on, deploy via GitHub |
| TTS / Voice | `edge-tts` | Daily podcast voice messages |
| RSS | `feedparser` | News module |
| Linting | `ruff` | Linter + formatter |

> ⚠️ The code uses `from google import genai` / `from google.genai import types` — **not** the legacy `google-generativeai` package. The `LORA_AGENT_BRIEF_v2.md` spec is outdated on this point.

---

## Environment Variables

```env
# .env (never commit)
TELEGRAM_BOT_TOKEN=        # from @BotFather
TELEGRAM_USER_ID=          # numeric Telegram user ID (int)
GEMINI_API_KEY=            # from Google AI Studio
DATABASE_URL=              # postgres://user:pass@host/db?sslmode=require
TIMEZONE=Europe/Bucharest  # pytz-compatible string
MORNING_BRIEFING_TIME=08:00
EOD_REFLECTION_TIME=21:00
HABIT_REMINDER_TIME=18:00
WEEKLY_REVIEW_DAY=sunday
OPENWEATHER_API_KEY=       # optional, for weather module
```

Validated at startup in `core/config.py` — missing var = immediate crash with a clear error.

---

## Directory Structure

```
lora/
├── main.py                   # Entry point — asyncio loop, registers handlers, starts scheduler
├── requirements.txt
├── railway.json              # Railway deployment config
├── LORA_AGENT_BRIEF_v2.md    # Original spec (reference only, may be outdated)
│
├── bot/
│   ├── handler.py            # ★ Message routing, security check, voice/text/callback dispatch
│   ├── keyboards.py          # Inline keyboard builders (task, habit, mood, confirmation)
│   ├── formatter.py          # MarkdownV2 escaping — escape_md(), safe_markdown(), split_message()
│   ├── onboarding.py         # First-run wizard (name → timezone → capabilities overview)
│   ├── tts.py                # edge-tts wrapper → returns a temp .ogg file path
│   └── voice.py              # STT via Telegram voice → transcribe_voice() → returns text
│
├── core/
│   ├── gemini.py             # ★ LLM integration — get_gemini_response() + get_proactive_response()
│   ├── config.py             # Env var loading + startup validation
│   ├── context.py            # build_context() — snapshot of today's data injected in every prompt
│   ├── router.py             # route_intent() — maps IntentResponse → correct module function
│   └── state.py              # Conversation state machine (get/set/clear_state)
│
├── modules/                  # Pure business logic — no formatting, no Telegram calls
│   ├── tasks.py              # handle_task_intent()
│   ├── habits.py             # handle_habit_intent()
│   ├── projects.py           # handle_project_intent()
│   ├── notes.py              # handle_note_intent()
│   ├── finance.py            # handle_finance_intent()
│   ├── events.py             # handle_event_intent()
│   ├── shopping.py           # handle_shopping_intent()
│   ├── weather.py            # get_weather_summary() — OpenWeather API
│   ├── news.py               # fetch_tech_news() — RSS via feedparser
│   └── skills.py             # handle_skills_intent() — Custom metric tracking
│
├── scheduler/
│   └── jobs.py               # All cron jobs (morning briefing, EOD, habit reminder, missed-habit log)
│
└── db/
    ├── connection.py         # asyncpg pool — get_pool() / close_pool()
    ├── schema.sql            # ★ Source of truth for all tables
    └── queries/              # One file per module (raw asyncpg SQL functions)
        ├── tasks.py
        ├── habits.py
        ├── projects.py
        ├── notes.py
        ├── finance.py
        ├── events.py
        ├── shopping.py
        ├── goals.py
        ├── skills.py
        └── profile.py
```

---

## Architecture — How a Message Flows

```
Telegram Message
    │
    ▼ bot/handler.py → security_check()
    │   Reject non-whitelisted user IDs silently
    │
    ▼ Onboarding check (is_onboarding_complete)
    │   If false → bot/onboarding.py (bypasses Gemini)
    │
    ▼ Voice check: if VOICE → bot/voice.py → transcribe → rejoin text pipeline
    │
    ▼ Special commands (/reload, /podcast)
    │
    ▼ core/state.py → get_state()
    │   awaiting_confirmation → handle yes/no/unrelated
    │   awaiting_edit_field   → build edit prompt + call Gemini
    │   NULL                  → normal flow ↓
    │
    ▼ core/context.py → build_context()   [today's tasks/events/habits/finance/projects]
    │
    ▼ core/gemini.py → get_gemini_response()
    │   System prompt + context + last 10 history turns
    │   Returns: IntentResponse JSON
    │
    ▼ core/router.py → route_intent()
    │   module=null         → return reply directly
    │   needs_confirmation  → set_state() + send confirmation keyboard
    │   module=tasks/habits/… → call modules/{module}.handle_*_intent()
    │
    ▼ bot/formatter.py → escape_md() / safe_markdown()
    │
    ▼ bot/keyboards.py → attach InlineKeyboardMarkup
    │
    ▼ Save reply to conversations table
    │
    └─► Send to Telegram (MarkdownV2, with plain-text fallback)
```

---

## The IntentResponse Schema (Gemini Output Contract)

Every Gemini call **must** return this JSON. Parse with `json.loads()`. Retry once on failure.

```json
{
  "intent": "add_task | list_tasks | complete_task | edit_task | delete_task | add_habit | list_habits | log_habit | add_project | list_projects | archive_project | add_note | list_notes | log_expense | log_income | list_finance | finance_summary | add_event | list_events | add_item | list_items | delete_item | get_weather | fetch_news | update_profile | list_schedule | log_attendance | add_exam | workout_log | add_sport | add_exercise | view_prs | add_goal | add_subtask | complete_subtask | view_goals | chat | clarify",
  "module": "tasks | habits | projects | notes | finance | events | shopping | weather | news | university | workout | goals | health | nutrition | focus | null",
  "data": {
    "tasks":    { "title": "string", "priority": "low|medium|high", "due_date": "YYYY-MM-DD", "project": "string" },
    "habits":   { "name": "string", "frequency": "daily|weekly" },
    "finance":  { "amount": 0, "category": "string", "description": "string" },
    "events":   { "title": "string", "date": "YYYY-MM-DD", "time": "HH:MM" },
    "notes":    { "content": "string", "project": "string", "type": "note|journal" },
    "weather":  { "city": "string" },
    "shopping": { "item": "string", "category": "string" },
    "news":     { "topic": "string" },
    "projects": { "name": "string", "description": "string", "status": "active|archived|on-hold" },
    "university": { "subject": "string", "type": "curs|seminar|laborator", "date": "YYYY-MM-DD" },
    "workout":  { "sport_name": "string", "duration_min": 0, "calories": 0, "exercises": [] },
    "goals":    { "title": "string", "category": "string", "task_title": "string" },
    "health":   { "sleep_hours": 0, "water_ml": 0, "weight_kg": 0 }
  },
  "reply": "Lora's Telegram MarkdownV2 reply — RAW characters, NO JSON backslash escaping",
  "needs_confirmation": false
}
```

---

## Modules & Supported Intents

### University (`modules/university.py`)
- `list_schedule`, `log_attendance`, `add_exam`, `view_attendance_stats`
- **Week Parity**: Calculated based on `semester_start` from `semester_config`. Even (pară) / Odd (impară).
- **Attendance**: Logged per subject and type (Course/Seminar/Lab).

### Workout (`modules/workout.py`)
- `workout_log`, `view_prs`, `add_sport`, `add_exercise`, `view_week_stats`
- **NLP Logging**: Supports sentences like "am făcut gym 1h, bench press 60kg 5 repetări".
- **Sports/Exercises**: Custom list of sports (`sport_types`) and exercises.
- **Calories**: Optional field for calorie tracking per session.

### Goals Dashboard (`modules/goals.py`)
- `add_goal`, `add_subtask`, `complete_subtask`, `view_goals`, `complete_goal`
- **Hierarchy**: Goals can have multiple sub-tasks.
- **Progress**: Automatically recalculated (0-100%) based on completed sub-tasks.
- **Categories**: Academice, Sport, Skills, Financiare, Lectură, Personal, Sănătate.

### Health & Nutrition (`modules/health.py`, `modules/nutrition.py`)
- `log_health` (sleep, water, weight), `log_nutrition` (calories, quality)
- Trends and insights generated during EOD reflection.

### Focus & Planner (`modules/focus.py`, `modules/planner.py`)
- `start_focus`, `stop_focus`, `plan_day`
- Focus mode silences non-urgent notifications (logic in handler).
- Planner aggregates tasks and events into a cohesive daily schedule.

---

## Scheduled Jobs (`scheduler/jobs.py`)

| Job | Trigger | Description |
|---|---|---|
| `send_morning_briefing` | Daily at `MORNING_BRIEFING_TIME` | Tasks + events + habits + weather + shopping + tech news → Gemini synthesis → text + voice (TTS) |
| `send_habit_reminder` | Daily at `HABIT_REMINDER_TIME` | Nudge for pending habits |
| `send_eod_reflection` | Daily at `EOD_REFLECTION_TIME` | Completed tasks + habits → reflective summary + mood keyboard + voice |
| `missed_habit_nudge` | Daily at `MORNING_BRIEFING_TIME + 1h` | Logs `missed` for unchecked habits from yesterday |
| `check_event_reminders` | Every 15 minutes | Future: 1-day and 1-hour event reminders |

All jobs are idempotent (`last_briefing_date`, `last_eod_date` fields in `user_profile`).  
All jobs have `misfire_grace_time=3600` — if bot restarts late, it still fires.

---

## Voice Interface

- **Incoming voice → STT:** `bot/voice.py` → `transcribe_voice()` → plain text → rejoins normal pipeline
- **Outgoing TTS → podcast:** `bot/tts.py` → `text_to_speech()` → temp `.ogg` file → sent as `send_voice`
- TTS text is stripped of all MarkdownV2 markers before passing to `edge-tts`
- Both morning briefing and EOD reflection send a voice podcast in addition to the text message

---

## Conversation State Machine (`core/state.py`)

One row in `conversation_state` table (key = `'current'`). When idle, `state_type = NULL`.

| State | When set | Next message behaviour |
|---|---|---|
| `awaiting_confirmation` | User requests delete/bulk action | Yes-words → execute; No-words → cancel; Unrelated → clear state, process normally |
| `awaiting_edit_field` | User says "edit X" without specifying field | Next message → Gemini extracts the field + value, applies change, clears state |

---

## Personality & Language

Lora speaks **Romglish** — Romanian as the base language with natural English tech terms woven in (task, meeting, deadline, setup, sync, cool, anyway). She is:
- Warm, organised, proactive, never annoying
- Aware of the user's timezone, name, and personal facts
- Tone configurable in `user_profile.tone`: `warm` | `direct` | `brief`
- **Never breaks character** — fallback errors are phrased in Lora's voice

---

## Database Schema (key tables)

| Table | Purpose |
|---|---|
| `user_profile` | Single row — name, timezone, tone, personal_notes, onboarding_complete, briefing dates |
| `conversations` | Full message history (role: user/assistant) |
| `conversation_state` | Single-row state machine for multi-turn flows |
| `tasks` | priority, due_date, project_id, is_recurring, recurrence |
| `habits` | frequency, target_days[], streak_count, forgiveness_window |
| `habit_logs` | Per-day log: done/skipped/missed + UNIQUE(habit_id, log_date) |
| `notes` | type: note/journal, tags[], mood, is_pinned, GIN full-text index |
| `finances` | type: income/expense, amount, category, tx_date |
| `budget_limits` | Per-category monthly spending caps |
| `events` | event_date, event_time, reminded_1day, reminded_1hour flags |
| `projects` | status: active/paused/done/archived |
| `university_schedule` | day_of_week, start_time, end_time, week_type, type (Course/Seminar), location |
| `subjects` | academic subjects with avg_grade and target_grade |
| `attendance` | log of presence at university courses |
| `exams` | dates and types of university exams |
| `sport_types` | available sports with metric flags (distance, weight, reps), icon, category |
| `exercises` | muscle groups and exercise library |
| `workouts` | Individual exercise logs linked to a workout session |
| `goals` | High-level goals (Personal, Sport, etc.) |
| `goal_tasks` | Sub-tasks for each goal |
| `skills` | Custom skills (Chess, Duolingo, etc.) |
| `skill_logs` | Logs for skill metrics (Elo, minutes, points) |
| `health_metrics` | sleep, water, weight tracking logs |
| `nutrition_logs` | calorie intake and nutrition quality tracking |
| `focus_sessions` | log of deep work sessions |

Run schema once: `psql $DATABASE_URL -f db/schema.sql`

For existing databases, run migrations:
```bash
psql $DATABASE_URL -f db/migrations/001_schema_fixes.sql
```

---

## Special Commands (in Telegram)

| Command | What it does |
|---|---|
| `/reload` | Kills + re-execs the process (`os.execl`) for hot reload on Railway |
| `/podcast` | Manually triggers morning briefing (resets `last_briefing_date` first) |
| `/start` | Triggers onboarding if not complete |

---

## Setup & Running

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env (copy from .env.example and fill in values)

# 3. Initialize database (run once)
psql $DATABASE_URL -f db/schema.sql

# 4. Start bot
python main.py
```

The bot runs via **long polling**, not webhooks. Railway keeps the process alive. Logs go to stdout (line-buffered) and `bot.log`.

---

## Development Conventions for AI Assistants

1. **Type hints everywhere** — `str`, `int`, `Dict[str, Any]`, `Tuple[str, Any]`, etc.
2. **Raw SQL with asyncpg** — use `$1, $2` placeholders, never string interpolation.
3. **No ORM** — all queries are in `db/queries/*.py` files.
4. **Formatting is centralised** — always use `bot/formatter.py` functions (`escape_md`, `safe_markdown`, `split_message`). Never manually escape MarkdownV2.
5. **Modules return `(str, InlineKeyboardMarkup | None)`** — they never call Telegram directly.
6. **Gemini `reply` field** — must use RAW MarkdownV2 characters in JSON (no backslash escaping within the JSON string; `safe_markdown()` handles that before sending).
7. **State safety** — always call `clear_state()` after handling a stateful flow.
8. **Idempotency** — scheduled jobs check date fields before acting.
9. **Error handling** — every handler and job is wrapped in try/except; errors are logged and a friendly message is sent to the user.
10. **Linting** — run `ruff check .` before committing.

---

## Prompts for AI Assistants to Improve Lora

Use these ready-made prompts when working with an AI assistant on this codebase:

### 🆕 Add a New Feature
```
I want to add [FEATURE NAME] to Lora. The project is a single-user Telegram bot
using python-telegram-bot==22.6, Gemini 2.5 Flash (google-genai SDK), asyncpg
for raw SQL on Neon PostgreSQL, and APScheduler. The intent pipeline is:
message → core/gemini.py (returns IntentResponse JSON) → core/router.py →
modules/{module}.py → db/queries/{module}.py. Modules return (str, keyboard|None).
Please implement: [describe what you want].
```

### 🐛 Debug / Fix a Bug
```
In Lora (Python Telegram bot, gemini-2.0-flash, asyncpg/PostgreSQL):
Bug description: [WHAT IS WRONG]
Affected file(s): [e.g. core/gemini.py, modules/tasks.py]
Error message or observed behaviour: [PASTE ERROR / DESCRIBE]
Please suggest a fix that maintains the existing architecture.
```

### 🎨 Improve Lora's Personality / Responses
```
Lora is a Telegram personal assistant that speaks Romglish (Romanian base +
English tech terms). Her system prompt is in core/gemini.py → get_gemini_response().
Current tone: warm/direct/brief (configurable via user_profile.tone).
I want to: [DESCRIBE CHANGE — e.g. make her more playful, add sarcasm mode, improve
her morning briefing structure, add a weekly review message, etc.]
Please suggest changes to the system_prompt string in core/gemini.py.
```

### 📊 Add a New Module
```
I want to add a new module "[MODULE NAME]" to Lora. Following the existing pattern:
1. Create modules/{module}.py with handle_{module}_intent(pool, intent, data) -> (str, keyboard|None)
2. Create db/queries/{module}.py with asyncpg raw SQL functions
3. Add ALTER TABLE / CREATE TABLE to db/schema.sql
4. Register new intents in core/router.py → route_intent()
5. Add intent examples to the IntentResponse schema in core/gemini.py system prompt
6. Add trigger phrases in the system prompt instructions
Please implement: [MODULE DESCRIPTION]
```

### ⏰ Add a Scheduled Job
```
I want to add a new scheduled job to Lora. The scheduler is in scheduler/jobs.py,
using APScheduler AsyncIOScheduler. All jobs follow this pattern:
1. async def job_name(application, pool) — wraps everything in try/except
2. Fetch user profile for idempotency check and personalisation
3. Gather data, call get_proactive_response() from core/gemini.py
4. Call safe_markdown() from bot/formatter.py then split_message()
5. Send via application.bot.send_message() with ParseMode.MARKDOWN_V2 + fallback
6. Update last_*_date in user_profile to prevent duplicates
7. Register with scheduler.add_job() in setup_scheduler()
Please implement: [JOB DESCRIPTION]
```

### 🗄️ Modify the Database Schema
```
I want to add/modify a database table in Lora. Rules:
- Never create or alter tables in application code
- Add changes to db/schema.sql using CREATE TABLE IF NOT EXISTS or ALTER TABLE
- Use asyncpg raw SQL ($1, $2 placeholders) in db/queries/{module}.py
- No ORM
Change needed: [DESCRIBE THE SCHEMA CHANGE AND WHY]
```

---

## Known Quirks & Gotchas

- **`google-genai` vs `google-generativeai`:** The code uses the NEW `google-genai` SDK (`from google import genai`). The spec doc (`LORA_AGENT_BRIEF_v2.md`) references the old package. Do NOT mix them.
- **MarkdownV2 escaping is tricky:** Use `escape_md()` for user-supplied strings, `safe_markdown()` for Gemini-generated text. Never send raw user text as MarkdownV2.
- **`reply` in Gemini JSON:** The `reply` field comes back as raw MarkdownV2 — any backslashes in the JSON will double-escape. The system prompt says: *"RAW characters in the JSON. DO NOT use backslashes to escape characters."*
- **Onboarding bypasses Gemini:** The onboarding wizard uses direct string matching + button callbacks. Don't route onboarding messages through the intent pipeline.
- **State row is always ID=1:** `conversation_state` has exactly one row with `state_key='current'`. `set_state()` UPDATEs it; `clear_state()` NULLs the fields.
- **`/reload` is a hard process restart:** It calls `os.execl(sys.executable, ...)` — useful on Railway but be aware it drops any in-flight requests.
- **Bot log file:** `bot.log` in the root directory can grow very large. Not rotated automatically.

---

*Last updated: 2026-03-19 | Bot version: v2.5 (gemini-2.0-flash, google-genai SDK)*

# LORA — AI Coding Agent Brief (v2)
> Complete specification for building Lora, a personal AI assistant Telegram bot.
> Read this entire document before writing a single line of code.
> Do not invent behaviour not defined here. If something is ambiguous, follow the closest example in this document.

---

## 0. Prime directive

You are building **Lora** — a private, intelligent Telegram bot that acts as a personal second brain for a single user. Lora is not a generic chatbot. She has persistent memory, understands natural language, manages six life domains, and proactively reaches out to the user on a schedule.

**This app is for one user only.** Every architectural decision should reflect that. There is no multi-tenancy, no auth system, no user registration. Security is enforced by whitelisting a single Telegram user ID.

---

## 1. Tech stack — exact versions

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | Use type hints everywhere |
| Telegram | `python-telegram-bot==20.7` | Async, long polling (not webhook) |
| LLM | `google-generativeai` latest | Gemini 1.5 Flash model |
| Database | Neon (serverless PostgreSQL) | Cloud-hosted Postgres |
| DB driver | `asyncpg` + raw SQL | No ORM — keep queries explicit |
| Scheduler | `apscheduler==3.10.4` | AsyncIOScheduler |
| HTTP | `httpx` | For any external calls |
| Config | `python-dotenv` | All secrets via `.env` |
| Hosting | Railway | Always-on service, deploy via GitHub |
| Linting | `ruff` | Fast linter + formatter |

---

## 2. Environment variables

### `.env` (never commit)
```env
# Telegram
TELEGRAM_BOT_TOKEN=          # from @BotFather
TELEGRAM_USER_ID=            # your numeric Telegram user ID (integer)

# Gemini
GEMINI_API_KEY=              # from Google AI Studio

# Neon
DATABASE_URL=                # postgres://user:pass@host/db?sslmode=require

# App config
TIMEZONE=Europe/Bucharest    # user's timezone (pytz-compatible string)
MORNING_BRIEFING_TIME=08:00  # HH:MM in user's timezone
EOD_REFLECTION_TIME=21:00    # HH:MM in user's timezone
WEEKLY_REVIEW_DAY=sunday     # lowercase day name
```

### `.env.example` (commit this)
```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_USER_ID=
GEMINI_API_KEY=
DATABASE_URL=
TIMEZONE=Europe/Bucharest
MORNING_BRIEFING_TIME=08:00
EOD_REFLECTION_TIME=21:00
WEEKLY_REVIEW_DAY=sunday
```

### Startup validation (`core/config.py`)

At startup, load all vars and fail immediately if any required var is missing or empty:

```python
import os
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_USER_ID",
    "GEMINI_API_KEY",
    "DATABASE_URL",
    "TIMEZONE",
    "MORNING_BRIEFING_TIME",
    "EOD_REFLECTION_TIME",
    "WEEKLY_REVIEW_DAY",
]

for var in REQUIRED_VARS:
    if not os.getenv(var):
        raise EnvironmentError(f"Missing required environment variable: {var}")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Bucharest")
MORNING_BRIEFING_TIME = os.getenv("MORNING_BRIEFING_TIME", "08:00")
EOD_REFLECTION_TIME = os.getenv("EOD_REFLECTION_TIME", "21:00")
WEEKLY_REVIEW_DAY = os.getenv("WEEKLY_REVIEW_DAY", "sunday")
```

---

## 3. Project structure

```
lora/
├── main.py                  # entry point — starts bot + scheduler
├── .env                     # secrets (gitignored)
├── .env.example             # committed template with empty values
├── requirements.txt
├── railway.json             # Railway deployment config
├── .gitignore
├── README.md
│
├── bot/
│   ├── __init__.py
│   ├── handler.py           # Telegram message + callback handler
│   ├── keyboards.py         # inline keyboard builders for all modules
│   ├── formatter.py         # formats replies with Telegram MarkdownV2
│   └── onboarding.py        # first-run flow
│
├── core/
│   ├── __init__.py
│   ├── gemini.py            # Gemini client, prompt builder, response parser
│   ├── context.py           # builds context snapshot injected into every prompt
│   ├── router.py            # intent detection + module routing
│   ├── state.py             # conversation state machine (confirmations, edit flows)
│   └── config.py            # loads + validates all env vars at startup
│
├── modules/
│   ├── __init__.py
│   ├── tasks.py
│   ├── habits.py
│   ├── projects.py
│   ├── notes.py
│   ├── finance.py
│   └── events.py
│
├── scheduler/
│   ├── __init__.py
│   └── jobs.py              # all scheduled jobs
│
└── db/
    ├── __init__.py
    ├── connection.py        # asyncpg pool setup + reconnect logic
    ├── schema.sql           # full schema — source of truth
    └── queries/
        ├── tasks.py
        ├── habits.py
        ├── projects.py
        ├── notes.py
        ├── finance.py
        ├── events.py
        └── profile.py
```

---

## 4. Database schema

Run `schema.sql` once against Neon before starting the app. Never create or alter tables in application code.

```sql
-- db/schema.sql
-- Run once: psql $DATABASE_URL -f db/schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── User profile ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_profile (
    id                    SERIAL PRIMARY KEY,
    telegram_id           BIGINT UNIQUE NOT NULL,
    name                  TEXT,
    timezone              TEXT DEFAULT 'Europe/Bucharest',
    morning_time          TEXT DEFAULT '08:00',
    eod_time              TEXT DEFAULT '21:00',
    tone                  TEXT DEFAULT 'warm',   -- warm | direct | brief
    personal_notes        TEXT,                  -- freeform facts Lora knows
    onboarding_complete   BOOLEAN DEFAULT FALSE,
    last_briefing_date    DATE,                  -- prevents duplicate daily briefing
    last_eod_date         DATE,                  -- prevents duplicate EOD message
    last_weekly_date      DATE,                  -- prevents duplicate weekly review
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

-- ── Conversation history ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id          SERIAL PRIMARY KEY,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_conversations_created ON conversations(created_at DESC);

-- ── Conversation state ────────────────────────────────────────
-- Stores ephemeral state between turns (confirmations, edit flows)
CREATE TABLE IF NOT EXISTS conversation_state (
    id          SERIAL PRIMARY KEY,
    state_key   TEXT NOT NULL UNIQUE,   -- always 'current' (one row only)
    state_type  TEXT,                   -- 'awaiting_confirmation' | 'awaiting_edit_field' | null
    module      TEXT,                   -- which module the pending action belongs to
    action      TEXT,                   -- pending action e.g. 'delete'
    item_id     INT,                    -- id of the item being acted on
    extra       JSONB,                  -- any additional context needed to complete the action
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO conversation_state (state_key) VALUES ('current') ON CONFLICT DO NOTHING;

-- ── Projects ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    status      TEXT DEFAULT 'active'
                CHECK (status IN ('active', 'paused', 'done', 'archived')),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Tasks ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id            SERIAL PRIMARY KEY,
    title         TEXT NOT NULL,
    notes         TEXT,
    priority      TEXT DEFAULT 'medium'
                  CHECK (priority IN ('high', 'medium', 'low')),
    status        TEXT DEFAULT 'pending'
                  CHECK (status IN ('pending', 'done', 'cancelled')),
    due_date      DATE,
    project_id    INT REFERENCES projects(id) ON DELETE SET NULL,
    is_recurring  BOOLEAN DEFAULT FALSE,
    recurrence    TEXT CHECK (recurrence IN ('daily', 'weekly', 'monthly', NULL)),
    completed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tasks_status   ON tasks(status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);

-- ── Habits ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS habits (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    frequency           TEXT DEFAULT 'daily'
                        CHECK (frequency IN ('daily', 'weekly')),
    target_days         TEXT[],          -- ['mon','wed','fri'] for weekly habits
    streak_count        INT DEFAULT 0,
    longest_streak      INT DEFAULT 0,
    forgiveness_window  INT DEFAULT 1,   -- missed days before streak resets
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── Habit logs ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS habit_logs (
    id          SERIAL PRIMARY KEY,
    habit_id    INT NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    log_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    status      TEXT NOT NULL CHECK (status IN ('done', 'skipped', 'missed')),
    note        TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (habit_id, log_date)
);
CREATE INDEX idx_habit_logs_date ON habit_logs(log_date DESC);

-- ── Notes & Journal ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notes (
    id          SERIAL PRIMARY KEY,
    content     TEXT NOT NULL,
    type        TEXT DEFAULT 'note' CHECK (type IN ('note', 'journal')),
    tags        TEXT[],
    mood        TEXT CHECK (mood IN ('great', 'good', 'okay', 'bad', 'awful', NULL)),
    is_pinned   BOOLEAN DEFAULT FALSE,
    project_id  INT REFERENCES projects(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_notes_type ON notes(type);
CREATE INDEX idx_notes_tags  ON notes USING GIN(tags);
CREATE INDEX idx_notes_search ON notes USING GIN(to_tsvector('english', content));

-- ── Finance ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS finances (
    id          SERIAL PRIMARY KEY,
    type        TEXT NOT NULL CHECK (type IN ('income', 'expense')),
    amount      NUMERIC(12, 2) NOT NULL,
    currency    TEXT DEFAULT 'RON',
    category    TEXT NOT NULL,
    description TEXT,
    tx_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_finances_date ON finances(tx_date DESC);
CREATE INDEX idx_finances_type ON finances(type);

-- ── Budget limits ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS budget_limits (
    id            SERIAL PRIMARY KEY,
    category      TEXT NOT NULL UNIQUE,
    monthly_limit NUMERIC(12, 2) NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── Events ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id                SERIAL PRIMARY KEY,
    title             TEXT NOT NULL,
    description       TEXT,
    event_date        DATE NOT NULL,
    event_time        TIME,
    project_id        INT REFERENCES projects(id) ON DELETE SET NULL,
    is_recurring      BOOLEAN DEFAULT FALSE,
    recurrence        TEXT CHECK (recurrence IN ('daily','weekly','monthly','yearly', NULL)),
    remind_1day       BOOLEAN DEFAULT TRUE,
    remind_1hour      BOOLEAN DEFAULT TRUE,
    reminded_1day     BOOLEAN DEFAULT FALSE,   -- flag: 1-day reminder already sent
    reminded_1hour    BOOLEAN DEFAULT FALSE,   -- flag: 1-hour reminder already sent
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_events_date ON events(event_date);
```

---

## 5. Startup sequence (`main.py`)

```
1. Load + validate all env vars via core/config.py (raise on missing)
2. Initialize asyncpg connection pool (db/connection.py)
3. Ensure user_profile row exists for TELEGRAM_USER_ID
4. Initialize Gemini client (core/gemini.py)
5. Initialize AsyncIOScheduler and register all jobs (scheduler/jobs.py)
6. Start scheduler
7. Build python-telegram-bot Application
8. Register handlers (message, callback, command)
9. Print "Lora is running 🤖" to stdout
10. Start long polling
```

---

## 6. Onboarding flow (`bot/onboarding.py`)

Triggered when `user_profile.onboarding_complete = FALSE` for the user's first message.

### Flow

```
Step 1 — Greeting
  Lora: "Hi! I'm Lora, your personal assistant 👋
         Before we start, what should I call you?"

Step 2 — Name captured
  User: [any text — treat as their name]
  Lora: "Nice to meet you, [name]! 
         I've got your timezone set to Europe/Bucharest — is that right?"
         [Yes, that's right] [No, change it]

Step 3a — Timezone confirmed
  → proceed to Step 4

Step 3b — Timezone correction
  Lora: "What's your timezone? (e.g. Europe/London, America/New_York)"
  User: [timezone string]
  → validate with pytz, ask again if invalid
  → proceed to Step 4

Step 4 — Briefing
  Lora: "Perfect. Here's what I can help you with:
         📋 Tasks & Projects
         ✅ Habits
         📓 Notes & Journal
         💰 Finance
         📅 Events

         Just talk to me naturally — no commands needed.
         I'll send you a morning briefing every day at [morning_time]
         and check in with you each evening at [eod_time].

         What would you like to start with?"

Step 5 — Set onboarding_complete = TRUE, save name + timezone to user_profile
```

Onboarding uses a separate simple state tracked in `user_profile.onboarding_complete`. Do not route onboarding messages through the normal Gemini intent pipeline — handle them with direct string matching and button callbacks.

---

## 7. Conversation state machine (`core/state.py`)

Many interactions require more than one turn. The `conversation_state` table holds exactly one row (key = `'current'`) representing the pending state. When no multi-turn flow is active, `state_type` is NULL.

### State types

#### `awaiting_confirmation`
Set when Lora is about to perform a destructive action (delete, bulk clear).

```
User:  "delete task buy milk"
Lora:  "Are you sure you want to delete 'Buy milk'?"
       [Yes, delete] [Cancel]
       → state_type = 'awaiting_confirmation'
       → module = 'tasks', action = 'delete', item_id = 42
```

On next message or button press:
- If user says "yes" / taps [Yes, delete] → execute the action, clear state
- If user says "no" / taps [Cancel] → send "Cancelled.", clear state
- If user sends an unrelated message → clear state, process new message normally, do not execute the pending action

#### `awaiting_edit_field`
Set when Lora needs to know what the user wants to change.

```
User:  "edit task buy milk"
Lora:  "What would you like to change about 'Buy milk'?
        You can say things like:
        • change title to 'Buy oat milk'
        • set due date to Friday
        • change priority to high"
       → state_type = 'awaiting_edit_field'
       → module = 'tasks', action = 'edit', item_id = 42
```

On next message:
- Pass the user's reply + pending context back to Gemini to extract the specific field change
- Apply the change, clear state, confirm to user

If the user's next message in either state is clearly unrelated (a new intent), abandon the pending state and process the new message. Never hold the user hostage in a state.

### State management functions (`core/state.py`)

```python
async def get_state(pool) -> dict
async def set_state(pool, state_type, module, action, item_id, extra={}) -> None
async def clear_state(pool) -> None
```

---

## 8. Core engine

### 8.1 Message flow

```
Incoming Telegram message
    │
    ▼
Security check — reject non-whitelisted user IDs silently
    │
    ▼
Onboarding check — if onboarding_complete=FALSE, route to bot/onboarding.py
    │
    ▼
Save message to conversations (role='user')
    │
    ▼
State check (core/state.py)
    ├── state_type = 'awaiting_confirmation' → handle confirmation flow
    ├── state_type = 'awaiting_edit_field'  → handle edit field flow
    └── state_type = NULL → normal flow ↓
    │
    ▼
Build context snapshot (core/context.py)
    │
    ▼
Call Gemini (core/gemini.py) — returns IntentResponse JSON
    │
    ▼
Parse + validate IntentResponse (core/router.py)
    │
    ├── module = null → send reply directly (casual chat, no DB action)
    │
    ├── needs_confirmation = true → set state, send confirmation message + buttons
    │
    └── module = tasks/habits/projects/notes/finance/events
              → call modules/{module}.py with data
              → get result
              → format reply (bot/formatter.py)
              → attach inline keyboard (bot/keyboards.py)
    │
    ▼
Save reply to conversations (role='assistant')
    │
    ▼
Send reply to user
```

### 8.2 Context snapshot (`core/context.py`)

Built fresh on every message. Inject into Gemini system prompt.

```python
async def build_context(pool) -> str:
    """
    Returns a formatted string containing:
    - Today's date and day of week (in user's timezone)
    - Pending tasks: overdue (all) + due today
    - Today's events (with time if set)
    - Active habits + today's log status (done/pending) + current streak
    - Last 3 journal entries (date + first 100 chars of content)
    - This month's finance summary: total income, total expenses, top 3 categories
    - Active projects (name + status only)
    - User profile: name, tone, personal_notes
    """
```

Keep the context string under ~1500 tokens. If the user has many tasks or notes, truncate to the most relevant (overdue first, most recent first).

### 8.3 Conversation history

Pass the last **10 turns** (5 user + 5 assistant, alternating) to Gemini as the `messages` array. Older history stays in the DB for reference but is not sent to the model.

If the total token estimate (system prompt + context + history + new message) exceeds 900k tokens, reduce history to 6 turns, then 4, until it fits. Use a rough estimate of 4 chars = 1 token.

### 8.4 Gemini client (`core/gemini.py`)

```python
import google.generativeai as genai
from core.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
        temperature=0.4,
        max_output_tokens=1000,
    )
)
```

Always set `response_mime_type="application/json"`. Parse the response with `json.loads()`. If parsing fails, retry once with an explicit instruction appended: `"Your previous response was not valid JSON. Respond ONLY with the JSON object, no other text."`. If it fails again, return a fallback plain reply.

### 8.5 Gemini system prompt

Build this string in `core/gemini.py` and refresh it on every call (context changes each time).

```
You are Lora, a warm and intelligent personal assistant living inside Telegram.
You belong exclusively to {name}. You are their second brain.

PERSONALITY:
- Tone: {tone}  (warm = friendly and encouraging | direct = concise, no fluff | brief = shortest possible replies)
- You remember everything the user tells you
- You are organised, proactive, and never annoying
- You always use the user's local timezone: {timezone}
- You never break character

CAPABILITIES:
Tasks, Habits, Projects, Notes & Journal, Finance, Events.
Each supports: add, edit, rename, delete, complete, list, search.

TODAY: {date}, {day_of_week}

CURRENT CONTEXT:
{context_snapshot}

PERSONAL FACTS ABOUT {name}:
{personal_notes}

INSTRUCTIONS:
1. Always respond with a single valid JSON object matching the IntentResponse schema below.
   No markdown fences, no explanation outside the JSON.
2. Resolve all relative dates using today's date as anchor:
   "tomorrow" = {tomorrow}, "Friday" = next {next_friday}, "next week" = {next_week_start}.
3. Currency defaults to RON unless the user specifies otherwise.
4. If the request is ambiguous, set intent="clarify", module=null, and ask ONE short question in "reply".
5. If no DB action is needed (casual chat, general question), set module=null, data={}.
6. For destructive actions (delete, bulk operations), set needs_confirmation=true.
7. The "reply" field is what Lora says to the user. Write it in Lora's voice.
   Use Telegram MarkdownV2 formatting in "reply" (bold with *text*, code with `text`).
8. If the user is telling you a personal fact ("I'm a developer", "I live in Cluj"),
   set intent="update_profile", module=null, data={"fact": "..."}.

IntentResponse schema:
{
  "intent": string,              // e.g. "add_task", "list_habits", "log_expense", "chat", "clarify", "update_profile"
  "module": string | null,       // "tasks"|"habits"|"projects"|"notes"|"finance"|"events"|null
  "data": object,                // structured data extracted from the message
  "reply": string,               // Lora's reply in Telegram MarkdownV2
  "needs_confirmation": boolean  // true only for destructive actions
}
```

### 8.6 Fallback behavior

When Lora doesn't understand, she should say something natural and ask for clarification. She never says "I don't understand" blankly. Examples:

- "Hmm, I'm not sure what you'd like me to do there — could you say that differently?"
- "I want to help but I'm not quite following — are you talking about a task, a note, or something else?"

This fallback is generated by Gemini when `intent="clarify"`. Do not hardcode the exact string — let Gemini write it in Lora's voice.

---

## 9. Lora's voice — example exchanges

Use these to calibrate the system prompt and validate output. Lora's replies should always feel like these, not robotic or overly formal.

**Adding a task:**
```
User: add task review the proposal due thursday high priority
Lora: Done ✅ Added *Review the proposal* — due Thursday, high priority.
      [✅ Complete] [✏️ Edit] [🗑 Delete]
```

**Logging an expense:**
```
User: spent 32 lei on lunch today
Lora: Logged 💸 `32 RON` — food & drink, today.
      Running total this month: `847 RON` spent.
      [✏️ Edit] [🗑 Delete]
```

**Checking habits:**
```
User: did I meditate this week?
Lora: Here's your meditation streak this week:
      Mon ✅  Tue ✅  Wed ✅  Thu ⬜  Fri ⬜
      Current streak: *3 days* 🔥 Keep it up!
```

**Casual chat:**
```
User: I'm exhausted today
Lora: That's okay — some days are just like that. 
      You've still got 3 tasks pending for today. 
      Want to push any of them to tomorrow?
```

**Ambiguous input:**
```
User: edit the project
Lora: Which project would you like to edit?
      • Website redesign (active)
      • Home gym setup (paused)
```

**Delete with confirmation:**
```
User: delete task buy milk
Lora: Are you sure you want to delete *Buy milk*?
      [Yes, delete] [Cancel]
```

**Profile update:**
```
User: I'm a software developer
Lora: Got it, I'll remember that! 👨‍💻
```

**Doesn't understand:**
```
User: do the thing with the stuff
Lora: Hmm, I'm not quite sure what you mean — are you thinking of a task, a note, or something else?
```

---

## 10. Module specifications

Each module lives in `modules/{name}.py`. Modules are pure data functions — they receive structured `data` from the router, interact with the DB via `db/queries/{name}.py`, and return a result dict. They never format output or send messages directly.

Every module implements these base operations:

| Operation | DB action |
|---|---|
| `add` | INSERT |
| `edit` | UPDATE specific fields |
| `rename` | UPDATE name/title only |
| `delete` | DELETE (hard delete, after confirmation) |
| `complete` | UPDATE status + completed_at |
| `list` | SELECT with filters |
| `get` | SELECT single item by id or name |

### 10.1 Tasks (`modules/tasks.py`)

**Extracted data fields:** `title`, `notes`, `priority` (high/medium/low, default medium), `due_date` (ISO date or null), `project_id` (null if not linked), `is_recurring`, `recurrence`

**List display order:** overdue (⚠️ prefix) → due today → due this week → upcoming → no due date

**Complete:** set `status='done'`, `completed_at=NOW()`. If `is_recurring=true`, immediately create a new task with the same fields and the next calculated due date (daily +1 day, weekly +7 days, monthly +1 month).

**Delete:** always `needs_confirmation=true`.

**Edit flow:** if user says "edit task X" without specifying what to change, set state to `awaiting_edit_field`. If user says "change due date of task X to Friday" in one message, apply directly without confirmation.

**Week view:** filter `due_date` BETWEEN today AND today + 7 days.

### 10.2 Habits (`modules/habits.py`)

**Extracted data fields:** `name`, `frequency` (daily/weekly), `target_days[]` (for weekly), `forgiveness_window` (default 1)

**Check-in:** insert into `habit_logs` with `status='done'` for today. If a row already exists for today, update it.

**Skip:** insert `habit_logs` row with `status='skipped'`.

**Streak calculation** (recalculate after every log entry):
```
Go backwards from yesterday.
Count consecutive days where log status = 'done' OR 'skipped' within forgiveness window.
First 'missed' day (no log or explicit missed beyond forgiveness window) = streak end.
Update habits.streak_count and habits.longest_streak.
```

**Weekly habits:** only require check-in on `target_days`. A day not in `target_days` does not count as missed.

**Delete habit:** deletes the habit and all its logs (CASCADE).

### 10.3 Projects (`modules/projects.py`)

**Extracted data fields:** `name`, `description`, `status`

**Status transitions:** active ↔ paused → done → archived. Archived projects are excluded from default list queries (add `WHERE status != 'archived'`).

**Show project detail:** include linked tasks (grouped: pending / done), linked notes count, linked events.

**Delete project:** requires confirmation. On delete, set `project_id = NULL` on all linked tasks, notes, events. Never cascade-delete linked items.

**Milestone tracking:** stored as notes of `type='note'` linked to the project with tag `['milestone']`. No separate milestones table needed.

### 10.4 Notes & Journal (`modules/notes.py`)

**Extracted data fields:** `content`, `type` (note/journal), `tags[]`, `mood`, `is_pinned`, `project_id`

**Auto-tagging:** after saving a note, call Gemini with a short prompt: `"Extract 1-3 relevant tags from this note as a JSON array of lowercase strings: {content}"`. Save returned tags. Do this asynchronously after the reply is sent — do not block the user's response.

**Search:** use PostgreSQL full-text search on the `idx_notes_search` GIN index. Also filter by tags array if tags mentioned.

**Pin/unpin:** toggle `is_pinned`. Pinned notes always appear first in list queries.

**Convert to task:** create a task with the note's content as the title. Keep the original note — do not delete it.

**Journal entries:** `type='journal'`. Created by the EOD reflection flow or when user explicitly says "journal" / "write in my journal". Mood field only set on journal entries.

**List display:** pinned first, then sorted by `created_at DESC`.

### 10.5 Finance (`modules/finance.py`)

**Extracted data fields:** `type` (income/expense), `amount` (numeric), `currency` (default RON), `category`, `description`, `tx_date` (default today)

**Standard expense categories:** `food & drink`, `transport`, `housing`, `health`, `entertainment`, `shopping`, `work`, `education`, `savings`, `other`. Gemini should classify into these. User can override.

**Monthly overview:** total income, total expenses, net (income - expenses), per-category breakdown with % of total expenses.

**Budget limit warning:** after logging an expense, check if the category's total this month exceeds `budget_limits.monthly_limit`. If yes, add a warning line to Lora's reply: `⚠️ You've exceeded your {category} budget for this month.` If over 80% but not exceeded: `💡 You're at 85% of your {category} budget this month.`

**Edit / delete:** allowed. For deletes, always use confirmation.

### 10.6 Events (`modules/events.py`)

**Extracted data fields:** `title`, `description`, `event_date`, `event_time`, `project_id`, `is_recurring`, `recurrence`, `remind_1day`, `remind_1hour`

**Upcoming events query:** `event_date >= today ORDER BY event_date, event_time`.

**Week view:** `event_date BETWEEN today AND today + 7 days`.

**Recurring events:** when an event's date passes, the scheduler creates the next occurrence with the same fields and resets `reminded_1day` and `reminded_1hour` to FALSE.

**Reminders:** handled by the scheduler (see Section 11). The `reminded_1day` / `reminded_1hour` flags prevent duplicate sends.

---

## 11. Scheduler jobs (`scheduler/jobs.py`)

Use `AsyncIOScheduler` from APScheduler. All times stored in UTC internally, displayed in user's timezone.

Register all jobs at startup. Each job is wrapped in try/except — a failing job must not crash the scheduler or the bot.

### Job 1 — Morning briefing

**Schedule:** daily at `MORNING_BRIEFING_TIME` in user's timezone

**Idempotency check:** before sending, check `user_profile.last_briefing_date`. If it equals today, skip. After sending, update `last_briefing_date = today`.

**Message format:**
```
Good morning, {name}! ☀️

📋 *Tasks*
⚠️ Overdue: [task list or "None"]
Today: [task list or "Nothing due today"]

📅 *Events today*
[event list with time, or "No events today"]

✅ *Habit check-in*
[habit name] — [streak info]  [✅ Done] [⏭ Skip]
[habit name] — [streak info]  [✅ Done] [⏭ Skip]

💰 *Finance*
This month: `{spent} RON` spent / `{income} RON` income
[Budget warning lines if any]

Have a great day! 💪
```

### Job 2 — EOD reflection

**Schedule:** daily at `EOD_REFLECTION_TIME` in user's timezone

**Idempotency check:** `last_eod_date`.

**Message format:**
```
Hey {name}, end of day 🌙

How did today go?
[😊 Great] [🙂 Good] [😐 Okay] [😔 Tough]

Or just tell me what's on your mind.
```

When user taps a mood button:
1. Create a journal entry with `type='journal'`, `mood={selected}`, `content="EOD reflection — {day}"`.
2. Reply: "Got it. Anything you want to note about today, or shall I see you tomorrow?"
3. If user replies with text, append it to the journal entry content.

When user replies with free text (no button):
1. Pass to Gemini with context: "User is responding to EOD reflection. Extract mood if present, create journal entry, check if any tasks are mentioned as completed."
2. Act on extracted intents (mark tasks done, create journal entry).

### Job 3 — Weekly review

**Schedule:** every Sunday at `EOD_REFLECTION_TIME` in user's timezone

**Idempotency check:** `last_weekly_date`.

**Content** (all calculated for the past 7 days):
- Habits: X of Y completed, best streak
- Tasks: X completed, X pending, X overdue
- Finance: total spent, top spending category
- Projects: any that changed status
- One closing line generated by Gemini: `"Write one warm, encouraging sentence for a weekly review. User completed {X} tasks and maintained {Y} habits this week."`

### Job 4 — Event reminders

**Schedule:** every 15 minutes

For each event where:
- `event_date + event_time - NOW() <= 24 hours` AND `remind_1day=TRUE` AND `reminded_1day=FALSE`
  → send "📅 Reminder: *{title}* is tomorrow at {time}." → set `reminded_1day=TRUE`

- `event_date + event_time - NOW() <= 1 hour` AND `remind_1hour=TRUE` AND `reminded_1hour=FALSE`
  → send "⏰ *{title}* starts in less than an hour!" → set `reminded_1hour=TRUE`

Events with no `event_time` use midnight for comparison (treat as all-day).

### Job 5 — Missed habit nudge

**Schedule:** daily, 1 hour after morning briefing time

For each active daily habit with no `habit_logs` entry for yesterday:
- Insert a `missed` log entry for yesterday.
- Recalculate streak (will reset if beyond forgiveness window).

Do not send a Telegram message for this — just update the data silently. The morning briefing already shows unchecked habits.

---

## 12. Telegram bot (`bot/`)

### Security (`bot/handler.py`)

```python
async def security_check(update: Update) -> bool:
    if update.effective_user.id != config.TELEGRAM_USER_ID:
        return False  # silent ignore — no reply, no log
    return True
```

Apply to ALL handlers before any other logic.

### Inline keyboards (`bot/keyboards.py`)

Callback data format: `{module}:{action}:{item_id}` — always parse with `data.split(":")`.

```python
def task_keyboard(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Done",   callback_data=f"tasks:complete:{task_id}"),
        InlineKeyboardButton("✏️ Edit",  callback_data=f"tasks:edit:{task_id}"),
        InlineKeyboardButton("🗑 Delete", callback_data=f"tasks:delete:{task_id}"),
    ]])

def habit_checkin_keyboard(habit_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Done", callback_data=f"habits:done:{habit_id}"),
        InlineKeyboardButton("⏭ Skip", callback_data=f"habits:skip:{habit_id}"),
    ]])

def confirmation_keyboard(module: str, action: str, item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Yes, delete", callback_data=f"{module}:{action}_confirmed:{item_id}"),
        InlineKeyboardButton("Cancel",      callback_data=f"{module}:cancel:{item_id}"),
    ]])

def mood_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("😊 Great", callback_data="mood:great"),
        InlineKeyboardButton("🙂 Good",  callback_data="mood:good"),
        InlineKeyboardButton("😐 Okay",  callback_data="mood:okay"),
        InlineKeyboardButton("😔 Tough", callback_data="mood:bad"),
    ]])
```

### Callback handler

```python
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # ALWAYS call this first — removes loading spinner

    if not await security_check(update):
        return

    parts = query.data.split(":")
    module, action, item_id = parts[0], parts[1], parts[2] if len(parts) > 2 else None

    # Route to correct module handler
    # Edit the original message — do not send a new one
    await query.edit_message_text(reply_text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=new_keyboard)
```

### Message formatting (`bot/formatter.py`)

MarkdownV2 requires escaping these characters: `_ * [ ] ( ) ~ ` > # + - = | { } . !`

```python
ESCAPE_CHARS = r'\_*[]()~`>#+-=|{}.!'

def escape_md(text: str) -> str:
    return re.sub(f'([{re.escape(ESCAPE_CHARS)}])', r'\\\1', str(text))
```

**Always pass dynamic content through `escape_md()` before inserting into MarkdownV2 strings.**

Max message length: 4096 characters. If a reply exceeds this, split at the nearest newline before the limit and send as multiple messages.

---

## 13. Database connection (`db/connection.py`)

```python
import asyncpg
from core.config import DATABASE_URL

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=30,
            server_settings={"application_name": "lora"}
        )
    return _pool

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
```

Neon serverless connections can go cold. Use `command_timeout=30` and handle `asyncpg.TooManyConnectionsError` by waiting briefly and retrying once.

---

## 14. Error handling — complete rules

| Scenario | Behaviour |
|---|---|
| Gemini API call fails | Retry once after 2s. If still failing, send user: "I'm having a moment — try again shortly 🤔" |
| Gemini returns invalid JSON | Retry once with explicit JSON instruction appended. If fails again, send a plain conversational reply without DB action. |
| DB query fails | Log error to stdout with full traceback. Send user: "Something went wrong saving that — try again?" Never expose raw error. |
| Scheduler job fails | Log error to stdout. Do not crash scheduler. Do not notify user (silent fail for scheduler). |
| Unknown callback data | Log and ignore. Call `query.answer()` to clear spinner. |
| Message too long (>4096 chars) | Split and send as multiple messages. |
| User sends a photo/file/voice | Reply: "I can only read text for now — what would you like to do?" |

---

## 15. Railway deployment

### `railway.json`
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python main.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 5
  }
}
```

### `requirements.txt`
```
python-telegram-bot==20.7
google-generativeai
asyncpg
apscheduler==3.10.4
httpx
python-dotenv
pytz
ruff
```

### `.gitignore`
```
.env
__pycache__/
*.pyc
*.pyo
.ruff_cache/
```

### Deployment steps
1. Push repo to GitHub (`.env` must be gitignored)
2. Create Railway project → connect GitHub repo
3. Add all env vars in Railway dashboard (use `.env.example` as reference)
4. Run `db/schema.sql` against Neon once via Neon SQL console or `psql $DATABASE_URL -f db/schema.sql`
5. Trigger first deploy
6. Watch Railway logs — should see "Lora is running 🤖"
7. Open Telegram, message the bot — onboarding flow should start

---

## 16. Implementation order

Build in this exact order. Complete and test each phase before moving to the next.

```
Phase 1 — Foundation
  ✦ .env + .env.example
  ✦ core/config.py          — env loading + validation
  ✦ db/schema.sql           — run against Neon
  ✦ db/connection.py        — asyncpg pool
  ✦ main.py skeleton        — starts, connects to DB, prints "Lora is running"

Phase 2 — Bot skeleton
  ✦ bot/handler.py          — security check + basic message echo
  ✦ bot/onboarding.py       — full onboarding flow
  ✦ bot/formatter.py        — escape_md + basic formatting helpers
  ✦ db/queries/profile.py   — get/create/update user_profile
  TEST: Send first message → onboarding runs → name + timezone saved

Phase 3 — Core engine
  ✦ core/gemini.py          — Gemini client + system prompt + call + parse
  ✦ core/context.py         — context snapshot builder (can return placeholder data initially)
  ✦ core/router.py          — parse IntentResponse, route to module or reply directly
  ✦ core/state.py           — state machine (get/set/clear)
  TEST: Send "hello" → Gemini replies in Lora's voice

Phase 4 — First module (prove full loop)
  ✦ db/queries/tasks.py
  ✦ modules/tasks.py
  ✦ bot/keyboards.py        — task_keyboard + confirmation_keyboard
  TEST: "add task buy milk" → saved to DB → reply with inline buttons
  TEST: Tap ✅ Done → marked complete
  TEST: "delete task buy milk" → confirmation → tap Yes → deleted

Phase 5 — Remaining modules
  ✦ habits + habit_logs (+ habit_checkin_keyboard)
  ✦ projects
  ✦ notes (+ auto-tagging)
  ✦ finance (+ budget limit check)
  ✦ events
  TEST each module: add → list → edit → delete

Phase 6 — Scheduler
  ✦ scheduler/jobs.py
  ✦ Morning briefing (test by temporarily setting time to +2 minutes)
  ✦ EOD reflection + mood keyboard
  ✦ Weekly review
  ✦ Event reminders
  ✦ Missed habit nudge

Phase 7 — Full context
  ✦ core/context.py complete implementation (all 6 modules)
  ✦ Verify Gemini uses context in replies ("you have 3 tasks due today")

Phase 8 — Polish + edge cases
  ✦ Message splitting for long replies
  ✦ Non-text message handling (photo, voice, sticker)
  ✦ State machine edge cases (unrelated message abandons state)
  ✦ Recurring tasks + recurring events auto-creation
  ✦ Streak recalculation after missed habit log
  ✦ Full error handling on all external calls

Phase 9 — Deploy
  ✦ railway.json
  ✦ Deploy to Railway
  ✦ Smoke test every module in production
  ✦ Let morning briefing run for 2 days to verify idempotency
```

---

## 17. Definition of done

The app is complete when all of the following are true:

**Core**
- [ ] Onboarding runs on first message, saves name + timezone
- [ ] Non-whitelisted users are silently ignored
- [ ] All messages and replies are saved to `conversations`
- [ ] Gemini always returns valid JSON; fallback handles failures gracefully

**Modules — each of the 6 must pass:**
- [ ] Add item via natural language
- [ ] List items (correct sort order)
- [ ] Edit item (single-field and multi-field)
- [ ] Rename item
- [ ] Delete item (confirmation required)
- [ ] Complete item (where applicable)
- [ ] Inline buttons work for all actions

**Scheduler**
- [ ] Morning briefing sends once per day at configured time
- [ ] EOD reflection sends once per day at configured time
- [ ] Weekly review sends once per week on Sunday
- [ ] Event reminders fire at 1 day and 1 hour before (no duplicates)
- [ ] Missed habit logs inserted silently

**State machine**
- [ ] Delete confirmation flow works via message and via button
- [ ] Edit field flow works: "edit task X" → Lora asks what to change → change applied
- [ ] Unrelated message correctly abandons pending state

**Finance**
- [ ] Budget limit warning appears when category > 80% of limit
- [ ] Budget exceeded warning appears when over limit

**Deployment**
- [ ] App runs 24/7 on Railway without manual restarts
- [ ] All env vars in Railway dashboard, none hardcoded
- [ ] Schema applied to Neon, all tables exist
- [ ] Logs visible in Railway dashboard

---

*End of brief. Build Lora.*

# LORA_CONTEXT.md — Complete Project Reference

> This document provides comprehensive information about the Lora project for any AI chatbot or agent to understand how the system works.

---

## What is Lora?

**Lora** is a personal Telegram bot that acts as a "second brain" for a single user. It integrates with the **Business Council** multi-agent system to provide:

- Task and project management
- Skills and habits tracking
- Finance and budgeting
- University schedule management
- Health and nutrition logging
- Workout tracking
- Daily briefings and EOD reflections
- Council integration for strategic context

---

## Architecture Overview

```
User Message → Telegram → bot/handler.py
                           ↓
                    core/gemini.py (LLM)
                           ↓
                    core/router.py (Intent routing)
                           ↓
                    modules/{module}.py (Business logic)
                           ↓
                    db/queries/{module}.py (SQL)
                           ↓
                    PostgreSQL (Neon)
```

---

## Core Components

### 1. Message Flow (`bot/handler.py`)
- Receives all Telegram updates (messages, callbacks, voice)
- Security check: validates `TELEGRAM_USER_ID`
- Routes to appropriate handlers or Gemini

### 2. LLM Integration (`core/gemini.py`)
- Uses `google-genai` SDK with `gemini-2.5-flash`
- System prompt defines personality and capabilities
- Returns `IntentResponse` JSON with: intent, module, data, reply, needs_confirmation
- Supports voice/ST transcription

### 3. Intent Routing (`core/router.py`)
- Maps Gemini intents to module handlers
- Modules: tasks, projects, notes, finance, events, shopping, goals, skills, mood, health, workout, focus, planner, university, nutrition, schedule, memory, weather, news

### 4. Modules (`modules/`)
Each module handles a specific domain:

| Module | Purpose | Key Intents |
|-------|---------|------------|
| `tasks.py` | Task management | add_task, list_tasks, complete_task, edit_task |
| `projects.py` | Project organization | add_project, list_projects, view_project, update_progress |
| `finance.py` | Expense/income tracking | finance_log, finance_summary, list_categories, add_category |
| `skills.py` | Skill/habit tracking | log_skill, view_skills, add_habit |
| `university.py` | Academic management | uni_add_subject, uni_log_attendance, uni_add_grade |
| `health.py` | Health logging | health_log, log_water, health_summary |
| `workout.py` | Workout logging | workout_log, workout_list, workout_stats |
| `goals.py` | Goal tracking | add_goal, update_goal, view_goals |

### 5. Database (`db/`)
- Raw SQL via `asyncpg` (no ORM)
- Schema in `db/schema.sql`
- Queries in `db/queries/{module}.py`

### 6. Scheduler (`scheduler/jobs.py`)
- Morning briefing (08:00 default)
- EOD reflection (21:00 default)
- Daily report to Council
- Journal night prompts

---

## Council Integration

### What is the Council?

The **Business Council** is a multi-agent system of 5 Telegram bots (CEO, CFO, CTO, CMO, COO) that run in a Telegram group chat and share a PostgreSQL database.

### Configuration
```
COUNCIL_API_URL=https://business-council.onrender.com
COUNCIL_API_SECRET=<secret>
COUNCIL_GROUP_CHAT_ID=-100xxxxx
CTO_BOT_USERNAME=@cto_bot
```

### Council API Functions (`core/council.py`)

| Function | Endpoint | Purpose |
|----------|----------|---------|
| `get_projects()` | `GET /projects` | Fetch strategic projects |
| `get_summary()` | `GET /summary/me` | Fetch executive summary |
| `get_decisions(id)` | `GET /decisions/{id}` | Fetch decisions for project |
| `send_feedback_to_cto()` | `POST /feedback` | Send task difficulty to CTO |
| `send_report_to_council()` | `POST /report/{id}` | Send daily completed tasks |

### Council-Powered Features

1. **Task Linking**
   - When completing a task, Lora fetches linked Council decisions
   - Shows: "Aligned with Council decision: [Decision Title]"

2. **Executive Summary**
   - Morning briefing includes `🏛️ Consiliu — Strategic` section
   - Fetches from `/summary/me` endpoint

3. **Feedback Loop**
   - After completing task: asks "How hard was this? (1-10)"
   - Sends feedback to CTO via `/feedback` API

4. **Daily Report**
   - At EOD time, collects completed tasks
   - Sends to Council via `POST /report/{id}`
   - Optionally posts `[REPORT]` to Council group chat

5. **Bot-to-User Translation**
   - `core/translator.py` translates Council jargon to plain Romanian
   - Terms: burn rate, LTV, CAC, MRR, runway, tech debt, etc.

---

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point, bot setup, scheduler |
| `bot/handler.py` | Message routing, security, commands |
| `core/gemini.py` | LLM calls, system prompt, IntentResponse |
| `core/router.py` | Intent → module routing |
| `core/council.py` | Council API integration |
| `core/context.py` | build_context() for prompts |
| `core/state.py` | Conversation state machine |
| `modules/*.py` | Domain logic (tasks, finance, etc.) |
| `db/queries/*.py` | SQL queries per module |
| `scheduler/jobs.py` | Scheduled jobs |
| `bot/formatter.py` | MarkdownV2 utilities |

---

## Environment Variables

### Required
```
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_USER_ID=<id>
GEMINI_API_KEY=<key>
DATABASE_URL=postgresql://...
TIMEZONE=Europe/Bucharest
MORNING_BRIEFING_TIME=08:00
EOD_REFLECTION_TIME=21:00
LORA_API_SECRET=<secret>
```

### Council (Optional)
```
COUNCIL_API_URL=https://business-council.onrender.com
COUNCIL_API_SECRET=<secret>
COUNCIL_GROUP_CHAT_ID=-100xxxxx
CTO_BOT_USERNAME=@cto_bot
```

---

## Database Schema

Key tables:
- `user_profile` - User settings, timezone, tone
- `tasks` - Task management with project links
- `projects` - Projects with metadata (deadline, priority, category, progress)
- `finances` - Expense/income tracking
- `finance_categories` - Custom expense categories
- `skills` - Skill/habit tracking
- `goals` - Hierarchical goals with sub-tasks
- `workouts` - Exercise logs
- `subjects` - University subjects
- `schedule` - University timetable
- `health_logs` - Health metrics
- `memory_facts` - Long-term memory

---

## Running the Project

```bash
# Install
pip install -r requirements.txt

# Database init
psql $DATABASE_URL -f db/schema.sql
psql $DATABASE_URL -f db/migrations/001_schema_fixes.sql
psql $DATABASE_URL -f db/migrations/003_projects_enhanced.sql
psql $DATABASE_URL -f db/migrations/004_finance_categories.sql

# Run
python main.py

# Lint (required before commit)
ruff check .
ruff format .
```

---

## Language Convention

- **Romglish**: Romanian base, English tech terms
- User errors in Romanian: "A apărut o eroare"
- System comments in English
- Avoid filler phrases
# Lora Project Context

Lora is a private, intelligent Telegram bot that acts as a personal "second brain" for a single user. It is built using Python and leverages the Gemini 2.0 Flash model (via `google-genai` SDK) for natural language understanding and task management.

## Project Overview

- **Purpose:** A personal assistant to manage tasks, habits, projects, notes, finances, shopping lists, university schedules, workouts, goals, and health metrics.
- **Key Features:** Persistent memory, multi-module support, proactive scheduled interactions (morning briefings, EOD reflections, habit nudges), voice interface (TTS & STT), and a custom conversation state machine.
- **Architecture:** Modular Python application with a PostgreSQL database (Neon) and Telegram interface.
- **Security:** Single-user whitelist based on Telegram User ID. No multi-tenancy or public registration.

## Tech Stack

- **Language:** Python 3.11+ (Type hints required)
- **Telegram Framework:** `python-telegram-bot==22.6` (Async, Long Polling)
- **LLM:** `google-genai` (Gemini 2.0 Flash) — **SDK: `from google import genai`**
- **Database:** Neon (Serverless PostgreSQL)
- **Database Driver:** `asyncpg` (Raw SQL, no ORM)
- **Scheduler:** `apscheduler==3.10.4` (AsyncIOScheduler)
- **TTS/Voice:** `edge-tts` for podcast generation, Telegram voice for interactions.
- **Hosting:** Railway
- **Linting/Formatting:** `ruff`

## Directory Structure

```text
lora/
├── main.py                  # Entry point (ApplicationBuilder + Polling)
├── bot/                     # Telegram bot logic
│   ├── handler.py           # ★ Main router (Message, Callback, Voice)
│   ├── keyboards.py         # Custom Inline/Reply keyboards
│   ├── formatter.py         # MarkdownV2 utility (escape_md, safe_markdown)
│   ├── onboarding.py        # First-run setup wizard
│   ├── tts.py               # Edge-TTS integration
│   └── voice.py             # STT via OpenAI Whisper or Telegram voice
├── core/                    # Core logic
│   ├── gemini.py            # ★ Gemini integration (Prompt, Schema, Proactive)
│   ├── config.py            # Environment configuration & validation
│   ├── router.py            # Maps IntentResponse → Module logic
│   ├── context.py           # Builds the dynamic prompt context from DB
│   └── state.py             # Conversation state machine
├── modules/                 # Functional logic (returns text + keyboard)
│   ├── tasks.py             # Task management (Priority, Recurrence)
│   ├── habits.py            # Habit tracking (Streaks, Reminders)
│   ├── projects.py          # Project organization (Statuses)
│   ├── finance.py           # Expense/Income tracking & Reports
│   ├── notes.py             # Notes, Search, and Journaling
│   ├── events.py            # Calendar & Appointments
│   ├── shopping.py          # Groceries & Shopping lists
│   ├── university.py        # ★ Schedule, Attendance, Exams, Week Parity
│   ├── workout.py           # ★ Sports CRUD, Exercises, PRs, Calories
│   ├── goals.py             # ★ Main Goals, Categories, Sub-tasks, Progress
│   ├── health.py            # Sleep, Water, Weight tracking
│   ├── nutrition.py         # Calorie & Macro tracking
│   ├── focus.py             # Productivity timer (Focus mode)
│   ├── mood.py              # Mood tracking & Analysis
│   ├── insights.py          # AI-driven pattern recognition
│   ├── weather.py           # OpenWeather integration
│   ├── news.py              # RSS Tech & Local news
│   └── skills.py            # ★ Skill tracking with custom metrics
├── scheduler/               # Cron jobs
│   └── jobs.py              # Briefings, Reflections, Nudges, Reminders
└── db/                      # Database layer
    ├── connection.py        # pool.acquire() management
    ├── schema.sql           # Database schema (Source of Truth)
    └── queries/             # SQL per module (Raw SQL, no ORM)
```

## Feature Deep-Dive (Technical)

### 1. Goals Dashboard (`modules/goals.py`)
- **Logic**: Hierarchical goals with sub-tasks. Progress is auto-recalculated on task completion.
- **DB**: `goals`, `goal_tasks`.
- **Intents**: `add_goal`, `add_subtask`, `complete_subtask`, `view_goals`.

### 2. Workout (`modules/workout.py`)
- **Logic**: Sports dictionary (`sport_types`) + Exercises (`exercises`) + Logs (`workouts`). Supports PRs.
- **DB**: `sport_types`, `exercises`, `workouts`.
- **Intents**: `workout_log` (NLP enabled), `view_prs`, `add_sport`.

### 3. University (`modules/university.py`)
- **Logic**: Week parity (impară/pară) calculation from `semester_start`. Automatic attendance logging.
- **DB**: `subjects`, `university_schedule`, `attendance`, `exams`.
- **Intents**: `list_schedule`, `log_attendance`, `add_exam`.

### 4. Scheduler (`scheduler/jobs.py`)
- **Logic**: Proactive "Morning Briefing" (08:00) and "EOD Reflection" (21:00). Synthetic podcast generation (Voice).
- **Idempotency**: Checked via `last_briefing_date` in `user_profile`.

### 5. Skills Tracking (`modules/skills.py`)
- **Logic**: Track custom skills (chess, language, gym) with custom units (elo, min, reps).
- **DB**: `skills`, `skill_logs`.
- **Intents**: `log_skill` (NLP enabled), `view_skills`.

## Building and Running

1. **Install**: `pip install -r requirements.txt`
2. **Env**: Set `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `TELEGRAM_USER_ID`.
3. **DB Init**: `psql $DATABASE_URL -f db/schema.sql`
4. **Run**: `python main.py`

## Development Conventions

- **Type Safety**: Use type hints for ALL function signatures.
- **Raw SQL**: Use `asyncpg`. Use `$1, $2` placeholders. NICIODATĂ string interpolation.
- **Formatting**: ALWAYS use `bot/formatter.py` (`escape_md`) for MarkdownV2.
- **Response Format**: Gemini MUST return `IntentResponse` JSON schema defined in `core/gemini.py`.
- **State**: Clear state after every multi-step interaction via `clear_state(pool)`.

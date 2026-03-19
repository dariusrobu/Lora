# Lora Project Context

Lora is a private, intelligent Telegram bot that acts as a personal "second brain" for a single user. It is built using Python and leverages the Gemini 1.5 Flash model for natural language understanding and task management.

## Project Overview

- **Purpose:** A personal assistant to manage tasks, habits, projects, notes, finances, shopping lists, and events.
- **Key Features:** Persistent memory, multi-module support, proactive scheduled interactions (morning briefings, EOD reflections, habit nudges), voice interface (TTS & STT), and a custom conversation state machine.
- **Architecture:** Modular Python application with a PostgreSQL database (Neon) and Telegram interface.
- **Security:** Single-user whitelist based on Telegram User ID. No multi-tenancy or public registration.

## Tech Stack

- **Language:** Python 3.11+ (Type hints required)
- **Telegram Framework:** `python-telegram-bot==20.7` (Async, Long Polling)
- **LLM:** `google-generativeai` (Gemini 1.5 Flash)
- **Database:** Neon (Serverless PostgreSQL)
- **Database Driver:** `asyncpg` (Raw SQL, no ORM)
- **Scheduler:** `apscheduler==3.10.4` (AsyncIOScheduler)
- **TTS/Voice:** `edge-tts` for podcast generation, Telegram voice for interactions.
- **Hosting:** Railway
- **Linting/Formatting:** `ruff`

## Directory Structure

```text
lora/
├── main.py                  # Entry point
├── bot/                     # Telegram bot logic
│   ├── handler.py           # Message and command routing
│   ├── keyboards.py         # Custom Inline/Reply keyboards
│   ├── formatter.py         # Telegram MarkdownV2 utility
│   ├── tts.py               # Edge-TTS integration
│   └── voice.py             # Voice message handling
├── core/                    # Core logic
│   ├── gemini.py            # Gemini integration
│   ├── config.py            # Environment configuration
│   └── state.py             # Conversation state management
├── modules/                 # Functional modules
│   ├── tasks.py             # Task management
│   ├── habits.py            # Habit tracking
│   ├── projects.py          # Project organization
│   ├── finance.py           # Expense/Income tracking
│   ├── notes.py             # Notes and journaling
│   ├── events.py            # Event/Calendar logic
│   ├── shopping.py          # Shopping lists
│   ├── weather.py           # Weather integration
│   └── news.py              # Tech & Local news
├── scheduler/               # Scheduled jobs (briefings, reflections, nudges)
└── db/                      # Database layer
    ├── connection.py        # Connection pooling
    ├── schema.sql           # Database schema
    └── queries/             # SQL query logic per module
```

## Building and Running

### Prerequisites

1.  **Python 3.11+** installed.
2.  **PostgreSQL (Neon)** database instance.
3.  **Telegram Bot Token** from @BotFather.
4.  **Google AI Studio API Key** for Gemini.
5.  **Weather API Key** (if applicable).

### Setup

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configure environment variables:**
    Create a `.env` file in the root directory.
    ```env
    TELEGRAM_BOT_TOKEN=
    TELEGRAM_USER_ID=
    GEMINI_API_KEY=
    DATABASE_URL=
    TIMEZONE=Europe/Bucharest
    MORNING_BRIEFING_TIME=08:00
    EOD_REFLECTION_TIME=21:00
    HABIT_REMINDER_TIME=18:00
    WEEKLY_REVIEW_DAY=sunday
    OPENWEATHER_API_KEY=
    ```
3.  **Initialize Database:**
    Run the schema script:
    ```bash
    psql $DATABASE_URL -f db/schema.sql
    ```

### Running the App

```bash
python main.py
```

### Testing

- Linting: `ruff check .`
- Manual verification via Telegram is the primary testing method.

## Development Conventions

- **Type Safety:** Use type hints for all function signatures and variables.
- **Database:** Use raw SQL with `asyncpg`. Do not use an ORM.
- **Code Style:** Adhere to `ruff` linting and formatting rules.
- **State Management:** Multi-turn interactions use `conversation_state` table.
- **Response Format:** Gemini responses must match the `IntentResponse` JSON schema.
- **Formatting:** Use `bot/formatter.py` to ensure proper MarkdownV2 escaping.
- **Proactive Logic:** Scheduled jobs handle idempotency (checking `last_briefing_date`, etc.).
- **Voice:** TTS generation for briefings should be cleaned of markdown markers before being sent to `edge-tts`.

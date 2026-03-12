# Lora Project Context

Lora is a private, intelligent Telegram bot that acts as a personal "second brain" for a single user. It is built using Python and leverages the Gemini 1.5 Flash model for natural language understanding and task management.

## Project Overview

- **Purpose:** A personal assistant to manage tasks, habits, projects, notes, finances, and events.
- **Key Features:** Persistent memory, multi-module support, proactive scheduled interactions (morning briefings, EOD reflections), and a custom conversation state machine.
- **Architecture:** Modular Python application with a PostgreSQL database (Neon) and Telegram interface.
- **Security:** Single-user whitelist based on Telegram User ID. No multi-tenancy or public registration.

## Tech Stack

- **Language:** Python 3.11+ (Type hints required)
- **Telegram Framework:** `python-telegram-bot==20.7` (Async, Long Polling)
- **LLM:** `google-generativeai` (Gemini 1.5 Flash)
- **Database:** Neon (Serverless PostgreSQL)
- **Database Driver:** `asyncpg` (Raw SQL, no ORM)
- **Scheduler:** `apscheduler==3.10.4` (AsyncIOScheduler)
- **Hosting:** Railway
- **Linting/Formatting:** `ruff`

## Directory Structure

```text
lora/
├── main.py                  # Entry point
├── bot/                     # Telegram bot logic (handlers, keyboards, formatting)
├── core/                    # Core logic (Gemini integration, context building, routing, state management)
├── modules/                 # Functional modules (tasks, habits, projects, notes, finance, events)
├── scheduler/               # Scheduled jobs (briefings, reminders)
└── db/                      # Database connection and SQL queries
```

## Building and Running

### Prerequisites

1.  **Python 3.11+** installed.
2.  **PostgreSQL (Neon)** database instance.
3.  **Telegram Bot Token** from @BotFather.
4.  **Google AI Studio API Key** for Gemini.

### Setup

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configure environment variables:**
    Create a `.env` file in the root directory (refer to `.env.example`).
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
3.  **Initialize Database:**
    Run the schema script against your PostgreSQL instance:
    ```bash
    psql $DATABASE_URL -f db/schema.sql
    ```

### Running the App

```bash
python main.py
```

### Testing

- No specific test framework is mentioned in the brief, but `ruff` is used for linting.
- Manual verification via Telegram is the primary testing method described.

## Development Conventions

- **Type Safety:** Use type hints for all function signatures and variables.
- **Database:** Use raw SQL with `asyncpg`. Do not use an ORM.
- **Code Style:** Adhere to `ruff` linting and formatting rules.
- **State Management:** All multi-turn interactions must be managed through the `conversation_state` table and `core/state.py`.
- **Response Format:** Gemini must always respond with valid JSON matching the `IntentResponse` schema.
- **Formatting:** Use Telegram MarkdownV2 for all bot replies, ensuring proper character escaping via `bot/formatter.py`.
- **Proactive Logic:** Scheduled jobs in `scheduler/jobs.py` must handle idempotency (e.g., checking `last_briefing_date`) to prevent duplicate messages.

# PA_BOT_OVERVIEW.md

## Project: Lora (Personal AI Assistant Bot)

Lora is a "second brain" Telegram bot designed for single-user productivity. It uses a hybrid architecture combining a standard command/handler Telegram bot with a powerful LLM-driven intent routing system.

---

## 1. Tech Stack & Dependencies

*   **Language:** Python 3.11+
*   **Bot Framework:** `python-telegram-bot` (Async, Long Polling)
*   **LLM Engine:** `google-genai` (Gemini 2.0/2.5 Flash)
*   **Database:** PostgreSQL (Neon) with `asyncpg` (Raw SQL, no ORM)
*   **Scheduler:** `apscheduler` (AsyncIOScheduler)
*   **Web Server:** `aiohttp` (Background server for health checks and WebCal `.ics` serving)
*   **Voice/Vision:** `edge-tts` (Podcast generation), Gemini Multimodal (STT and Image analysis)
*   **Data Analysis:** `matplotlib`, `numpy` (Insights and charts)

---

## 2. Project Structure

```text
lora/
├── main.py                  # Entry point: initializes DB, Bot, Scheduler, and Web Server
├── bot/                     # Telegram-specific logic
│   ├── handler.py           # Core Router: Message, Voice, Photo, and Command handlers
│   ├── formatter.py         # MarkdownV2 escaping and formatting utilities
│   ├── onboarding.py        # First-run setup wizard
│   ├── tts.py               # Edge-TTS integration for voice briefings
│   └── voice.py             # Voice transcription using Gemini Multimodal
├── core/                    # Intelligence & Configuration
│   ├── gemini.py            # AI logic: Prompt engineering, Intent extraction, Proactive responses
│   ├── router.py            # Maps AI-extracted Intents -> Functional Modules
│   ├── context.py           # Builds dynamic "Context Snapshot" from DB for every AI turn
│   ├── memory.py            # Long-term fact extraction and retrieval
│   ├── agent.py             # "Agentic Mode" for complex multi-tool reasoning
│   ├── vision.py            # Image analysis logic
│   └── config.py            # Environment variable validation
├── modules/                 # Functional Domains (Logic + UI components)
│   ├── tasks.py, finance.py, goals.py, health.py, university.py, etc.
├── db/                      # Persistence Layer
│   ├── connection.py        # Database pool management
│   ├── schema.sql           # Source of truth for DB structure (15+ tables)
│   └── queries/             # Modular SQL queries (Raw asyncpg)
└── scheduler/               # Automated Jobs
    └── jobs.py              # Morning briefings, EOD reflections, and reminders
```

---

## 3. Initialization & Bot Lifecycle

1.  **DB Pool:** `main.py` creates a global `asyncpg` pool.
2.  **Profiles:** Ensures a `user_profile` exists for the whitelisted `TELEGRAM_USER_ID`.
3.  **Scheduler:** Starts `apscheduler` for proactive jobs (08:00 Briefing, 21:00 Reflection).
4.  **Web Server:** Starts `aiohttp` on port 8080.
    *   `/`: Health check.
    *   `/calendar/{token}`: Serves a dynamically generated `.ics` file for WebCal.
5.  **Bot Handlers:** Registers commands and a catch-all `message_handler`.
6.  **Polling:** Runs in Long Polling mode (Note: Multi-instance execution is forbidden to avoid polling conflicts).

---

## 4. Message Processing Flow

The core of Lora is the **Research -> Context -> Intent -> Action** cycle:

1.  **Receive:** `message_handler` receives text, voice (transcribed), or photo.
2.  **Context Building (`core/context.py`):** Queries the DB to create a text-based "snapshot" of the user's life (pending tasks, budget status, events today, recent notes, etc.).
3.  **AI Analysis (`core/gemini.py`):** Sends the message + Context + History to Gemini.
4.  **Intent Extraction:** Gemini returns a structured **JSON (IntentResponse)**:
    ```json
    {
      "intent": "add_task",
      "module": "tasks",
      "data": {"title": "Buy milk", "priority": "high"},
      "reply": "Task adăugat ✅ *Buy milk*",
      "needs_confirmation": false
    }
    ```
5.  **Routing (`core/router.py`):** The router calls the specific module (e.g., `modules/tasks.py`) to perform the DB operation using the `data` payload.
6.  **Respond:** The `reply` (MarkdownV2) is sent back to the user with any module-generated keyboards.

---

## 5. Data Storage & User Memory

### 5.1 Database (PostgreSQL)
Stored in a serverless Neon DB. Key entities include:
*   `tasks`, `projects`, `goals`: Hierarchical productivity tracking.
*   `finances`, `budget_limits`: Expense tracking and threshold alerts.
*   `health_logs`, `meals`, `workout_exercises`: Wellness tracking.
*   `university_schedule`, `attendance`: Academic management.

### 5.2 Short-Term Context
Managed via the `conversations` table (last N turns) and `conversation_state` (ephemeral flags like `awaiting_confirmation`).

### 5.3 Long-Term Memory (`memory_facts` table)
*   **Extraction:** After every interaction, a background task (`core/memory.py`) analyzes the chat to find permanent facts (e.g., "User lives in Cluj", "Likes spicy food").
*   **Retrieval:** These facts are injected back into the LLM context when relevant keywords match.

---

## 6. Integration Points & APIs

*   **Telegram API:** UI interface.
*   **Gemini API:** Reasoning, STT, Vision, and Fact Extraction.
*   **OpenWeather API:** Real-time weather data for briefings.
*   **Nutritionix API:** (Optional) Food database for calorie estimation.
*   **WebCal (.ics):** Outgoing feed for integration with Apple/Google Calendar.
*   **Agentic Tools:** `core/agent.py` defines a set of `FunctionDeclarations` that Gemini can call to "browse" the database when simple intent routing fails.

---

## 7. Environment Variables (.env)

*   `TELEGRAM_BOT_TOKEN`: Bot father token.
*   `TELEGRAM_USER_ID`: **CRITICAL** - The single authorized user ID (Security whitelist).
*   `GEMINI_API_KEY`: Google AI SDK key.
*   `DATABASE_URL`: Connection string.
*   `TIMEZONE`: Default `Europe/Bucharest`.
*   `MORNING_BRIEFING_TIME`, `EOD_REFLECTION_TIME`: Cron-like triggers.

---

## 8. Extension Guide (For Developers)

To add a new capability:
1.  **DB:** Add a table in `db/schema.sql` and queries in `db/queries/`.
2.  **Module:** Create `modules/new_feature.py` with an `handle_intent` function.
3.  **Intelligence:** Update the `system_prompt` in `core/gemini.py` to describe the new intent and data schema.
4.  **Router:** Register the module in `core/router.py`.
5.  **Context:** Add the new data type to `core/context.py` so Lora "knows" about it during conversations.

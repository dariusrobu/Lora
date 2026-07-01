# AGENTS.md — Lora

> Read before editing. Every claim is verified against the running code.

## Stack

- **Python 3.11+** with type hints
- **LLM**: Ollama `llama3.2:3b` — primary LLM for intent parsing (`get_gemini_response` calls Ollama, not Gemini), proactive messages, voice normalization. Google GenAI (`google-genai` SDK: `from google import genai` / `from google.genai import types`) used for **embeddings** (`text-embedding-004`), **agent mode** (`gemini-2.5-flash` in `core/agent.py`), **vision** (`core/vision.py`), **memory** (`core/memory.py`), **correlations** (`core/correlations.py`), **translations** (`core/translator.py`).
- **Telegram**: `python-telegram-bot==22.6` long polling
- **Database**: Neon PostgreSQL via `asyncpg` — no ORM. Raw SQL with `$1, $2` placeholders, never f-strings.
- **Scheduler**: `apscheduler==3.10.4` (`AsyncIOScheduler`)
- **Hosting**: Railway (`numReplicas: 1`) — Render config deprecated
- **Linting**: `ruff` with defaults (no config file)

## Architecture

`message → bot/handler.py (security check, onboarding, voice STT) → core/gemini.py (Ollama structured JSON) → core/router.py (route + confirmation interception) → core/dispatcher.py (dynamic importlib.import_module) → modules/{module}.py → db/queries/{module}.py`

**Modules return `(str, InlineKeyboardMarkup | None, int | None)`** — never call Telegram directly.

**Dispatcher** imports `modules.{module}` dynamically and calls `handle_{module}_intent(pool, intent, data)` with optional `user_id`/`bot` kwargs via `inspect.signature`.

## Critical gotchas

- **Confirmation is DISABLED** — `router.py:262` has `if False:`. All write intents execute immediately.
- **`get_gemini_response` calls Ollama** (`generate_structured_response` → `_ollama_client.chat`). Legacy name.
- **DDL runs at startup** in `main.py` (creates `saved_locations`, `travel_items`, `ALTER TABLE user_profile` + `health_logs`). `schema.sql` is NOT the full source of truth.
- **`bot/handler.py` monkey-patches** `CallbackQuery.edit_message_text` and `Message.edit_text` to auto-wrap `safe_markdown()`. Send MarkdownV2 text raw; monkey-patch handles escaping.
- **`bot.log` is rotated** (2MB × 3 via `RotatingFileHandler` in `main.py:62-63`).
- **PID lock** (`lora.pid`) prevents multiple instances. 15s startup delay for old polling to clear (`main.py:553-554`).
- **Web server** (aiohttp) runs alongside bot on `PORT` (default `8083`), proxies `/api/*` to FastAPI on `8090`, serves dashboard SPA from `dashboard/dist/`. **All non-API paths** serve `index.html` (React Router SPA fallback, `main.py:482-515`).
- **`/reload`** uses `os.execl()` — hard restart, drops in-flight requests (`handler.py:514-524`).
- **Broken `client` import** — `handler.py`, `router.py`, and `correlations.py:7` import `from core.gemini import client`, but `client` does NOT exist in `core/gemini.py` (it has `_ollama_client` and `_google_genai_client`). The real `client = genai.Client(api_key=GEMINI_API_KEY)` lives in `core/translator.py:11`. Fix: import from `core/translator.py` or add `client` to `core/gemini.py`. `handler.py` uses are in `try` blocks; `router.py:96` and `correlations.py:7` are NOT wrapped — will crash when agent mode triggers or on module import.
- **Group chat @mention-only** — In groups, the bot only responds when explicitly @mentioned (e.g. `@lora_bot ...`). Check `handler.py:448-481`.
- **`requirements.txt` has `google-generativeai`** (old SDK) but code uses `google-genai` (`from google import genai`). If pip installing, use `google-genai`.
- **Cerebras dead code** — `_call_cerebras_with_retry` in `core/gemini.py:334` never called.
- **`DATABASE_URL` auto-fix** — `core/config.py:46-47` silently rewrites `postgres://` to `postgresql://`.

## MarkdownV2 rules

- `escape_md()` → user-supplied strings only
- `safe_markdown()` → LLM-generated text (handles double-escaping)
- **Date strings in JSON `reply` field** must be RAW — never `escape_md()` dates (breaks `2026\-03\-26`)
- `split_message()` → splits at 4000 chars (`bot/formatter.py:49`)

## Env vars

**Required** (validated at startup via `core/config.py`): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`, `GEMINI_API_KEY`, `DATABASE_URL`, `TIMEZONE`, `MORNING_BRIEFING_TIME`, `EOD_REFLECTION_TIME`, `LORA_API_SECRET`

**Optional**: `OPENWEATHER_API_KEY`, `NUTRITIONIX_APP_ID`, `NUTRITIONIX_API_KEY`, `OLLAMA_HOST` (default `http://localhost:11434`), `OLLAMA_MODEL` (default `llama3.2:3b`), `ICLOUD_USERNAME`, `ICLOUD_APP_PASSWORD`, `ICLOUD_CALENDAR_NAME`, `CALENDAR_SYNC_INTERVAL_MINUTES`, `CALENDAR_SECRET`, `HABIT_REMINDER_TIME`, `WEEKLY_REVIEW_DAY`, `SEMESTER_START_DATE`, `JOURNAL_NIGHT_TIME`, `COUNCIL_API_URL`, `COUNCIL_API_SECRET`, `COUNCIL_GROUP_CHAT_ID`, `CTO_BOT_USERNAME`, `LORA_API_PASSWORD`, `JWT_SECRET`, `API_PORT`, `DASHBOARD_URL`, `WEATHER_CITY`

## Commands

```bash
python main.py                # run bot (requires Ollama)
python -m lora_api.main       # API + dashboard standalone (NO LLM) — or ./run_api.sh
pip install -r requirements.txt
ruff check .                  # no config file; uses defaults
```

DB:
```bash
psql $DATABASE_URL -f db/schema.sql                    # base schema (run once)
psql $DATABASE_URL -f db/migrations/NNN_name.sql        # migrations in order
cd dashboard && npx vite build                          # build frontend to dist/
```

## Standalone API (no LLM)

`lora_api/main.py` is fully independent of Telegram bot. Requires only `DATABASE_URL`. Auto-builds dashboard. Run via `./run_api.sh` (port 8090) or `./start_kiosk.sh` (port 8088, background, logs to `api.log`). Both scripts auto-detect `.venv/bin/python`.

**⚠️ API port must match bot web proxy target** — `main.py:404` proxies `/api/*` to port **8090**. If `.env` `API_PORT` differs, kiosk widgets get empty responses (ServerStatus, Health, etc.). Currently set to `8090`.

## Kiosk dashboard

- **Server status**: Uses Tailscale IP `100.81.206.5` (`.env` `SERVER_IP`) for SSH + TCP checks. LAN DHCP changes (currently `192.168.1.17`) don't affect it. Home server has 10 Docker containers, all currently up. CPU at 0% = genuine idle.
- **Health widget**: Fetches `/api/health/summary` + `/api/nutrition/daily` in parallel. Falls back to defaults (sleep 7.5h, water 1800ml) when DB empty.
- **WidgetErrorBoundary**: Auto-resets after 30s for transient errors (e.g. API temporarily down during restart).

## State machine

Single row `conversation_state` with `state_key = 'current'`. When idle, `state_type = NULL`.

**Confirm/action**: `awaiting_confirmation`, `awaiting_action_confirm`, `awaiting_clarification`
**Multi-turn input**: `awaiting_edit_field`, `awaiting_task_input`, `awaiting_project_input`, `awaiting_health_input`, `awaiting_finance_input`, `awaiting_workout_input`, `awaiting_skill_input`, `awaiting_uni_input`
**Module-specific**: `awaiting_focus_result`, `awaiting_profile_hours`, `awaiting_day_plan_input`, `awaiting_evening_response`, `awaiting_event_note`, `awaiting_project_edit`, `awaiting_project_name`, `awaiting_goal_title`, `awaiting_goal_description`, `awaiting_subtask_title`, `awaiting_vision_confirmation`

## Valid modules (router.py whitelist)

`tasks`, `projects`, `notes`, `finance`, `events`, `shopping`, `goals`, `skills`, `mood`, `insights`, `health`, `nutrition`, `workout`, `university`, `schedule`, `reading`, `focus`, `planner`, `memory`, `weather`, `calendar`, `calendar_module`, `integrations`, `travel`, `wishlist`

## Style

- Type hints required: `async def fn(pool, user_id: int) -> Optional[Dict[str, Any]]:`
- DB: `$1, $2` placeholders — never f-strings
- Imports: stdlib → third-party → local absolute
- Errors to user: Romanian ("A apărut o eroare."). System comments: English.
- No filler: never "Sigur!", "Cu plăcere!", "Bineînțeles!"
- Romglish: Romanian base, English tech terms

## Council integration

All automatic Council reporting disabled/isolated. `core/council.py` exists but not invoked by tasks or scheduler.

## Frontend (dashboard/)

- **React 19** + TypeScript 6 + Vite 8 + React Router v7 + TanStack Query v5
- **TailwindCSS 3** + framer-motion + lucide-react + class-variance-authority
- 23 API routers in `lora_api/routers/` — one per module
- Login via JWT, 401 → auto-logout
- **Kiosk** (`/kiosk`): Fullscreen tablet dashboard, 8 LiquidGlassCard widgets with mock fallbacks. `./start_kiosk.sh`
- **TMA**: Dashboard accessible as Telegram Mini App via `DASHBOARD_URL`. Auth via `LORA_API_SECRET`.
- **Lora Space** (`/space`): Admin panel — Profile, LLM toggle (Ollama vs Gemini), Integration test buttons
- **Theme**: Dark/light/auto toggle via `ThemeContext`, persisted to `localStorage` key `lora_theme_mode`. Class-based dark mode.
- **Build**: `cd dashboard && npx vite build` → outputs to `dashboard/dist/`

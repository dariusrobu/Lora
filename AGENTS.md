# AGENTS.md — Lora

> Read before editing. Every claim verified against running code (2026-09-16).

## Stack

- **Python 3.11+**, type hints required everywhere
- **LLM: Ollama only** — `core/gemini.py:16` ("Ollama is Lora's only LLM runtime"). `get_llm_response()` → `generate_structured_response()` (JSON via `format="json"`, default model `OLLAMA_MODEL`); `generate_text_response()` for free text. **`get_gemini_response` is a legacy alias of `get_llm_response`** (test-verified) — it does NOT call Gemini/NVIDIA/Cerebras. `client = None` in `core/gemini.py:21`; `_call_cerebras_with_retry` is dead code.
- **Voice STT**: `bot/voice.py` — Gemini multimodal (`gemini-2.0-flash`) if `GEMINI_API_KEY`, else Groq Whisper (`GROQ_API_KEY`), else OpenAI Whisper (`OPENAI_API_KEY`); then local post-processing via `generate_text_response`.
- **Embeddings**: `core/embeddings.py` — local Ollama, dummy `[0.0]*768` fallback. No Google embeddings.
- **Telegram**: `python-telegram-bot==22.6` long polling (no webhooks)
- **Database**: Neon PostgreSQL via `asyncpg` — raw SQL `$1, $2` placeholders, never f-strings
- **Scheduler**: `apscheduler==3.10.4` (`AsyncIOScheduler`)
- **Hosting**: `railway.json` (numReplicas:1) and `render.yaml` both present
- **Linting/tests**: `ruff check .` (defaults, no config file); pytest via `pytest.ini` (`asyncio_mode = auto`, `testpaths = tests`)

## Architecture

`message → bot/handler.py (security check, onboarding, voice STT) → core/gemini.py (Ollama structured JSON) → core/router.py (route + confirmation gate) → core/dispatcher.py (dynamic importlib) → modules/{module}.py → db/queries/{module}.py`

- Handler Function names follow `handle_{module}_intent(pool, intent, data)`; dispatcher inspects signature for optional `user_id`/`bot` kwargs and always coerces results to the 3-tuple `(text, keyboard|None, item_id|None)` — modules never call Telegram directly.
- Dispatcher maps module `calendar` → file `modules/calendar_module.py`.
- Router diverts `needs_agent` to local `core/agent.agent_loop()` (since `client` is None); `< 0.7` confidence or `clarification_needed` sets `awaiting_clarification` state.
- Undo: `correct_last` intent (`undo`, `am greșit`) reverts `last_intent` saved in `conversation_state`.

## Critical gotchas

- **Write confirmation is gated by `REQUIRE_CONFIRMATION`** (default `true` in `core/config.py:25`), NOT hardcoded off. `router.py:276-285`: write intents with `needs_confirmation=true` are intercepted and stored as `awaiting_action_confirm` with a pending action; `.env.example` documents `REQUIRE_CONFIRMATION=true`. No `if False:` bypass remains.
- **`get_gemini_response` → Ollama** (legacy alias). `client` (Gemini) is `None`; the real google client lives only in `bot/voice.py` for STT.
- **Migrations auto-apply at startup** — `db/connection.apply_migrations()` runs `db/migrations/*.sql` alphabetically, tracked in `schema_migrations` (idempotent). No manual migration step needed. Extra DDL also runs in `main.py` (`saved_locations`, `travel_items`, `feedback`, `ALTER TABLE` fixes) — `schema.sql` is NOT the full source of truth.
- **`bot/handler.py` monkey-patches** `CallbackQuery.edit_message_text` and `Message.edit_text` to auto-wrap `safe_markdown()`. Send MarkdownV2 text raw; monkey-patch handles escaping (handler.py:22-43).
- **PID lock** (`lora.pid`) prevents a second instance; **15s startup delay** (main.py:624) for old polling to clear.
- **Web server** on `PORT` (default 8083) proxies all `/api/*` to `http://127.0.0.1:8090` (FastAPI launched as a background uvicorn task from `main.py`). **All non-API paths** serve `dashboard/dist/index.html` (React Router SPA fallback). Dashboard dist must be built or the SPA 404s.
- **`/reload`** uses `os.execl()` (handler.py:534) — hard restart, drops in-flight requests.
- **Group chat @mention-only** — in groups, bot stays silent unless explicitly @mentioned (handler.py:461-490).
- **`requirements.txt` has `google-generativeai` (old SDK) and `cerebras-cloud-sdk` (unused)** — code uses `google-genai` (`from google import genai`). If pip installing, use `google-genai`.
- **`DATABASE_URL` auto-fix** — `core/config.py:51-52` and `lora_api/config.py:7-8` silently rewrite `postgres://` → `postgresql://`.
- **`bot/handler.py` is 3600+ lines** — all commands/callbacks live there; keep modules Telegram-free.

## Env vars

**Required** (validated at import in `core/config.py`): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`, `DATABASE_URL`, `TIMEZONE`, `MORNING_BRIEFING_TIME`, `EOD_REFLECTION_TIME`, `LORA_API_SECRET`

**Optional (opt-in features)**: `OLLAMA_HOST` (default `http://localhost:11434`), `OLLAMA_MODEL` (default `llama3.2:3b`), `OLLAMA_STRUCTURED_MODEL` (default `qwen2.5:7b`, used only by receipt parsing), `OLLAMA_VISION_MODEL` (default `moondream`), `REQUIRE_CONFIRMATION`, `GEMINI_API_KEY` (voice STT), `GROQ_API_KEY` / `OPENAI_API_KEY` (STT fallbacks), `OPENWEATHER_API_KEY`, `NUTRITIONIX_APP_ID`/`NUTRITIONIX_API_KEY`, `SEMESTER_START_DATE`, iCloud (`ICLOUD_USERNAME`, `ICLOUD_APP_PASSWORD`, `ICLOUD_CALENDAR_NAME`, `CALENDAR_SYNC_INTERVAL_MINUTES`, `CALENDAR_SECRET`), `HABIT_REMINDER_TIME`, `WEEKLY_REVIEW_DAY`, `JOURNAL_NIGHT_TIME`, `COUNCIL_API_SECRET`, `LORA_API_PASSWORD`, `JWT_SECRET`, `API_PORT` (default 8090), `DASHBOARD_URL`, `LORA_ALLOWED_ORIGINS` (default `http://localhost:5173`), `WEATHER_CITY`, `TASK_CLEANUP_DAYS`, home server (`SERVER_IP`, `SERVER_SSH_USER`, `SERVER_SSH_PASSWORD`, `QBIT_USERNAME`, `QBIT_PASSWORD`, `RADARR_API_KEY`, `SONARR_API_KEY`), `KITTEN_TTS_MODEL` (default `KittenML/kitten-tts-mini-0.8`), `KITTEN_TTS_VOICE` (default `Luna`)

## Commands

```bash
python main.py                # bot (Ollama must be reachable at OLLAMA_HOST)
python -m lora_api.main       # standalone API + dashboard (NO LLM) — ./run_api.sh
pytest                        # 35 tests; needs `.env` (core.config validates env at import)
ruff check .                  # defaults; no config file
cd dashboard && npm run dev   # Vite dev server on 5173
cd dashboard && npm run build # tsc -b && vite build → dashboard/dist/
```

DB: base schema once via `psql $DATABASE_URL -f db/schema.sql`; per-file startup migrations are automatic.

## Scheduler (scheduler/jobs.py)

`setup_scheduler()` registers ~28 APScheduler jobs. Notable: morning briefing catch-up (05:00 + startup check), EOD reflection, weekly review (Sun 21:30), monthly review (1st 20:00), weekly finance summary (Mon), class reminders (every 5 min), event reminders (every 1 min), habit reminders, weather alerts (3h), calendar sync (`CALENDAR_SYNC_INTERVAL_MINUTES`), Cleanups at 04:00/04:30, contextual nudges hourly. All jobs get `misfire_grace_time`; add new jobs here, same pattern (`args=[application, pool]`).

## Valid modules (router.py `VALID_MODULES` whitelist)

`tasks`, `projects`, `notes`, `finance`, `events`, `shopping`, `goals`, `skills`, `mood`, `insights`, `health`, `nutrition`, `workout`, `university`, `schedule`, `reading`, `focus`, `planner`, `memory`, `weather`, `calendar` (→ `calendar_module`), `calendar_module`, `integrations`, `travel`, `wishlist`, `news`. Unknown module name → falls back to chat (no crash).

## Standalone API (lora_api/main.py)

Independent of the Telegram bot (no LLM). Run via `./run_api.sh` (port `API_PORT`, default 8090) or `./start_kiosk.sh` (port 8088, background, logs to `api.log`); both auto-detect `.venv/bin/python` and auto-build the dashboard if `dashboard/dist` is missing. **Requires `DATABASE_URL`, `JWT_SECRET`, and `LORA_API_PASSWORD`** (raised in FastAPI lifespan, `lora_api/main.py:36-41`). Also runs `apply_migrations()` at startup and serves the dashboard SPA.

**⚠️ API port must match bot web proxy** — `main.py:439` proxies `/api/*` to `127.0.0.1:8090`.

## TTS (hybrid engine)

`bot/tts.py`: KittenTTS (local ONNX) for English, `edge-tts` for Romanian — auto-detected via diacritics (`ăâîșț`) + common-word heuristics. `voice="auto"` is default (override `"ro"`/`"en"`). Model pre-loads in background at startup (`main.py`); until loaded, English falls back to `en-US-JennyNeural` (edge-tts). 30s timeout on download.

## Vision & OCR (100% local)

`core/vision.py`:
- **OCR**: `bin/apple_ocr` (Swift `VNRecognizeTextRequest`, Apple Neural Engine, macOS only — auto-compiles from `.swift` if missing). OCR preprocessing uses PIL (EXIF rotate, grayscale, upscale <1200px, contrast).
- **Receipts**: local Ollama `OLLAMA_STRUCTURED_MODEL` parses receipts into line-items → each confirmed as a separate expense.
- **Scene/food**: `OLLAMA_VISION_MODEL` (moondream) + structured model macro pipeline with inline confirmation.

## Style

- Type hints: `async def fn(pool, user_id: int) -> Optional[Dict[str, Any]]:`
- DB: `$1, $2` placeholders — never f-strings
- Imports: stdlib → third-party → local absolute
- Errors to user in Romanian ("A apărut o eroare."); system comments English
- No filler words ("Sigur!", "Cu plăcere!", "Bineînțeles!", "Desigur!") and NEVER address the user by name — rules are enforced inside the LLM system prompt with ALL-CAPS directives
- Romglish: Romanian base, English tech terms

## State machine (`core/state.py`)

Single row `conversation_state` with `state_key = 'current'`; idle ⇒ `state_type = NULL`. **30-minute TTL** — expired state is returned as None (state.py:32-45). Undo metadata (`last_intent`, `last_inserted_id`) survives `clear_state()`.

**Confirm/action**: `awaiting_confirmation`, `awaiting_action_confirm` (pending write), `awaiting_clarification`
**Multi-turn input**: `awaiting_edit_field`, `awaiting_task_input`, `awaiting_project_input`, `awaiting_health_input`, `awaiting_finance_input`, `awaiting_workout_input`, `awaiting_skill_input`, `awaiting_uni_input`, `awaiting_eod_mood`, `awaiting_day_plan_input`, `awaiting_evening_response`
**Module-specific**: `awaiting_focus_result`, `awaiting_profile_hours`, `awaiting_event_note`, `awaiting_project_edit`, `awaiting_project_name`, `awaiting_goal_title`, `awaiting_goal_description`, `awaiting_subtask_title`, `awaiting_vision_confirmation`, `skills_*`, `reading_*`

## MarkdownV2 rules

- `escape_md()` → user-supplied strings only
- `safe_markdown()` → LLM-generated text (handles double-escaping, balances `*`/backticks)
- **Date strings in JSON `reply` field must be RAW** — never `escape_md()` dates
- `split_message()` (`bot/formatter.py:49`) splits at 4000 chars

## Council integration

Disabled/isolated — `core/council.py` is never invoked by tasks or scheduler (only a docstring reference remains).

## Frontend (dashboard/)

- **React 19 + TypeScript 6 + Vite 8 + React Router v7 + TanStack Query v5**; TailwindCSS 3, framer-motion, lucide-react, zustand
- 26 API routers in `lora_api/routers/` (one per module) + WebSocket push via `lora_api.main.ws_manager`
- Build is `tsc -b && vite build` (type errors fail the build); lint via `npm run lint` (eslint)
- Login via JWT (`LORA_API_PASSWORD` + `JWT_SECRET`); 401 → auto-logout
- **Kiosk** (`/kiosk`): fullscreen tablet dashboard; **Lora Space** (`/space`): admin panel (Profile, LLM toggle, integration test buttons)
- Theme toggle via `ThemeContext`, persisted to `localStorage["lora_theme_mode"]`
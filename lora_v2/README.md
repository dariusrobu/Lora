# Lora v2 — isolated rebuild

This is a separate application and database. The legacy bot, dashboard, Obsidian files, and n8n workflows are untouched. Do not run both Telegram polling bots with the same token at the same time.

## Local setup

1. Create a **new PostgreSQL database** and set `LORA_V2_DATABASE_URL` to its URL. The code rejects reuse of `DATABASE_URL`.
2. Set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`, and `TIMEZONE=Europe/Bucharest` in the existing local environment. Set `LORA_V2_MEDIA_DIR` to a persistent private folder for photos and voice messages.
3. Run Ollama locally with `qwen2.5:7b`, a vision model (default `moondream`), and a local Faster Whisper model (default `base`). `LORA_V2_OLLAMA_MODEL`, `LORA_V2_VISION_MODEL`, and `LORA_V2_WHISPER_MODEL` override them.
4. `cd lora_v2/web && npm ci && npm run build` builds the Mini App.
5. `.venv/bin/uvicorn lora_v2.run_api:app --host 127.0.0.1 --port 8092` serves the API and built Mini App. Telegram requires a trusted HTTPS URL. Set `LORA_V2_MINI_APP_URL` to that URL before starting the new bot.
6. `.venv/bin/python -m lora_v2.bot` starts Telegram polling and the background worker **only after stopping the legacy polling bot**.

Migrations run automatically on the v2 database at startup. `LORA_V2_APPLE_SYNC_ENABLED` defaults to `false`; when enabled, it uses a dedicated Apple Reminders list named `Lora v2` and the existing iCloud credentials. Its two-way merge has simulated tests, but it still requires a live Apple account test and conflict resolution UI before relying on it.

## Data migration

`python -m lora_v2.migrate_legacy` is a read-only source inventory by default. `--apply` requires `--backup-file` and writes only to the v2 database. The migration is idempotent for its supported entities. Compare source and target counts and inspect dates, schedule parity, and sample items before switching. Some secondary history and integrations remain to be mapped.

## Current safety boundary

Clear Mini App forms use validated commands. Natural-language captures are saved before model processing, and proposed changes need approval. The local LLM is **not yet reliable on long compound messages**; wrong dates, mismatched amounts, and invalid commands are rejected or sent for clarification. No production cutover has been performed.

## Checks

`.venv/bin/ruff check lora_v2 tests/test_lora_v2.py`

`LORA_V2_TEST_DATABASE_URL=<isolated-test-db> .venv/bin/pytest -q tests/test_lora_v2.py`

`cd lora_v2/web && npm run build`

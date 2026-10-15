# Lora v2 — isolated rebuild

This is a separate application and database. The legacy bot, dashboard, Obsidian files, and n8n workflows are untouched. Do not run both Telegram polling bots with the same token at the same time.

## Local setup

1. Create a **new PostgreSQL database** and set `LORA_V2_DATABASE_URL` to its URL. The code rejects reuse of `DATABASE_URL`.
2. Set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`, and `TIMEZONE=Europe/Bucharest` in the existing local environment. Set `LORA_V2_MEDIA_DIR` to a persistent private folder for photos and voice messages.
3. Run Ollama locally with `qwen2.5:7b`, a vision model (default `moondream`), and a local Faster Whisper model (default `base`). `LORA_V2_OLLAMA_MODEL`, `LORA_V2_VISION_MODEL`, and `LORA_V2_WHISPER_MODEL` override them.
4. `cd lora_v2/web && npm ci && npm run build` builds the Mini App.
5. `.venv/bin/uvicorn lora_v2.run_api:app --host 127.0.0.1 --port 8092` serves the API and built Mini App. Telegram requires a trusted HTTPS URL. Set `LORA_V2_MINI_APP_URL` to that URL before starting the new bot.
6. `.venv/bin/python -m lora_v2.bot` starts Telegram polling and the background worker **only after stopping the legacy polling bot**.

Migrations run automatically on the v2 database at startup. `LORA_V2_APPLE_SYNC_ENABLED` defaults to `false`; when enabled, it uses a dedicated Apple Reminders list named `Lora v2` and the existing iCloud credentials. The Mini App has a conflict review screen and the two-way merge has simulated tests. A temporary task was pushed to the configured iCloud account, edited remotely, pulled back into a temporary v2 database, and removed from Apple. The live background worker, user-facing conflict flow, and device notification delivery still need verification before enabling automatic sync.

## Data migration

`python -m lora_v2.migrate_legacy` is a read-only source inventory by default. `--apply` requires `--backup-file` and writes only to the v2 database. The migration is idempotent for its supported entities. Invalid legacy rows that cannot become valid v2 records are retained in `legacy_import_exceptions` for review. The importer has been exercised against a restored copy of the local legacy database; it has not been applied to a live v2 production database. Compare source and target counts and inspect dates, schedule parity, and sample items before switching. Some secondary history and integrations remain to be mapped.

## Current safety boundary

Clear Mini App forms use validated commands. Natural-language captures are saved before model processing, and proactive changes require the owner's choice. Common Romanian captures have deterministic extraction with validation. The local LLM is **not yet reliable on arbitrary long compound messages**; wrong dates, mismatched amounts, and invalid commands are rejected or sent for clarification. No production cutover has been performed.

The Mini App now displays the last submitted message's processing result or clarification in place while the worker also sends its receipt to Telegram. It polls the owner-scoped capture endpoint until the worker has produced a result; direct forms remain available during an Ollama outage.

Recent local evaluations found invented command types and missing dates from `qwen2.5:7b`. Parsing now preserves valid actions from a partially invalid JSON reply and asks for clarification about the rest. Grounded Romanian shortcuts handle common tasks with times, reminders, transport expenses, stated food weights, and water in liters. For stated food weights, the raw/cooked answer is kept for ten minutes and must arrive before a meal proposal is made. The recorded grams are labeled with that preparation state; calories and macros remain unset until a trusted nutrition estimate is available. Broader food clarification and general conversational accuracy still need work.

If Ollama is unavailable while a compound text or voice capture contains clear deterministic actions, those actions still run. The unparsed remainder is retained as a separate local capture and retried by the worker after five minutes; retries do not repeat the already executed actions or send repeated failure messages. Relative dates in text, voice, and photo interpretation use the original capture time, so a delayed retry does not shift the meaning of „azi” or „mâine”. This has a simulated outage/recovery test, not a live long-duration outage test.

Every photo-derived meal requires explicit review before saving, even if the vision model reports high confidence. If it cannot identify an item, the bot asks for a new photo with a description rather than creating an approvable meal. Photo captures cannot create unrelated entities. This behavior has an isolated database test with a mocked vision result; real photo accuracy has not yet been validated.

When `NUTRITION_CLOUD_ENABLED=true` and the existing USDA key is configured, v2 uses the project's read-only USDA/Open Food Facts reference lookup. Only an ingredient identity and preparation hint leave the Mac; photos, conversation text, gram weights, and meal history stay local. Model-generated calories and macros are discarded. A verified per-100 g reference is scaled locally and stored with its provider, title, ID, and URL; an ambiguous or incompatible match leaves macros blank. Every AI meal is reviewed before saving. The Journal shows full-meal totals only when every item has complete values and exposes the reference for each item. A live lookup for generic cooked chicken breast returned breaded microwave tenders; v2 rejects that result rather than displaying false precision. More specific preparation and food-variety dialogue is still needed for broad nutrition coverage.

Telegram answers short read-only questions such as „Ce am azi?”, „Ce am mâine?”, „Ce taskuri am?”, „Cât am cheltuit luna asta?” and „Ce am la facultate azi?” directly from v2 data. `/azi`, `/maine`, `/taskuri`, `/cheltuieli`, and `/facultate` are shortcuts for the same views. Text and transcribed voice can propose deletion of the latest item in a named domain or correction of the latest expense category. A short follow-up answer to a missing target or category is retained for ten minutes. The target and version are shown before explicit approval; broader edits and entity selection still need work.

The University tab opens on a seven-day calendar, with the selected day's classes and exams visible immediately. Navigating weeks materializes that week's academic rules in the isolated v2 database, including odd/even weeks and vacations. Academic data editing stays behind the calendar; Obsidian and n8n remain untouched.

The background worker also materializes the next 14 days of classes at startup and on each new day, without opening the Mini App. When an approximate noon reminder would land during classes, the capture flow proposes the first free slot with a 15-minute buffer after the overlapping classes; it waits for approval before saving. A database/FakeBot journey verifies academic conflict proposals and the two requested event alerts at 30 minutes before and at the start. Real Telegram/device delivery still needs cutover verification.

Evening follow-ups for unfinished reminders now offer explicit „Am făcut” and „Mută pe mâine” choices in Telegram and the Mini App. Both verify the reminder version before updating it; generated conflict proposals also wait for a choice.

For expenses, a category explicitly chosen in the Mini App overrides an older merchant rule and becomes the new learned category for that merchant. When a newly extracted expense disagrees with the remembered merchant category, Lora shows both categories and waits for the owner's approval before saving; a changed rule invalidates a stale approval. If no category and no merchant rule is available, Lora keeps the expense for ten minutes, asks for a short category reply, and proposes the completed expense for review. This prevents an incomplete expense proposal that could never be saved.

## Checks

`.venv/bin/ruff check lora_v2 tests/test_lora_v2.py`

`LORA_V2_TEST_DATABASE_URL=<isolated-test-db> .venv/bin/pytest -q tests/test_lora_v2.py`

`cd lora_v2/web && npm run build`

# Lora v2 cutover — 20 October 2026

## Live runtime

Telegram now runs `lora_v2.bot`, with a separate `lora_v2.run_worker` for capture
processing and delivery. `com.lora.bot` is disabled in launchd and is no longer
polling. The v2 bot does not start a second worker in this installation.

Both `/` and `/v2` on the public gateway serve Mini App v2. Legacy `/api/*` writes
return 410 instead of silently writing the old database. Telegram commands and
Mini App share `LORA_V2_DATABASE_URL`. The owner confirmed the Mini App displays
the correct data after cutover.

Services are installed from the tracked `scripts/com.lora.v2.*.plist` files.
The existing n8n workflow was not edited or activated. Its `/extract-many` bridge
is now independently available on port 8788, including HTTP 200 from inside the
n8n container. The existing workflow is inactive; connectivity is not a claim
that a scheduled Moodle extraction ran.

## Data and backups

- Both databases were backed up and restored into temporary databases before
  cutover. Fresh activation backups/config/LaunchAgents and the Markdown vault
  copy are private under `backups/v2-activation-20261019-150315/`.
- Final source snapshot ID: `0eb0df74-9b5c-4bef-8bd5-9f592f0da6e1` (see activation-report.json for the
  exact ID). Every public legacy table is retained in v2 snapshots, including
  fields that have no corresponding v2 editor.
- Mapped live data: 1 project, 31 tasks, 35 events/reminders, 74 expenses, 3 incomes,
  5 workouts, 4 health records, 12 subjects, 23 timetable rules, 39 attendance
  records, 2 grades and 10 vacation periods. There are no source meals or exams.
- One invalid expense is preserved in `legacy_import_exceptions`; it was not
  silently converted into a valid amount.
- Reimports update untouched imported records and preserve v2 versions > 1.
  No active pending legacy task or future standalone reminder remained at cutover.
- Complete snapshots are preservation, **not active CRUD coverage for every old
  module**. Receipt-learning data and operational history are retained but do
  not yet have v2 editors or runtime consumers.
- The 20 October history migration promoted 91 reflections, 18 day plans,
  14 expense categories, the owner's safe profile fields, and nutrition targets
  to editable v2 tables. The profile's old cloud API key was explicitly excluded.
  The Mini App exposes these under Jurnal → Istoric și preferințe; its authenticated
  API returned all migrated counts through the active gateway. Expense inference
  uses active owner categories and asks when a clear keyword contradicts the
  model's category. Other archived legacy tables remain available only in the
  immutable snapshot until they receive a specific v2 consumer/editor.
- `scripts/backup_local.sh` now invokes a Python backup for both databases; it
  avoids sourcing dotenv as shell code. Dumps are mode 0600 and catalog-checked.
  It does not remove previous backups.

## Obsidian

`lora_v2.obsidian` updates existing frontmatter while preserving manual bodies,
unknown metadata, paths and attachments. It excludes archives, prefers existing
canonical subject notes, and does not recreate missing notes or treat absence
as deletion. Timetable fields can flow back to v2 with optimistic version checks;
simultaneous changes are recorded as conflicts rather than overwritten.

Verification on a complete Markdown copy: 107 metadata-only changes, no manual
body changes; the second sync made zero changes. Final live sync included two
new attendance records: 109 metadata updates, zero conflicts. Subsequent live
status was zero changes and zero conflicts.
Timetable conflicts can now be compared and resolved explicitly in Mini App.
The decision checks both the current v2 version and the exact note revision;
manual note bodies remain preserved.

The existing OCR/draft processor runs separately via
`lora_v2.run_obsidian_processor`. Its implementation and n8n workflows were not
rewritten. New generated entities may add a Markdown projection in the existing
domain folder; existing notes are never deleted by this adapter.

## Reminders and Telegram reliability

- Academic occurrences receive a reminder 15 minutes before class. Only future
  alert times are scheduled, avoiding replay of the legacy scheduler's alerts.
- Notification delivery runs independently from slow LLM/capture and Apple work.
- One live, clearly labelled test reminder was sent by the running worker. The
  outbox recorded one delivery; the test was removed from the active calendar.
- The owner's first `/azi` reached the new bot but sending its response failed
  with `httpx.ConnectError`. Read commands, help and ingress receipts now use the
  durable outbox. The missed response was recovered and recorded as delivered.
- A regression test simulates connection failure and verifies successful retry
  without duplicate outbox rows. Device confirmation of the repaired command is
  complete: the owner confirmed `/azi` responds after the repair.
- Stale proposals are expired when their reminder was edited or removed, and
  pending Telegram proposal messages are suppressed before delivery.

## Apple boundary

The existing dedicated `Lora v2` CalDAV collection is accessible. A temporary
reminder with no alarm was created, read back and removed successfully.
`LORA_V2_APPLE_SYNC_ENABLED=true` enables the existing two-way task/reminder
adapter, with conflict handling. Apple failures cannot stop Telegram delivery.

This proves the CalDAV boundary, **not visibility in Apple's current Reminders
app on the phone**. Native EventKit is not implemented. Legacy Apple Calendar
VEVENT exports/recurrence remain in iCloud but their ongoing reconciliation is
not yet implemented by the v2 Reminders adapter. Do not describe that separate
calendar integration as migrated or delete its existing remote records.

New v2-owned events now sync one way to a dedicated `Lora v2 Calendar` CalDAV
collection, including start/end and alert offsets. Migrated legacy events and
academic recurring exports still belong to the old calendar and are excluded
to avoid duplicate entries. A temporary, alarm-free event in the year 2000 was
created, read back, and deleted in the dedicated iCloud collection. This proves
the CalDAV boundary, not phone display or full old-calendar recurrence parity.
Remote edits block a v2 overwrite and are listed in Mini App under
"Evenimente de comparat". The owner can keep the Lora version or import the
Apple version after reviewing both; a version check prevents accepting an
outdated decision. This covers v2-owned events only. Remote-only edits to an
unchanged Lora event are detected when that event next changes locally, rather
than continuously monitored.

## Validation and rollback

48 isolated v2/migration/Obsidian/gateway/history/Apple event tests passed on a
clean database. A real-source isolated import also passed.
Focused Ruff checks and
Mini App production build passed. Authenticated live `/today`, `/tasks`,
`/university`, `/journal` and `/integrations` returned 200 through the gateway.
After the history migration, authenticated live `/daily-history`, `/proposals`,
`/obsidian/conflicts` and `/integrations` returned 200, and the gateway served
the updated Mini App bundle.
Migration `020_apple_event_conflicts.sql` applied in the live v2 database. After
restarting the API, worker and integration service, authenticated gateway
requests returned 200 for `/apple/event-conflicts` and `/daily-history`.

Rollback requires stopping the v2 bot, worker and integration services **before**
re-enabling legacy polling. Restore the saved runtime env/gateway configuration.
Reconcile any v2 records created after cutover; never restore an old database dump
blindly over new user data. Keep both notification schedulers from running at once.

The work remains on the `codex/lora-v2-daily-driver` branch until committed
and published.

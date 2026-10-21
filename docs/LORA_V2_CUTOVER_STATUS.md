# Lora v2 cutover — 20 October 2026

## 21 October: bounded daily agent

Lora v2 now creates a persisted daily brief from owner-scoped calendar,
academic, task and routine reads. Telegram accepts natural requests such as
“Organizează-mi ziua de mâine”; Mini App → Azi shows the latest brief and buttons
for today or tomorrow. The worker schedules one morning brief and one evening
brief using the saved morning/evening preferences (or the day's wake time plus
30 minutes), with 08:00/20:00 defaults. The evening brief includes open
reminders from today. Every suggested change is a separate, version-checked
proposal; the agent never executes a suggestion before approval. A short
“după ultimul curs” answer may revise one recent, unambiguous reminder proposal.
Ollama is local and bounded; saved data still produces a deterministic summary
if it is unavailable.

Migration `027` was applied after verified legacy and v2 backups. The isolated
v2 suite passed 49 tests, Ruff passed, and the Mini App production build passed.
The authenticated local gateway created and read an on-demand brief from live
data without creating a proposal. API and worker were restarted and healthy.
A scheduled brief has not yet reached its delivery time, so real Telegram
delivery of the new morning/evening message remains unobserved.

## 21 October: Moodle and iCloud Drive transition

The initial news import was too broad: it treated every Moodle forum discussion
as a personal update, including classmates' Marketing case studies and attendance
posts. The news importer accepts designated announcement forums and general
forum discussions started by a teacher listed for that subject in Lora or named
as teaching staff on the Moodle course page. The Mini App also lets the owner
follow an otherwise unknown forum author once under Facultate → Noutăți Moodle;
future posts by that author in that course generate notifications, while old
filtered posts become visible as read without retrospective alerts. Other
authors stay hidden. The initial live classification retained two teacher
messages and archived 53 student submissions without deleting them; an
authenticated gateway read returned two news items and all 203 material records.
The Moodle bridge was restarted so future n8n syncs use the corrected filter.

The active Moodle bridge now uses headless Chromium and writes downloaded
attachments to `iCloud Drive/Lora/Facultate/<materie>/`, with each file verified
by SHA-256. Moodle remains read-only. The existing n8n workflow is still active
every six hours and calls the same local bridge. A complete live bridge run
discovered seven courses, and an immediate repeat import produced no duplicate
files, posts or notifications. The live v2 database has 203 material records,
covering 198 distinct verified files in iCloud Drive, and 55 forum discussions.
Preexisting discussions were baselined as read, without retrospective alerts.
Subsequent new or changed discussions queue durable Telegram notifications and
appear under Facultate → Noutăți Moodle; new files appear under Materiale in
iCloud Drive. The owner confirmed that the seven subjects and files are visible
in iPad Files → iCloud Drive → Lora → Facultate.

The two v2 Obsidian LaunchAgents (`integrations` and `obsidian-processor`) are
disabled and stopped. n8n's Obsidian mount was removed; its own persistent data
volume and the six-hour workflow survived container recreation. The old vault
was **not deleted** and remains a recovery copy while non-Moodle notes are
reviewed. A scheduled n8n run after the Chromium change has not yet completed;
the complete live extraction was invoked directly through the same bridge.
The n8n CLI cannot manually run this Schedule Trigger without a start node.
The health monitor now checks freshness of each imported Moodle course.

Mini App now also has a private university notes editor with create, edit,
delete, subject association and concurrent-edit protection. Migration `025`
was applied after a verified backup; the authenticated live notes endpoint
returned 200 with zero notes. The old Markdown vault remains untouched while
the owner chooses which notes should be imported. The notes editor does not
yet render Markdown formatting or link directly to iCloud files.

## Live runtime

Telegram now runs `lora_v2.bot`, with a separate `lora_v2.run_worker` for capture
processing and delivery. `com.lora.bot` is disabled in launchd and is no longer
polling. The v2 bot does not start a second worker in this installation.

Both `/` and `/v2` on the public gateway serve Mini App v2. Legacy `/api/*` writes
return 410 instead of silently writing the old database. Telegram commands and
Mini App share `LORA_V2_DATABASE_URL`. The owner confirmed the Mini App displays
the correct data after cutover.

Services are installed from the tracked `scripts/com.lora.v2.*.plist` files.
On 20 October, the existing n8n Moodle-to-Obsidian workflow was changed only in
its Schedule Trigger, from an unspecified interval to every six hours, then
published and activated. Its existing `/extract-many` bridge and credentials
were preserved. A private workflow backup was saved before the change. The
bridge and n8n health endpoints returned 200 after restart. An isolated run
over the five cached courses generated 134 files; its second run generated no
new files, and existing Moodle index files use bounded generated sections.
No completed scheduled run has yet been observed after activation.

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
- Rules for a recognized expense merchant can be added, corrected and removed
  in Mini App under Jurnal → Istoric și preferințe. Applying a corrected rule
  to a later expense is covered by an isolated test. The old receipt product
  memory (700 rows) and merchant-name aliases (26 rows) remain in snapshots.
  The latest distinct product rules are now active in v2 (49 rules on the live
  owner). A receipt photo proposes one expense per product, with its own
  category; the Mini App lets the owner edit products, categories, amounts,
  merchant and total before one atomic approval. A printed-total mismatch or
  unsupported product prevents an automatic proposal. No real receipt photo
  has yet been verified end to end on the live phone.
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
- A recent overdue task now generates at most one opt-in move proposal per day,
  under the shared two-proposal daily limit. Completing or editing the task
  expires its pending proposal. No task date changes before approval.
- The local launchd health check now monitors the worker, integrations,
  Obsidian processor, n8n, Moodle bridge and overdue Telegram delivery in
  addition to the bot, API, gateway and Ollama.
- The natural phrase "Duminică am meci la 20, amintește-mi la 19:30 și 20:00"
  is handled without waiting for the LLM and creates one event with both
  reminder offsets.

## Apple boundary

The existing dedicated `Lora v2` CalDAV collection is accessible. A temporary
reminder with no alarm was created, read back and removed successfully.
`LORA_V2_APPLE_SYNC_ENABLED=true` enables the existing two-way task/reminder
adapter, with conflict handling. Apple failures cannot stop Telegram delivery.

The owner subsequently confirmed that a no-alarm test reminder appeared in
Apple Reminders on the iPhone. Native EventKit is not implemented. Legacy Apple Calendar
VEVENT exports/recurrence remain in iCloud but their ongoing reconciliation is
not yet implemented by the v2 Reminders adapter. Do not describe that separate
calendar integration as migrated or delete its existing remote records.

New v2-owned events now sync one way to a dedicated `Lora v2 Calendar` CalDAV
collection, including start/end and alert offsets. Migrated legacy events and
academic recurring exports still belong to the old calendar and are excluded
to avoid duplicate entries. A temporary, alarm-free event in the year 2000 was
created, read back, and deleted in the dedicated iCloud collection. A second
no-alarm event for 21 October at 15:30 was confirmed visible on the iPhone
**after synchronization**, then deleted remotely. Thus phone display works,
but immediate propagation is not guaranteed and full old-calendar recurrence
parity remains unverified.
Remote edits block a v2 overwrite and are listed in Mini App under
"Evenimente de comparat". The owner can keep the Lora version or import the
Apple version after reviewing both; a version check prevents accepting an
outdated decision. This covers v2-owned events only. Remote-only edits to an
unchanged Lora event are now detected on the next five-minute calendar sync.

## Validation and rollback

55 isolated v2/migration/Obsidian/gateway/history/Apple event/receipt tests
passed on a clean database after the final non-photo receipt guard. A
real-source isolated import also passed.
Focused Ruff checks and
Mini App production build passed. Authenticated live `/today`, `/tasks`,
`/university`, `/journal` and `/integrations` returned 200 through the gateway.
After the history migration, authenticated live `/daily-history`, `/proposals`,
`/obsidian/conflicts` and `/integrations` returned 200, and the gateway served
the updated Mini App bundle.
Migration `020_apple_event_conflicts.sql` applied in the live v2 database. After
restarting the API, worker and integration service, authenticated gateway
requests returned 200 for `/apple/event-conflicts` and `/daily-history`.
Receipt migrations `022` and `023` applied to the active v2 database after a
verified local backup. The expense count remained 74 before and after. After
restarting the API, worker and bot, all three services were running, the API
health check returned 200, and authenticated gateway requests returned 200 for
`/proposals` and `/journal` (74 expenses). The production Mini App bundle built
successfully. A real receipt photo remains to be checked on the phone.

Rollback requires stopping the v2 bot, worker and integration services **before**
re-enabling legacy polling. Restore the saved runtime env/gateway configuration.
Reconcile any v2 records created after cutover; never restore an old database dump
blindly over new user data. Keep both notification schedulers from running at once.

The v2 branch is `codex/lora-v2-daily-driver`; the previous cutover and history
changes were published as commit `f86bd0d`.

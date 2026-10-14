-- The active academic year starts on Monday 2026-09-28.
-- The old seed (2026-02-23) caused October 2026 reminders to use the wrong parity.
UPDATE semester_config
SET semester_start = '2026-09-28'
WHERE semester_start = '2026-02-23';

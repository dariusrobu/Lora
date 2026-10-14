ALTER TABLE task_deadline_reminders_sent
    ADD COLUMN IF NOT EXISTS reminder_slot TEXT NOT NULL DEFAULT '09';

ALTER TABLE task_deadline_reminders_sent
    DROP CONSTRAINT IF EXISTS task_deadline_reminders_sent_pkey;

ALTER TABLE task_deadline_reminders_sent
    ADD CONSTRAINT task_deadline_reminders_sent_pkey
    PRIMARY KEY (task_id, reminder_date, reminder_slot);

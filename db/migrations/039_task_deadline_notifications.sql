CREATE TABLE IF NOT EXISTS task_deadline_reminders_sent (
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    reminder_date DATE NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (task_id, reminder_date)
);

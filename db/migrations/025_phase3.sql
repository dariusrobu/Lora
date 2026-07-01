-- 025_phase3.sql — Lora Space Phase 3: Backups, jobs management

CREATE TABLE IF NOT EXISTS backup_config (
    id              SERIAL PRIMARY KEY,
    enabled         BOOLEAN DEFAULT FALSE,
    schedule_cron   TEXT DEFAULT '0 4 * * 0',
    retention_days  INTEGER DEFAULT 30,
    last_backup_at  TIMESTAMPTZ,
    next_backup_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO backup_config (enabled, schedule_cron, retention_days)
SELECT FALSE, '0 4 * * 0', 30
WHERE NOT EXISTS (SELECT 1 FROM backup_config LIMIT 1);

CREATE TABLE IF NOT EXISTS backup_log (
    id              SERIAL PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'pending',
    file_name       TEXT,
    file_size_bytes BIGINT,
    error_message   TEXT,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

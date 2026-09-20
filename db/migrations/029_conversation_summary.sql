CREATE TABLE IF NOT EXISTS conversation_summary (
    user_id BIGINT PRIMARY KEY,
    summary TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

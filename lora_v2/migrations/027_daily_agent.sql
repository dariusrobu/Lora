CREATE TABLE IF NOT EXISTS agent_briefs (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    target_date DATE NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('morning', 'evening', 'on_demand')),
    dedupe_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'ready', 'failed')),
    summary TEXT,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    tool_events JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, dedupe_key)
);
CREATE INDEX IF NOT EXISTS agent_briefs_owner_recent ON agent_briefs(owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_dialogue_focus (
    owner_id BIGINT PRIMARY KEY,
    brief_id UUID NOT NULL REFERENCES agent_briefs(id) ON DELETE CASCADE,
    proposal_id UUID NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    entity_type TEXT,
    entity_id UUID,
    expires_at TIMESTAMPTZ NOT NULL
);

-- 018: Archive agent_memory pre-images so upserts keep full history.
-- Idempotent (CockroachDB DDL). Written atomically with the store_memory upsert.

CREATE TABLE IF NOT EXISTS agent_memory_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL REFERENCES agent_memory(id) ON DELETE CASCADE,
    version INT NOT NULL,
    value JSONB,
    source STRING,
    confidence FLOAT,
    superseded_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_versions_memory
    ON agent_memory_versions (memory_id, version);

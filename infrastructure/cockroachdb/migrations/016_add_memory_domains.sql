-- 016: Promote embeddings metadata to real columns + add memory domain tables.
-- Idempotent (CockroachDB DDL). Backfills existing embeddings from metadata.

ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS org_id STRING;
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS content_type STRING;
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS content_id STRING;
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS workflow_id STRING;

UPDATE embeddings
SET org_id = COALESCE(metadata->>'org_id', org_id),
    content_type = COALESCE(metadata->>'content_type', content_type),
    content_id = COALESCE(metadata->>'content_id', content_id)
WHERE org_id IS NULL OR content_type IS NULL OR content_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_embeddings_org ON embeddings (org_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_org_type ON embeddings (org_id, content_type);
CREATE INDEX IF NOT EXISTS idx_embeddings_content_id ON embeddings (content_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_workflow ON embeddings (workflow_id);

CREATE TABLE IF NOT EXISTS episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    workflow_id STRING,
    thread_id UUID REFERENCES support_threads(id) ON DELETE SET NULL,
    source STRING,
    input_summary STRING,
    evidence_ids JSONB DEFAULT '[]',
    doc_id UUID REFERENCES documentation(id) ON DELETE SET NULL,
    outcome STRING,
    quality_score FLOAT,
    duration_ms INT8,
    token_usage INT8,
    cost_cents INT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_episodes_org_created ON episodes (org_id, created_at);
CREATE INDEX IF NOT EXISTS idx_episodes_workflow ON episodes (workflow_id);
CREATE INDEX IF NOT EXISTS idx_episodes_doc ON episodes (doc_id);

CREATE TABLE IF NOT EXISTS reflections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    episode_id UUID REFERENCES episodes(id) ON DELETE SET NULL,
    lesson STRING NOT NULL,
    confidence FLOAT,
    frequency INT DEFAULT 1,
    tags STRING[],
    status STRING DEFAULT 'active' CHECK (status IN ('active', 'superseded', 'archived')),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reflections_org_status ON reflections (org_id, status);
CREATE INDEX IF NOT EXISTS idx_reflections_episode ON reflections (episode_id);

CREATE TABLE IF NOT EXISTS memory_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    from_type STRING NOT NULL,
    from_id UUID NOT NULL,
    to_type STRING NOT NULL,
    to_id UUID NOT NULL,
    relation STRING NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_memory_links_from ON memory_links (from_type, from_id);
CREATE INDEX IF NOT EXISTS idx_memory_links_to ON memory_links (to_type, to_id);

CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    user_id STRING NOT NULL,
    preferences JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (org_id, user_id)
);

CREATE TABLE IF NOT EXISTS evaluation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    doc_id UUID REFERENCES documentation(id) ON DELETE CASCADE,
    episode_id UUID REFERENCES episodes(id) ON DELETE SET NULL,
    metric STRING NOT NULL,
    score FLOAT,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_evaluation_doc ON evaluation_results (doc_id);
CREATE INDEX IF NOT EXISTS idx_evaluation_metric ON evaluation_results (metric, created_at);

CREATE TABLE IF NOT EXISTS agent_trace_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    trace_id UUID,
    workflow_id STRING,
    node_name STRING NOT NULL,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration_ms FLOAT,
    token_usage INT8,
    input_state JSONB,
    output_state JSONB,
    error STRING,
    succeeded BOOL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_trace_nodes_workflow ON agent_trace_nodes (workflow_id, node_name);
CREATE INDEX IF NOT EXISTS idx_agent_trace_nodes_org_created ON agent_trace_nodes (org_id, created_at);

-- agent_memory lost its inline UNIQUE (org_id, key) constraint when migration 007
-- dropped the org_id column (the constraint came back down with it) and never
-- recreated it. Without it, store_memory's ON CONFLICT (org_id, key) upsert fails
-- with "no unique or exclusion constraint matching the ON CONFLICT specification".
-- Dedup any duplicates that accumulated since 007 (keep one row per (org_id, key),
-- preferring the most recently created), then restore uniqueness. The DELETE and
-- the ADD CONSTRAINT run in a single transaction (CockroachDB DDL is transactional),
-- so a concurrent insert cannot create a duplicate in the gap between them and fail
-- the ALTER. Idempotent: re-running is a no-op once the constraint exists.
BEGIN;

DELETE FROM agent_memory
WHERE id NOT IN (
    SELECT DISTINCT ON (org_id, key) id
    FROM agent_memory
    ORDER BY org_id, key, created_at DESC, id DESC
);

ALTER TABLE agent_memory
    ADD CONSTRAINT IF NOT EXISTS agent_memory_org_id_key UNIQUE (org_id, key);

COMMIT;

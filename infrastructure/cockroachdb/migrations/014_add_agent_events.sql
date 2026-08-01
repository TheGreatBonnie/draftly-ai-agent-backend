-- Migration 014: Structured agent event capture for dashboard telemetry

CREATE TABLE IF NOT EXISTS agent_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    workflow_id STRING,
    event_type STRING NOT NULL,
    level STRING NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_events_org_created ON agent_events (org_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_events_workflow ON agent_events (workflow_id);
CREATE INDEX IF NOT EXISTS idx_agent_events_type_created ON agent_events (event_type, created_at);

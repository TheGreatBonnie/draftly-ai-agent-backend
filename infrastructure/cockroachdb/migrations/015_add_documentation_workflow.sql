-- Migration 015: Link documentation rows to their originating workflow
--
-- Allows per-draft traces: a review's doc exposes workflow_id, which is used
-- to query the agent_events table for the full workflow timeline.

ALTER TABLE documentation ADD COLUMN IF NOT EXISTS workflow_id STRING;

CREATE INDEX IF NOT EXISTS idx_documentation_workflow ON documentation (workflow_id);

-- Compound index backing the per-draft trace lookup (org-scoped workflow events).
CREATE INDEX IF NOT EXISTS idx_agent_events_org_workflow ON agent_events (org_id, workflow_id);

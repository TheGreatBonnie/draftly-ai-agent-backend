-- Migration 011: Add discord_workflows table for pipeline run tracking
-- Mirrors the existing slack_workflows and github_workflows tables

CREATE TABLE IF NOT EXISTS discord_workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id),
    discord_channel_id STRING NOT NULL,
    discord_message_id STRING NOT NULL,
    discord_thread_id STRING,
    source_message STRING NOT NULL,
    status STRING NOT NULL DEFAULT 'pending',
    workflow_run_id UUID,
    report_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for org lookups (list workflows for an org)
CREATE INDEX IF NOT EXISTS idx_discord_workflows_org_id ON discord_workflows (org_id);

-- Index for status filtering (find pending/running workflows)
CREATE INDEX IF NOT EXISTS idx_discord_workflows_status ON discord_workflows (status);

-- Index for dedup lookups (check if message already processed)
CREATE INDEX IF NOT EXISTS idx_discord_workflows_message ON discord_workflows (discord_message_id);

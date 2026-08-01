-- Migration: Add Slack workflow tables
-- Date: 2026-07-23

-- 14. Slack Installations (Bolt OAuth installation data)
CREATE TABLE IF NOT EXISTS slack_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING,
    team_id STRING NOT NULL,
    team_name STRING,
    bot_user_id STRING,
    bot_token STRING NOT NULL,
    bot_scopes STRING,
    user_id STRING NOT NULL,
    user_token STRING,
    user_scopes STRING,
    token_type STRING,
    installed_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now() ON UPDATE now(),
    UNIQUE (team_id)
);

CREATE INDEX idx_slack_installations_org ON slack_installations(org_id);
CREATE INDEX idx_slack_installations_team ON slack_installations(team_id);

-- 15. Slack Workflows (pipeline runs triggered by Slack messages)
CREATE TABLE IF NOT EXISTS slack_workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL,
    channel_id STRING NOT NULL,
    thread_ts STRING NOT NULL,
    status STRING DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_slack_workflows_status ON slack_workflows(status);
CREATE INDEX idx_slack_workflows_thread ON slack_workflows(channel_id, thread_ts);

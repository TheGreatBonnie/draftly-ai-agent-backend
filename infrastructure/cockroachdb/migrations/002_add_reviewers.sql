-- Migration: Add reviewers table for notification preferences
-- Date: 2025-07-19

-- 9. Reviewers (notification recipients)
CREATE TABLE IF NOT EXISTS reviewers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name STRING NOT NULL,
    email STRING,
    slack_user_id STRING,
    discord_user_id STRING,
    notification_channel STRING DEFAULT 'slack' CHECK (notification_channel IN ('slack', 'discord', 'email')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now() ON UPDATE now()
);

CREATE INDEX IF NOT EXISTS idx_reviewers_org ON reviewers(org_id);
CREATE INDEX IF NOT EXISTS idx_reviewers_active ON reviewers(is_active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewers_email_org ON reviewers(org_id, email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewers_slack_org ON reviewers(org_id, slack_user_id) WHERE slack_user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewers_discord_org ON reviewers(org_id, discord_user_id) WHERE discord_user_id IS NOT NULL;

-- Add foreign key constraint to review_sessions
ALTER TABLE review_sessions ADD CONSTRAINT fk_reviewer 
    FOREIGN KEY (reviewer_id) REFERENCES reviewers(id) ON DELETE SET NULL;

-- Migration 008: Link reviewers to Clerk org members
-- Allows reviewer self-registration tied to a Clerk user account

ALTER TABLE reviewers ADD COLUMN clerk_user_id STRING;

CREATE INDEX idx_reviewers_clerk_user ON reviewers(clerk_user_id);

CREATE UNIQUE INDEX idx_reviewers_clerk_user_org ON reviewers(org_id, clerk_user_id)
    WHERE clerk_user_id IS NOT NULL;

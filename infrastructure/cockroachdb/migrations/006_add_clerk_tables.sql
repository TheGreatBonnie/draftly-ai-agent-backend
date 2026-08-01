-- Migration: Add Clerk auth tables
-- Date: 2025-07-20

-- Add clerk_org_id column to organizations
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS clerk_org_id STRING;
CREATE INDEX IF NOT EXISTS idx_organizations_clerk_org_id ON organizations(clerk_org_id);

-- 12. Clerk Users
CREATE TABLE IF NOT EXISTS clerk_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_user_id STRING NOT NULL UNIQUE,
    email STRING NOT NULL DEFAULT '',
    name STRING NOT NULL DEFAULT 'Unknown',
    avatar_url STRING NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now() ON UPDATE now()
);

-- 13. User-Organization memberships
CREATE TABLE IF NOT EXISTS user_organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES clerk_users(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role STRING NOT NULL DEFAULT 'org:member',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, org_id)
);

CREATE INDEX IF NOT EXISTS idx_user_org_user ON user_organizations(user_id);
CREATE INDEX IF NOT EXISTS idx_user_org_org ON user_organizations(org_id);

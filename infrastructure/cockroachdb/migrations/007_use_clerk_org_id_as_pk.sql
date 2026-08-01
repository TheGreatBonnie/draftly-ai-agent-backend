-- Migration: Use Clerk org_id as primary key for organizations
-- Date: 2026-07-20
--
-- CockroachDB limitation: cannot ALTER COLUMN TYPE on PK columns or indexed columns.
-- Strategy: add new column -> copy data -> drop old -> rename -> add constraints.

-- Step 1: Unlock schema-locked tables
ALTER TABLE organizations SET (schema_locked = false);

-- Step 2: Drop all FK constraints referencing organizations(id)

ALTER TABLE support_threads DROP CONSTRAINT IF EXISTS support_threads_org_id_fkey;
ALTER TABLE documentation DROP CONSTRAINT IF EXISTS documentation_org_id_fkey;
ALTER TABLE embeddings DROP CONSTRAINT IF EXISTS embeddings_org_id_fkey;
ALTER TABLE agent_workflows DROP CONSTRAINT IF EXISTS agent_workflows_org_id_fkey;
ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_org_id_fkey;
ALTER TABLE audit_logs DROP CONSTRAINT IF EXISTS audit_logs_org_id_fkey;
ALTER TABLE reviewers DROP CONSTRAINT IF EXISTS reviewers_org_id_fkey;
ALTER TABLE github_installations DROP CONSTRAINT IF EXISTS github_installations_org_id_fkey;
ALTER TABLE github_workflows DROP CONSTRAINT IF EXISTS github_workflows_org_id_fkey;
ALTER TABLE user_organizations DROP CONSTRAINT IF EXISTS user_organizations_org_id_fkey;

-- Step 3: Drop all indexes on org_id columns

DROP INDEX IF EXISTS idx_support_threads_org;
DROP INDEX IF EXISTS idx_doc_org;
DROP INDEX IF EXISTS idx_embeddings_org;
DROP INDEX IF EXISTS idx_workflow_org;
DROP INDEX IF EXISTS idx_memory_org;
DROP INDEX IF EXISTS idx_audit_org;
DROP INDEX IF EXISTS idx_reviewers_org;
DROP INDEX IF EXISTS idx_reviewers_active;
DROP INDEX IF EXISTS idx_installations_org;
DROP INDEX IF EXISTS idx_installations_github_org;
DROP INDEX IF EXISTS idx_user_org_org;

-- Drop unique constraints
ALTER TABLE support_threads DROP CONSTRAINT IF EXISTS support_threads_org_id_channel_id_thread_id_key;
ALTER TABLE user_organizations DROP CONSTRAINT IF EXISTS user_organizations_user_id_org_id_key;

-- Drop partial unique indexes on reviewers
DROP INDEX IF EXISTS idx_reviewers_email_org;
DROP INDEX IF EXISTS idx_reviewers_slack_org;
DROP INDEX IF EXISTS idx_reviewers_discord_org;

-- Step 4: Add new STRING columns alongside UUID columns

ALTER TABLE organizations ADD COLUMN new_id STRING;
ALTER TABLE support_threads ADD COLUMN new_org_id STRING;
ALTER TABLE documentation ADD COLUMN new_org_id STRING;
ALTER TABLE embeddings ADD COLUMN new_org_id STRING;
ALTER TABLE agent_workflows ADD COLUMN new_org_id STRING;
ALTER TABLE agent_memory ADD COLUMN new_org_id STRING;
ALTER TABLE audit_logs ADD COLUMN new_org_id STRING;
ALTER TABLE reviewers ADD COLUMN new_org_id STRING;
ALTER TABLE github_installations ADD COLUMN new_org_id STRING;
ALTER TABLE github_workflows ADD COLUMN new_org_id STRING;
ALTER TABLE user_organizations ADD COLUMN new_org_id STRING;

-- Step 5: Copy data (UUID -> STRING conversion)

-- Organizations: generate synthetic Clerk-format IDs
UPDATE organizations SET new_id = 'org_default' WHERE name = 'default';
UPDATE organizations SET new_id = 'org_github_' || name WHERE name != 'default' AND new_id IS NULL;

-- Child tables: copy UUID as string (will be replaced by matching org_id)
UPDATE support_threads SET new_org_id = (
    SELECT new_id FROM organizations WHERE organizations.id = support_threads.org_id
);
UPDATE documentation SET new_org_id = (
    SELECT new_id FROM organizations WHERE organizations.id = documentation.org_id
);
UPDATE embeddings SET new_org_id = (
    SELECT new_id FROM organizations WHERE organizations.id = embeddings.org_id
);
UPDATE agent_workflows SET new_org_id = (
    SELECT new_id FROM organizations WHERE organizations.id = agent_workflows.org_id
);
UPDATE agent_memory SET new_org_id = (
    SELECT new_id FROM organizations WHERE organizations.id = agent_memory.org_id
);
UPDATE audit_logs SET new_org_id = (
    SELECT new_id FROM organizations WHERE organizations.id = audit_logs.org_id
);
UPDATE reviewers SET new_org_id = (
    SELECT new_id FROM organizations WHERE organizations.id = reviewers.org_id
);
UPDATE github_installations SET new_org_id = (
    SELECT new_id FROM organizations WHERE organizations.id = github_installations.org_id
);
UPDATE github_workflows SET new_org_id = (
    SELECT new_id FROM organizations WHERE organizations.id = github_workflows.org_id
);
UPDATE user_organizations SET new_org_id = (
    SELECT new_id FROM organizations WHERE organizations.id = user_organizations.org_id
);

-- Step 6: Drop old columns and PK

ALTER TABLE organizations DROP COLUMN id;
ALTER TABLE organizations RENAME COLUMN new_id TO id;
ALTER TABLE organizations ALTER COLUMN id SET NOT NULL;
ALTER TABLE organizations ADD CONSTRAINT PRIMARY KEY (id);

-- Drop old org_id columns and rename new ones
ALTER TABLE support_threads DROP COLUMN org_id;
ALTER TABLE support_threads RENAME COLUMN new_org_id TO org_id;
ALTER TABLE support_threads ALTER COLUMN org_id SET NOT NULL;

ALTER TABLE documentation DROP COLUMN org_id;
ALTER TABLE documentation RENAME COLUMN new_org_id TO org_id;
ALTER TABLE documentation ALTER COLUMN org_id SET NOT NULL;

ALTER TABLE embeddings DROP COLUMN org_id;
ALTER TABLE embeddings RENAME COLUMN new_org_id TO org_id;
ALTER TABLE embeddings ALTER COLUMN org_id SET NOT NULL;

ALTER TABLE agent_workflows DROP COLUMN org_id;
ALTER TABLE agent_workflows RENAME COLUMN new_org_id TO org_id;
ALTER TABLE agent_workflows ALTER COLUMN org_id SET NOT NULL;

ALTER TABLE agent_memory DROP COLUMN org_id;
ALTER TABLE agent_memory RENAME COLUMN new_org_id TO org_id;
ALTER TABLE agent_memory ALTER COLUMN org_id SET NOT NULL;

ALTER TABLE audit_logs DROP COLUMN org_id;
ALTER TABLE audit_logs RENAME COLUMN new_org_id TO org_id;
ALTER TABLE audit_logs ALTER COLUMN org_id SET NOT NULL;

ALTER TABLE reviewers DROP COLUMN org_id;
ALTER TABLE reviewers RENAME COLUMN new_org_id TO org_id;
ALTER TABLE reviewers ALTER COLUMN org_id SET NOT NULL;

ALTER TABLE github_installations DROP COLUMN org_id;
ALTER TABLE github_installations RENAME COLUMN new_org_id TO org_id;
ALTER TABLE github_installations ALTER COLUMN org_id SET NOT NULL;

ALTER TABLE github_workflows DROP COLUMN org_id;
ALTER TABLE github_workflows RENAME COLUMN new_org_id TO org_id;
ALTER TABLE github_workflows ALTER COLUMN org_id SET NOT NULL;

ALTER TABLE user_organizations DROP COLUMN org_id;
ALTER TABLE user_organizations RENAME COLUMN new_org_id TO org_id;
ALTER TABLE user_organizations ALTER COLUMN org_id SET NOT NULL;

-- Step 7: Re-add FK constraints

ALTER TABLE support_threads ADD CONSTRAINT fk_support_threads_org
    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE documentation ADD CONSTRAINT fk_documentation_org
    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE embeddings ADD CONSTRAINT fk_embeddings_org
    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE agent_workflows ADD CONSTRAINT fk_agent_workflows_org
    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE agent_memory ADD CONSTRAINT fk_agent_memory_org
    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE audit_logs ADD CONSTRAINT fk_audit_logs_org
    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE reviewers ADD CONSTRAINT fk_reviewers_org
    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE github_installations ADD CONSTRAINT fk_github_installations_org
    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE github_workflows ADD CONSTRAINT fk_github_workflows_org
    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE user_organizations ADD CONSTRAINT fk_user_organizations_org
    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;

-- Step 8: Re-create indexes

CREATE INDEX idx_support_threads_org ON support_threads(org_id);
CREATE INDEX idx_doc_org ON documentation(org_id);
CREATE INDEX idx_embeddings_org ON embeddings(org_id);
CREATE INDEX idx_workflow_org ON agent_workflows(org_id);
CREATE INDEX idx_memory_org ON agent_memory(org_id);
CREATE INDEX idx_audit_org ON audit_logs(org_id);
CREATE INDEX idx_reviewers_org ON reviewers(org_id);
CREATE INDEX idx_reviewers_active ON reviewers(is_active);
CREATE INDEX idx_installations_org ON github_installations(org_id);
CREATE INDEX idx_installations_github_org ON github_installations(github_org);
CREATE INDEX idx_user_org_org ON user_organizations(org_id);

-- Recreate unique constraints
CREATE UNIQUE INDEX idx_support_threads_org_channel_thread
    ON support_threads(org_id, channel_id, thread_id);
CREATE UNIQUE INDEX idx_user_org_unique
    ON user_organizations(user_id, org_id);

-- Recreate partial unique indexes on reviewers
CREATE UNIQUE INDEX idx_reviewers_email_org ON reviewers(org_id, email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX idx_reviewers_slack_org ON reviewers(org_id, slack_user_id) WHERE slack_user_id IS NOT NULL;
CREATE UNIQUE INDEX idx_reviewers_discord_org ON reviewers(org_id, discord_user_id) WHERE discord_user_id IS NOT NULL;

-- Step 9: Re-lock schema
ALTER TABLE organizations SET (schema_locked = true);

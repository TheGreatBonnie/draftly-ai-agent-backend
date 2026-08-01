-- Draftly AI Database Schema
-- CockroachDB with Distributed Vector Index

-- Enable vector indexes (required for CREATE VECTOR INDEX to work)
SET CLUSTER SETTING feature.vector_index.enabled = true;

-- 1. Organizations (multi-tenant)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_org_id STRING NOT NULL UNIQUE,
    clerk_org_name STRING NOT NULL,
    slack_workspace_id STRING,
    discord_guild_id STRING,
    discord_trigger_channels JSONB DEFAULT '[]'::JSONB,
    github_org STRING,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Support Threads (episodic memory)
CREATE TABLE IF NOT EXISTS support_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    source STRING NOT NULL CHECK (source IN ('slack', 'discord', 'github', 'cli')),
    channel_id STRING NOT NULL,
    thread_id STRING NOT NULL,
    title STRING,
    question_summary STRING,
    resolution TEXT,
    status STRING DEFAULT 'open' CHECK (status IN ('open', 'processing', 'resolved')),
    participants JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    UNIQUE (org_id, channel_id, thread_id)
);

CREATE INDEX IF NOT EXISTS idx_support_threads_org ON support_threads(org_id);
CREATE INDEX IF NOT EXISTS idx_support_threads_status ON support_threads(status);
CREATE INDEX IF NOT EXISTS idx_support_threads_source ON support_threads(source);

-- 3. Documentation (versioned output)
CREATE TABLE IF NOT EXISTS documentation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    title STRING NOT NULL,
    content TEXT NOT NULL,
    doc_type STRING NOT NULL CHECK (doc_type IN ('howto', 'faq', 'tutorial', 'troubleshooting', 'reference')),
    version INT DEFAULT 1,
    status STRING DEFAULT 'draft' CHECK (status IN ('draft', 'in_review', 'approved', 'published')),
    source_thread_id UUID REFERENCES support_threads(id) ON DELETE SET NULL,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    published_to JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now() ON UPDATE now()
);

CREATE INDEX IF NOT EXISTS idx_doc_org ON documentation(org_id);
CREATE INDEX IF NOT EXISTS idx_doc_status ON documentation(status);

-- 4. Embeddings (semantic memory with vector index)
-- Schema matches AsyncCockroachDBVectorStore expectations.
-- org_id, content_type, content_id are stored in the metadata JSONB column.
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT,
    embedding VECTOR(3072),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- C-SPANN index created by AsyncCockroachDBVectorStore.aapply_vector_index()
-- To create manually: CREATE VECTOR INDEX ON embeddings (embedding vector_cosine_ops);

-- 5. Review Sessions (reviewer memory)
CREATE TABLE IF NOT EXISTS review_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documentation(id) ON DELETE CASCADE,
    reviewer_id UUID,
    status STRING DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'needs_changes')),
    reviewer_feedback TEXT,
    edits_made JSONB,
    confidence_before FLOAT CHECK (confidence_before >= 0 AND confidence_before <= 1),
    confidence_after FLOAT CHECK (confidence_after >= 0 AND confidence_after <= 1),
    thread_id STRING,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_review_doc ON review_sessions(doc_id);
CREATE INDEX IF NOT EXISTS idx_review_status ON review_sessions(status);
CREATE INDEX IF NOT EXISTS idx_review_thread ON review_sessions(thread_id);

-- 6. Agent Workflows (procedural memory)
CREATE TABLE IF NOT EXISTS agent_workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    thread_id UUID REFERENCES support_threads(id) ON DELETE SET NULL,
    doc_id UUID REFERENCES documentation(id) ON DELETE SET NULL,
    graph_state JSONB NOT NULL,
    current_node STRING,
    status STRING DEFAULT 'running' CHECK (status IN ('running', 'paused', 'completed', 'failed')),
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now() ON UPDATE now()
);

CREATE INDEX IF NOT EXISTS idx_workflow_org ON agent_workflows(org_id);
CREATE INDEX IF NOT EXISTS idx_workflow_status ON agent_workflows(status);

-- 7. Agent Memory (organizational knowledge)
CREATE TABLE IF NOT EXISTS agent_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    memory_type STRING NOT NULL CHECK (memory_type IN ('episodic', 'procedural', 'organizational', 'reviewer')),
    key STRING NOT NULL,
    value JSONB NOT NULL,
    source TEXT,
    confidence FLOAT DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMPTZ DEFAULT now(),
    last_accessed TIMESTAMPTZ,
    UNIQUE (org_id, key)
);

CREATE INDEX IF NOT EXISTS idx_memory_org ON agent_memory(org_id);
CREATE INDEX IF NOT EXISTS idx_memory_type ON agent_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_key ON agent_memory(key);

-- 8. Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    actor STRING NOT NULL CHECK (actor IN ('agent', 'human', 'system')),
    actor_id STRING,
    action STRING NOT NULL,
    resource_type STRING,
    resource_id UUID,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_org ON audit_logs(org_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);

-- 9. Reviewers (notification recipients)
CREATE TABLE IF NOT EXISTS reviewers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    name STRING NOT NULL,
    email STRING,
    slack_user_id STRING,
    discord_user_id STRING,
    clerk_user_id STRING,
    notify_slack BOOL DEFAULT true,
    notify_discord BOOL DEFAULT false,
    notify_email BOOL DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now() ON UPDATE now()
);

CREATE INDEX IF NOT EXISTS idx_reviewers_org ON reviewers(org_id);
CREATE INDEX IF NOT EXISTS idx_reviewers_active ON reviewers(is_active);
CREATE INDEX IF NOT EXISTS idx_reviewers_clerk_user ON reviewers(clerk_user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewers_email_org ON reviewers(org_id, email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewers_slack_org ON reviewers(org_id, slack_user_id) WHERE slack_user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewers_discord_org ON reviewers(org_id, discord_user_id) WHERE discord_user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewers_clerk_user_org ON reviewers(org_id, clerk_user_id) WHERE clerk_user_id IS NOT NULL;

-- 10. GitHub Installations (App installation data)
CREATE TABLE IF NOT EXISTS github_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    installation_id INT NOT NULL UNIQUE,
    github_org STRING NOT NULL,
    repositories JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now() ON UPDATE now()
);

CREATE INDEX IF NOT EXISTS idx_installations_org ON github_installations(org_id);
CREATE INDEX IF NOT EXISTS idx_installations_github_org ON github_installations(github_org);

-- 11. GitHub Workflows (pipeline runs triggered by GitHub issues)
CREATE TABLE IF NOT EXISTS github_workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL,
    installation_id INT NOT NULL,
    owner STRING NOT NULL,
    repo STRING NOT NULL,
    issue_number INT NOT NULL,
    status STRING DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_github_workflows_status ON github_workflows(status);
CREATE INDEX IF NOT EXISTS idx_github_workflows_issue ON github_workflows(owner, repo, issue_number);

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
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    role STRING NOT NULL DEFAULT 'org:member',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, org_id)
);

CREATE INDEX IF NOT EXISTS idx_user_org_user ON user_organizations(user_id);
CREATE INDEX IF NOT EXISTS idx_user_org_org ON user_organizations(org_id);

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

CREATE INDEX IF NOT EXISTS idx_slack_installations_org ON slack_installations(org_id);
CREATE INDEX IF NOT EXISTS idx_slack_installations_team ON slack_installations(team_id);

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

CREATE INDEX IF NOT EXISTS idx_slack_workflows_status ON slack_workflows(status);
CREATE INDEX IF NOT EXISTS idx_slack_workflows_thread ON slack_workflows(channel_id, thread_ts);

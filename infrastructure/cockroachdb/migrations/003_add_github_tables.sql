-- Migration: Add GitHub App tables
-- Date: 2025-07-19

-- 10. GitHub Installations (App installation data)
CREATE TABLE IF NOT EXISTS github_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    installation_id INT NOT NULL UNIQUE,
    github_org STRING NOT NULL,
    repositories JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now() ON UPDATE now()
);

CREATE INDEX idx_installations_org ON github_installations(org_id);
CREATE INDEX idx_installations_github_org ON github_installations(github_org);

-- 11. GitHub Workflows (pipeline runs triggered by GitHub issues)
CREATE TABLE IF NOT EXISTS github_workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL,
    installation_id INT NOT NULL,
    owner STRING NOT NULL,
    repo STRING NOT NULL,
    issue_number INT NOT NULL,
    status STRING DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_github_workflows_status ON github_workflows(status);
CREATE INDEX idx_github_workflows_issue ON github_workflows(owner, repo, issue_number);

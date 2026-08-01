-- Migration 013: Loop Engineering — trace collection, improvement proposals, versioned config

CREATE TABLE IF NOT EXISTS agent_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    workflow_id STRING NOT NULL,
    trace_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_traces_org_created ON agent_traces (org_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_traces_workflow ON agent_traces (workflow_id);

CREATE TABLE IF NOT EXISTS harness_improvements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    improvement_type STRING NOT NULL,
    proposed_changes JSONB NOT NULL,
    rationale STRING,
    status STRING DEFAULT 'pending',
    reviewed_by STRING,
    reviewed_at TIMESTAMPTZ,
    review_reason STRING,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_harness_improvements_org_status ON harness_improvements (org_id, status);

CREATE TABLE IF NOT EXISTS prompt_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    node_name STRING NOT NULL,
    prompt_text STRING NOT NULL,
    version INT NOT NULL,
    is_active BOOLEAN DEFAULT false,
    performance_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_prompt_versions_org_node ON prompt_versions (org_id, node_name);

CREATE TABLE IF NOT EXISTS rubric_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    criterion_name STRING NOT NULL,
    criterion_text STRING NOT NULL,
    version INT NOT NULL,
    is_active BOOLEAN DEFAULT false,
    performance_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rubric_versions_org_criterion ON rubric_versions (org_id, criterion_name);

CREATE TABLE IF NOT EXISTS tool_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id STRING NOT NULL REFERENCES organizations(clerk_org_id) ON DELETE CASCADE,
    name STRING NOT NULL,
    description STRING NOT NULL,
    implementation_type STRING NOT NULL,
    config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT true,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tool_configs_org_name ON tool_configs (org_id, name);

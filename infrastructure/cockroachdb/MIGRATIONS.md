# Schema Migration — Jul 20

## Context
- Fresh CockroachDB cluster: `draftly-29343`
- Connection: `postgresql://bonnie:zOTH6O1DZkroKlDAZ-Xwnw@draftly-29343.j77.aws-eu-west-2.cockroachlabs.cloud:26257/draftly-ai?sslmode=verify-full`

## Schema
`infrastructure/cockroachdb/schema.sql` — 11 tables, all using `clerk_org_id` as FK reference.

## Migration Log

### Jul 20 — Initial schema
```bash
psql "$COCKROACHDB_URL" -f infrastructure/cockroachdb/schema.sql
```
Tables created: organizations, support_threads, documentation, embeddings, review_sessions, agent_workflows, agent_memory, audit_logs, reviewers, github_installations, github_workflows.

### Aug 2 — Migration 016 (memory domains)
```bash
psql "$COCKROACHDB_URL" -f infrastructure/cockroachdb/migrations/016_add_memory_domains.sql
```
Adds the memory domain tables (episodes, reflections, memory_links, user_preferences, evaluation_results, agent_trace_nodes), promotes embeddings metadata (org_id, content_type, content_id, workflow_id) from the JSONB metadata column to real indexed columns with a backfill, and restores the `UNIQUE (org_id, key)` constraint on agent_memory that migration 007 dropped — required for the `store_memory` upsert. Re-running is safe: all DDL is `IF NOT EXISTS`. The migration dedups agent_memory first (keeping the most recent row per `(org_id, key)`) so the unique constraint can be restored.

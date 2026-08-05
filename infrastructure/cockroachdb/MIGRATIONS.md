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

### Aug 5 — Migration 017 (trace node FK)
```bash
psql "$COCKROACHDB_URL" -f infrastructure/cockroachdb/migrations/017_add_trace_node_fk.sql
```
Adds `agent_trace_nodes.trace_id → agent_traces(id)` with `ON DELETE CASCADE` so the retention purge of `agent_traces` no longer orphans node rows. A pre-cleanup `DELETE` removes existing orphans so the FK add is safe on live data. The FK lives only in this migration (`schema.sql` does not define `agent_traces` — that table comes from migration 013).

### Aug 5 — Migration 018 (memory version archive)
```bash
psql "$COCKROACHDB_URL" -f infrastructure/cockroachdb/migrations/018_add_memory_versions.sql
```
Adds `agent_memory_versions`, an archive of `agent_memory` pre-images written atomically by the `store_memory` upsert CTE. `agent_memory` remains the single current row (`UNIQUE (org_id, key)` intact); history is read via `GET /api/memory/versions`. Re-running is safe: all DDL is `IF NOT EXISTS`.

### Aug 5 — Migration 019 (embeddings org_id cleanup)
```bash
psql "$COCKROACHDB_URL" -f infrastructure/cockroachdb/migrations/019_embeddings_org_id_cleanup.sql
```
Backfills `embeddings.org_id` for `documentation`/`support_threads` rows from the source tables (join on `content_id`), deletes rows still NULL (unreachable dead weight), then sets `org_id NOT NULL`. Every write path already supplies `org_id`, so the constraint is safe. Re-running is safe.

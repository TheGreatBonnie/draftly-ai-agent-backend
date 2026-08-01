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

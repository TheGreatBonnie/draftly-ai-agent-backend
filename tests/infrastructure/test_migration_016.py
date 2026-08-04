from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parent.parent.parent
    / "infrastructure/cockroachdb/migrations/016_add_memory_domains.sql"
)


def test_migration_016_defines_all_tables_idempotently():
    assert MIGRATION.exists()
    sql = MIGRATION.read_text()

    for table in (
        "episodes",
        "reflections",
        "memory_links",
        "user_preferences",
        "evaluation_results",
        "agent_trace_nodes",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql

    assert "ADD COLUMN IF NOT EXISTS org_id" in sql
    assert "ADD COLUMN IF NOT EXISTS content_type" in sql
    assert "ADD COLUMN IF NOT EXISTS content_id" in sql
    assert "ADD COLUMN IF NOT EXISTS workflow_id" in sql
    assert "CREATE INDEX IF NOT EXISTS" in sql
    assert "DELETE FROM agent_memory" in sql
    assert (
        "ADD CONSTRAINT IF NOT EXISTS agent_memory_org_id_key UNIQUE (org_id, key)" in sql
    )


def test_schema_sql_stays_in_sync_with_new_tables():
    schema = (
        Path(__file__).resolve().parent.parent.parent
        / "infrastructure/cockroachdb/schema.sql"
    ).read_text()
    assert "CREATE TABLE IF NOT EXISTS episodes" in schema
    assert "CREATE TABLE IF NOT EXISTS reflections" in schema
    assert "CREATE TABLE IF NOT EXISTS memory_links" in schema
    assert "CREATE TABLE IF NOT EXISTS agent_trace_nodes" in schema

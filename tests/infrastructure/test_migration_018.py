from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parent.parent.parent
    / "infrastructure/cockroachdb/migrations/018_add_memory_versions.sql"
)


def test_migration_018_defines_versions_table_idempotently():
    assert MIGRATION.exists()
    sql = MIGRATION.read_text()
    assert "CREATE TABLE IF NOT EXISTS agent_memory_versions" in sql
    assert "REFERENCES agent_memory(id) ON DELETE CASCADE" in sql
    assert "CREATE INDEX IF NOT EXISTS" in sql


def test_schema_sql_stays_in_sync_with_versions_table():
    schema = (
        Path(__file__).resolve().parent.parent.parent
        / "infrastructure/cockroachdb/schema.sql"
    ).read_text()
    assert "CREATE TABLE IF NOT EXISTS agent_memory_versions" in schema

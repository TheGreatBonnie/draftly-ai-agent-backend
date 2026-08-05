from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parent.parent.parent
    / "infrastructure/cockroachdb/migrations/019_embeddings_org_id_cleanup.sql"
)


def test_migration_019_cleans_and_restricts_org_id():
    assert MIGRATION.exists()
    sql = MIGRATION.read_text()
    assert "UPDATE embeddings" in sql
    assert "SELECT d.org_id FROM documentation d" in sql
    assert "SELECT s.org_id FROM support_threads s" in sql
    assert "DELETE FROM embeddings WHERE org_id IS NULL" in sql
    assert "SET NOT NULL" in sql


def test_schema_sql_marks_embeddings_org_id_not_null():
    schema = (
        Path(__file__).resolve().parent.parent.parent
        / "infrastructure/cockroachdb/schema.sql"
    ).read_text()
    assert (
        "ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS org_id STRING NOT NULL"
        in schema
    )

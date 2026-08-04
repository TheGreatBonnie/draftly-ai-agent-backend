from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_delete_embeddings_for_content_uses_predicate():
    from src.memory.vector_store import delete_embeddings_for_content

    with patch("src.database.execute", new_callable=AsyncMock) as mock_exec:
        await delete_embeddings_for_content("doc-uuid-123")

    sql = mock_exec.await_args.args[0]
    assert "metadata->>'content_id'" in sql
    assert "content_id = $1" in sql
    assert mock_exec.await_args.args[1] == "doc-uuid-123"


@pytest.mark.asyncio
async def test_store_embedding_writes_promoted_columns():
    from src.memory import vector_store

    mock_store = AsyncMock()
    mock_store.embeddings.aembed_query = AsyncMock(return_value=[0.1, 0.2])

    mock_conn = AsyncMock()
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_engine = MagicMock()
    mock_engine.engine.begin.return_value = begin_ctx

    with patch.object(vector_store, "_engine", mock_engine), patch.object(
        vector_store, "get_vector_store", new_callable=AsyncMock, return_value=mock_store
    ):
        await vector_store.store_embedding(
            org_id="org-1",
            content_type="documentation",
            content_id="doc-1",
            content_text="hello",
        )

    params = mock_conn.execute.await_args.args[1]
    sql = mock_conn.execute.await_args.args[0].text
    assert params["org_id"] == "org-1"
    assert params["content_type"] == "documentation"
    assert params["content_id"] == "doc-1"
    assert "org_id" in sql and "content_id" in sql

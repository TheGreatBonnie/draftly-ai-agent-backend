from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_delete_embeddings_for_content_uses_predicate():
    from src.memory.vector_store import delete_embeddings_for_content

    with patch("src.database.execute", new_callable=AsyncMock) as mock_exec:
        await delete_embeddings_for_content("doc-uuid-123")

    sql = mock_exec.await_args.args[0]
    assert "metadata->>'content_id'" in sql
    assert mock_exec.await_args.args[1] == "doc-uuid-123"

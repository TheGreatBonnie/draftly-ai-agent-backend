from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_delete_embeddings_for_content():
    from src.memory.vector_store import delete_embeddings_for_content

    mock_store = AsyncMock()
    mock_store.asimilarity_search_with_score = AsyncMock(
        return_value=[
            (MagicMock(id="emb-1"), 0.1),
            (MagicMock(id="emb-2"), 0.2),
        ]
    )
    mock_store.adelete = AsyncMock()

    with patch(
        "src.memory.vector_store.get_vector_store",
        new_callable=AsyncMock,
        return_value=mock_store,
    ):
        await delete_embeddings_for_content("doc-uuid-123")
        mock_store.adelete.assert_called_once_with(["emb-1", "emb-2"])


@pytest.mark.asyncio
async def test_ingest_knowledge_stores_chunks():
    """Verify that POST /api/knowledge creates multiple embeddings (chunks)."""
    from src.api.routes.knowledge import ingest_knowledge

    mock_token = {"org_id": "org-test-123"}

    delete_patch = patch(
        "src.api.routes.knowledge.delete_embeddings_for_content",
        new_callable=AsyncMock,
    )
    chunks_patch = patch(
        "src.api.routes.knowledge.store_document_chunks",
        new_callable=AsyncMock,
    )
    with patch("src.api.routes.knowledge.fetch_one", new_callable=AsyncMock) as mock_fetch_one, \
         delete_patch as mock_delete, \
         chunks_patch as mock_chunks:
        mock_fetch_one.return_value = {"id": "doc-uuid-456"}
        mock_chunks.return_value = 5

        request = MagicMock()
        request.title = "Test Doc"
        request.content = "A" * 5000
        request.doc_type = "howto"
        request.source_url = None

        result = await ingest_knowledge(request, token=mock_token)

        assert result["id"] == "doc-uuid-456"
        assert result["status"] == "approved"
        mock_chunks.assert_called_once()
        mock_delete.assert_called_once_with("doc-uuid-456")
        call_kwargs = mock_chunks.call_args[1]
        assert call_kwargs["org_id"] == "org-test-123"
        assert call_kwargs["content_id"] == "doc-uuid-456"
        assert call_kwargs["title"] == "Test Doc"
        assert call_kwargs["content"] == "A" * 5000


@pytest.mark.asyncio
async def test_publish_node_stores_chunks():
    """Verify that publish_node creates multiple embeddings (chunks)."""
    from src.agents.nodes.publish import publish_node

    state = {
        "org_id": "org-test-123",
        "doc_id": "doc-uuid-789",
        "draft_title": "How to Deploy",
        "draft_content": "A" * 5000,
        "doc_type": "howto",
        "confidence_score": 0.9,
        "source": "cli",
        "source_metadata": {},
    }

    chunks_patch = patch(
        "src.agents.nodes.publish.store_document_chunks",
        new_callable=AsyncMock,
    )
    with patch("src.agents.nodes.publish.execute", new_callable=AsyncMock), \
         chunks_patch as mock_chunks, \
         patch("src.agents.nodes.publish.store_memory", new_callable=AsyncMock), \
         patch("src.agents.nodes.publish.store_audit_log", new_callable=AsyncMock):
        mock_chunks.return_value = 5

        await publish_node(state)

        mock_chunks.assert_called_once()
        call_kwargs = mock_chunks.call_args[1]
        assert call_kwargs["org_id"] == "org-test-123"
        assert call_kwargs["content_id"] == "doc-uuid-789"
        assert "How to Deploy" in call_kwargs["title"]
        assert call_kwargs["metadata"]["doc_type"] == "howto"
        assert call_kwargs["metadata"]["confidence"] == 0.9


@pytest.mark.asyncio
async def test_delete_knowledge_removes_all_chunks():
    """Verify that DELETE /api/knowledge/{doc_id} removes all chunk embeddings."""
    from src.api.routes.knowledge import delete_knowledge

    mock_token = {"org_id": "org-test-123"}

    delete_patch = patch(
        "src.api.routes.knowledge.delete_embeddings_for_content",
        new_callable=AsyncMock,
    )
    with patch("src.api.routes.knowledge.fetch_one", new_callable=AsyncMock) as mock_fetch, \
         delete_patch as mock_del, \
         patch("src.api.routes.knowledge.execute", new_callable=AsyncMock):
        mock_fetch.return_value = {"id": "doc-uuid-456"}

        result = await delete_knowledge("doc-uuid-456", token=mock_token)

        assert result["status"] == "deleted"
        mock_del.assert_called_once_with("doc-uuid-456")


def test_chunk_text_short_document():
    """Short documents produce a single chunk."""
    from src.memory.chunking import chunk_text

    text = "Hello world. This is a short document."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_long_document():
    """Long documents produce multiple overlapping chunks."""
    from src.memory.chunking import chunk_text

    text = "This is a sentence about topic A. " * 100
    chunks = chunk_text(text)
    assert len(chunks) >= 2
    combined = " ".join(chunks)
    assert "topic A" in combined


def test_chunk_text_empty():
    """Empty text returns empty list."""
    from src.memory.chunking import chunk_text

    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_preserves_code_blocks():
    """Code blocks are not split mid-line."""
    from src.memory.chunking import chunk_text

    text = (
        "# Title\n\nSome intro text.\n\n```python\n"
        "def hello():\n    print('hello')\n```\n\nConclusion."
    )
    chunks = chunk_text(text)
    combined = " ".join(chunks)
    assert "def hello():" in combined
    assert "Conclusion." in combined

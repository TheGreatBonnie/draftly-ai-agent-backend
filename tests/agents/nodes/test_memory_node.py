from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_memory_retrieve_uses_hybrid_search_and_keeps_shape():
    from src.agents.nodes.memory import memory_retrieve_node

    hybrid = [
        {"id": "1", "content_type": "documentation", "content_id": "doc-1",
         "content_text": "a", "metadata": {}, "similarity": 0.9},
    ]
    with patch(
        "src.agents.nodes.memory.hybrid_search", new_callable=AsyncMock, return_value=hybrid
    ) as mock_hybrid, patch(
        "src.agents.nodes.memory.search_threads", new_callable=AsyncMock, return_value=[]
    ), patch(
        "src.agents.nodes.memory.search_memory", new_callable=AsyncMock, return_value=[]
    ), patch(
        "src.agents.nodes.memory.get_reviewer_memory", new_callable=AsyncMock, return_value=[]
    ):
        result = await memory_retrieve_node({"org_id": "org-1", "question": "how to deploy"})

    mock_hybrid.assert_awaited_once_with("org-1", "how to deploy", k=10, days=None)
    assert result["existing_docs"] == hybrid
    assert result["semantic_context"] == hybrid
    assert result["similar_threads"] == []
    assert result["reviewer_feedback_history"] == []


@pytest.mark.asyncio
async def test_memory_retrieve_excludes_non_documentation_from_existing_docs():
    from src.agents.nodes.memory import memory_retrieve_node

    hybrid = [
        {"id": "1", "content_type": "documentation", "content_id": "doc-1",
         "content_text": "a", "metadata": {}, "similarity": 0.9},
        {"id": "2", "content_type": "knowledge", "content_id": "k-1",
         "content_text": "c", "metadata": {}, "similarity": 0.5},
    ]
    with patch(
        "src.agents.nodes.memory.hybrid_search", new_callable=AsyncMock, return_value=hybrid
    ) as mock_hybrid, patch(
        "src.agents.nodes.memory.search_threads", new_callable=AsyncMock, return_value=[]
    ), patch(
        "src.agents.nodes.memory.search_memory", new_callable=AsyncMock, return_value=[]
    ), patch(
        "src.agents.nodes.memory.get_reviewer_memory", new_callable=AsyncMock, return_value=[]
    ):
        result = await memory_retrieve_node({"org_id": "org-1", "question": "how to deploy"})

    mock_hybrid.assert_awaited_once_with("org-1", "how to deploy", k=10, days=None)
    assert len(result["existing_docs"]) == 1
    assert result["existing_docs"][0]["content_id"] == "doc-1"
    assert len(result["semantic_context"]) == 2

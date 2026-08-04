from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_hybrid_search_filters_by_org_and_dedupes():
    from src.memory import vector_store

    rows = [
        {"id": "1", "content_type": "documentation", "content_id": "doc-1",
         "content": "a", "metadata": {}, "similarity": 0.9},
        {"id": "2", "content_type": "documentation", "content_id": "doc-1",
         "content": "b", "metadata": {}, "similarity": 0.7},
        {"id": "3", "content_type": "knowledge", "content_id": "k-1",
         "content": "c", "metadata": {}, "similarity": 0.5},
    ]
    with patch.object(
        vector_store, "embed_text", new_callable=AsyncMock, return_value=[0.1, 0.2]
    ), patch(
        "src.database.fetch_all", new_callable=AsyncMock, return_value=rows
    ) as mock_fetch:
        results = await vector_store.hybrid_search(
            "org-1", "how to deploy", content_types=["documentation"], k=10, days=180
        )

    assert len(results) == 2  # doc-1 deduped, k-1 kept
    sql = mock_fetch.await_args.args[0]
    assert "org_id = $1" in sql
    assert "content_type = ANY" in sql
    assert "<=>" in sql
    assert "LIMIT" in sql
    assert results[0]["similarity"] == 0.9


@pytest.mark.asyncio
async def test_hybrid_search_requires_org_filter():
    from src.memory import vector_store

    with patch.object(
        vector_store, "embed_text", new_callable=AsyncMock, return_value=[0.1]
    ), patch(
        "src.database.fetch_all", new_callable=AsyncMock, return_value=[]
    ) as mock_fetch:
        await vector_store.hybrid_search("org-1", "q")

    sql = mock_fetch.await_args.args[0]
    assert sql.count("$1") >= 1  # org_id always bound


@pytest.mark.asyncio
async def test_hybrid_search_parses_metadata_and_allows_days_none():
    from src.memory import vector_store

    rows = [
        {"id": "1", "content_type": "documentation", "content_id": "doc-1",
         "content": "a", "metadata": '{"k": "v"}', "similarity": 0.9},
    ]
    with patch.object(
        vector_store, "embed_text", new_callable=AsyncMock, return_value=[0.1]
    ), patch(
        "src.database.fetch_all", new_callable=AsyncMock, return_value=rows
    ) as mock_fetch:
        results = await vector_store.hybrid_search(
            "org-1", "q", k=5, days=None
        )

    assert results[0]["metadata"] == {"k": "v"}  # raw JSON string parsed to dict
    args = mock_fetch.await_args
    assert args.args[2] is None  # days param is None
    assert "$3::INT IS NULL" in args.args[0]

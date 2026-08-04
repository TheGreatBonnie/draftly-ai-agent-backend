from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_store_episode_returns_id():
    from src.memory.episodes import store_episode

    with patch("src.memory.episodes.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"id": "ep-1"}
        result = await store_episode(
            org_id="org-1",
            workflow_id="w-1",
            source="slack",
            input_summary="how to deploy",
            outcome="published",
            quality_score=0.9,
        )
    assert result == "ep-1"
    sql = mock_fetch.await_args.args[0]
    assert "INSERT INTO episodes" in sql


@pytest.mark.asyncio
async def test_store_episode_aligns_params_and_encodes_jsonb():
    import json

    from src.memory.episodes import store_episode

    with patch("src.memory.episodes.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"id": "ep-1"}
        result = await store_episode(
            org_id="org-1",
            workflow_id="w-1",
            source="slack",
            input_summary="how to deploy",
            outcome="published",
            quality_score=0.9,
            evidence_ids=["a", "b"],
        )

    assert result == "ep-1"
    args = mock_fetch.await_args.args
    sql = " ".join(args[0].split())
    assert (
        "org_id, workflow_id, thread_id, source, input_summary, evidence_ids,"
        " doc_id, outcome, quality_score, duration_ms, token_usage" in sql
    )
    assert "$6::jsonb" in sql
    assert args[1] == "org-1"
    assert args[2] == "w-1"
    assert args[3] is None
    assert args[4] == "slack"
    assert args[5] == "how to deploy"
    assert args[6] == json.dumps(["a", "b"])
    assert args[7] is None
    assert args[8] == "published"
    assert args[9] == 0.9
    assert args[10] is None
    assert args[11] is None


@pytest.mark.asyncio
async def test_store_episode_raises_when_row_missing():
    from src.memory.episodes import store_episode

    with patch("src.memory.episodes.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = None
        with pytest.raises(RuntimeError):
            await store_episode(
                org_id="org-1",
                workflow_id="w-1",
                source="slack",
                input_summary="how to deploy",
                outcome="published",
            )

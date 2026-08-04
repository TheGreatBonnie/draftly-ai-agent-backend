from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_reflect_writes_lesson_for_published_run():
    from src.agents.nodes.reflect import reflect_node

    state = {
        "org_id": "org-1",
        "episode_id": "ep-1",
        "question": "how to deploy",
        "confidence_score": 0.9,
        "published_urls": [{"platform": "draftly"}],
        "human_feedback": "",
    }

    parsed = type("R", (), {"lesson": "Deploy via CLI", "confidence": 0.8, "tags": ["deploy"]})()
    with patch(
        "src.agents.nodes.reflect.call_llm_structured",
        new_callable=AsyncMock,
        return_value=(parsed, ""),
    ), patch(
        "src.agents.nodes.reflect.store_reflection",
        new_callable=AsyncMock,
        return_value="ref-1",
    ) as mock_ref, patch(
        "src.agents.nodes.reflect.link_episode_reflection", new_callable=AsyncMock
    ) as mock_link:
        result = await reflect_node(state)

    assert result["_reflected"] is True
    mock_ref.assert_awaited_once_with("org-1", "ep-1", "Deploy via CLI", 0.8, ["deploy"])
    mock_link.assert_awaited_once_with("org-1", "ep-1", "ref-1")


@pytest.mark.asyncio
async def test_reflect_runs_for_failed_run():
    from src.agents.nodes.reflect import reflect_node

    state = {
        "org_id": "org-1",
        "episode_id": "ep-2",
        "question": "why is deploy broken",
        "confidence_score": 0.2,
        "published_urls": [],
        "human_feedback": "incomplete",
    }

    parsed = type("R", (), {"lesson": "Check env first", "confidence": 0.4, "tags": []})()
    with patch(
        "src.agents.nodes.reflect.call_llm_structured",
        new_callable=AsyncMock,
        return_value=(parsed, ""),
    ), patch(
        "src.agents.nodes.reflect.store_reflection",
        new_callable=AsyncMock,
        return_value="ref-2",
    ) as mock_ref, patch(
        "src.agents.nodes.reflect.link_episode_reflection", new_callable=AsyncMock
    ):
        result = await reflect_node(state)

    assert result["_reflected"] is True
    mock_ref.assert_awaited_once()


@pytest.mark.asyncio
async def test_reflect_skips_when_no_episode():
    from src.agents.nodes.reflect import reflect_node

    with patch(
        "src.agents.nodes.reflect.call_llm_structured", new_callable=AsyncMock
    ) as mock_llm, patch(
        "src.agents.nodes.reflect.store_reflection", new_callable=AsyncMock
    ) as mock_ref:
        result = await reflect_node({"org_id": "org-1"})

    assert result["_reflected"] is True
    mock_llm.assert_not_awaited()
    mock_ref.assert_not_awaited()


@pytest.mark.asyncio
async def test_reflect_is_idempotent():
    from src.agents.nodes.reflect import reflect_node

    with patch(
        "src.agents.nodes.reflect.call_llm_structured", new_callable=AsyncMock
    ) as mock_llm:
        result = await reflect_node({"org_id": "o", "episode_id": "e", "_reflected": True})

    assert result["_reflected"] is True
    mock_llm.assert_not_awaited()

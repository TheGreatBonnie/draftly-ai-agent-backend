"""Tests for the CLI workflow runner."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_run_workflow_propagates_workflow_id() -> None:
    """CLI generates a workflow_id, sets it in state, binds contextvars, and backfills."""
    import structlog

    captured: dict = {}
    mock_result = {
        "draft_content": "Draft docs",
        "draft_title": "How-to",
        "doc_id": "doc-1",
        "human_decision": "approved",
    }

    async def fake_ainvoke(state, config):
        captured["state"] = state
        captured["ctx"] = structlog.contextvars.get_contextvars()
        assert state["rubric_evaluations"] == []
        assert state["rubric_feedback"] == ""
        return mock_result

    with (
        patch("src.database.get_pool", new_callable=AsyncMock),
        patch("src.database.close_pool", new_callable=AsyncMock),
        patch("src.analytics.events.start_flusher", new_callable=AsyncMock),
        patch("src.analytics.events.stop_flusher", new_callable=AsyncMock),
        patch(
            "src.memory.organizations.link_workflow_to_document",
            new_callable=AsyncMock,
        ) as mock_link,
        patch("src.cli.draftly.create_checkpointer") as MockFactory,
        patch("src.cli.draftly.build_hybrid_graph") as mock_build,
    ):
        mock_checkpointer = AsyncMock()
        mock_checkpointer.setup = AsyncMock()
        mock_graph = AsyncMock()
        mock_graph.ainvoke = fake_ainvoke
        mock_saver_instance = AsyncMock()
        mock_saver_instance.__aenter__ = AsyncMock(return_value=mock_checkpointer)
        mock_saver_instance.__aexit__ = AsyncMock(return_value=False)
        MockFactory.return_value = mock_saver_instance
        mock_build.return_value.compile.return_value = mock_graph

        from src.cli.draftly import run_workflow

        result = await run_workflow(question="How do I reset?", org_id="org-1")

    assert result == mock_result
    assert captured["state"]["workflow_id"] != ""
    assert captured["ctx"].get("workflow_id") == captured["state"]["workflow_id"]
    assert captured["ctx"].get("org_id") == "org-1"
    mock_link.assert_awaited_once()
    assert mock_link.await_args.args == (captured["state"]["workflow_id"], "doc-1")
    assert "workflow_id" not in structlog.contextvars.get_contextvars()


@pytest.mark.asyncio
async def test_run_workflow_requires_org_id() -> None:
    """CLI exits when org_id is missing."""
    from src.cli.draftly import run_workflow

    with pytest.raises(SystemExit):
        await run_workflow(question="hi", org_id=None)

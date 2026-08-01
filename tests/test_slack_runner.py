"""Tests for Slack pipeline runner."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.runners.slack_runner import build_slack_state


class TestBuildSlackState:
    """Tests for building Slack state from message event data."""

    def test_build_slack_state_basic(self) -> None:
        state = build_slack_state(
            team_id="T123",
            channel="C456",
            thread_ts="1234567890.123",
            ts="1234567890.123",
            text="How do I configure webhooks?",
            user="U789",
            org_id="org-1",
        )
        assert state["org_id"] == "org-1"
        assert state["source"] == "slack"
        assert state["channel_id"] == "C456"
        assert state["thread_id"] == "1234567890.123"
        assert state["question"] == "How do I configure webhooks?"

    def test_build_slack_state_source_metadata(self) -> None:
        state = build_slack_state(
            team_id="T123",
            channel="C456",
            thread_ts="999.888",
            ts="999.888",
            text="Help",
            user="U789",
            org_id="org-1",
        )
        metadata = state["source_metadata"]
        assert metadata["team_id"] == "T123"
        assert metadata["channel"] == "C456"
        assert metadata["thread_ts"] == "999.888"
        assert metadata["ts"] == "999.888"
        assert metadata["user_id"] == "U789"

    def test_build_slack_state_initializes_defaults(self) -> None:
        state = build_slack_state(
            team_id="T1",
            channel="C1",
            thread_ts="1.1",
            ts="1.1",
            text="test",
            user="U1",
            org_id="org-1",
        )
        assert state["similar_threads"] == []
        assert state["existing_docs"] == []
        assert state["reviewer_feedback_history"] == []
        assert state["semantic_context"] == []
        assert state["github_context"] == []
        assert state["slack_context"] == []
        assert state["knowledge_package"] == {}
        assert state["draft_content"] == ""
        assert state["draft_title"] == ""
        assert state["doc_type"] == "howto"
        assert state["confidence_score"] == 0.0
        assert state["review_result"] == {}
        assert state["review_feedback"] == ""
        assert state["rubric_feedback"] == ""
        assert state["rubric_evaluations"] == []
        assert state["human_decision"] == ""
        assert state["human_feedback"] == ""
        assert state["published_urls"] == []
        assert state["messages"] == []

    def test_build_slack_state_graph_thread_id(self) -> None:
        state = build_slack_state(
            team_id="T99",
            channel="C88",
            thread_ts="777.666",
            ts="777.666",
            text="question",
            user="U55",
            org_id="org-2",
        )
        assert state["graph_thread_id"] == "slack-C88-777.666"


@pytest.mark.asyncio
async def test_run_slack_pipeline_propagates_workflow_id() -> None:
    """Runner sets state.workflow_id, binds contextvars, and backfills doc link."""
    import structlog

    captured: dict = {}
    mock_result = {"draft_content": "Draft docs", "human_decision": "approved", "doc_id": "doc-1"}

    async def fake_ainvoke(state, config):
        captured["state"] = state
        captured["ctx"] = structlog.contextvars.get_contextvars()
        return mock_result

    with (
        patch("src.database.get_pool", new_callable=AsyncMock),
        patch(
            "src.memory.organizations.get_org_by_slack",
            new_callable=AsyncMock,
        ) as mock_get_org,
        patch(
            "src.integrations.slack_mcp.get_slack_mcp_tools",
            new_callable=AsyncMock,
        ),
        patch(
            "src.integrations.slack_store.installation_store.async_find_installation",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "src.memory.organizations.store_slack_workflow",
            new_callable=AsyncMock,
        ),
        patch(
            "src.memory.organizations.update_slack_workflow_status",
            new_callable=AsyncMock,
        ),
        patch(
            "src.memory.organizations.link_workflow_to_document",
            new_callable=AsyncMock,
        ) as mock_link,
        patch(
            "src.agents.runners.slack_runner.AsyncCockroachDBSaver",
        ) as MockSaver,
        patch("src.agents.runners.slack_runner.build_hybrid_graph") as mock_build,
        patch(
            "src.integrations.slack_conversation.conversation_store.add_message",
            new_callable=AsyncMock,
        ),
    ):
        mock_get_org.return_value = {"id": "org1", "name": "Test Org"}

        mock_checkpointer = AsyncMock()
        mock_checkpointer.setup = AsyncMock()
        mock_graph = AsyncMock()
        mock_graph.ainvoke = fake_ainvoke
        mock_saver_instance = AsyncMock()
        mock_saver_instance.__aenter__ = AsyncMock(return_value=mock_checkpointer)
        mock_saver_instance.__aexit__ = AsyncMock(return_value=False)
        MockSaver.from_conn_string.return_value = mock_saver_instance
        mock_build.return_value.compile.return_value = mock_graph

        from src.agents.runners.slack_runner import run_slack_pipeline

        await run_slack_pipeline(
            team_id="T123",
            channel="C456",
            thread_ts="1234567890.123",
            ts="1234567890.123",
            text="How do I configure webhooks?",
            user="U789",
        )

    assert captured["state"]["workflow_id"] != ""
    assert captured["ctx"].get("workflow_id") == captured["state"]["workflow_id"]
    assert captured["ctx"].get("org_id") == "org1"
    mock_link.assert_awaited_once()
    assert mock_link.await_args.args == (captured["state"]["workflow_id"], "doc-1")
    assert "workflow_id" not in structlog.contextvars.get_contextvars()

"""Tests for discord_runner — state builder + pipeline orchestration."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.runners.discord_runner import build_discord_state


def test_build_discord_state_minimal() -> None:
    """State contains source='discord' and correct graph_thread_id."""
    state = build_discord_state(
        guild_id="g1",
        channel_id="ch1",
        message_id="msg1",
        thread_id=None,
        text="How do I reset?",
        user_id="user1",
        org_id="org1",
    )
    assert state["source"] == "discord"
    assert state["graph_thread_id"] == "discord-ch1-msg1"
    assert state["question"] == "How do I reset?"
    assert state["org_id"] == "org1"
    assert state["source_metadata"]["guild_id"] == "g1"
    assert state["rubric_feedback"] == ""
    assert state["rubric_evaluations"] == []


def test_build_discord_state_with_thread() -> None:
    """graph_thread_id uses message_id when thread_id is provided."""
    state = build_discord_state(
        guild_id="g1",
        channel_id="ch1",
        message_id="msg1",
        thread_id="thread1",
        text="Hello",
        user_id="user1",
        org_id="org1",
    )
    assert state["thread_id"] == "thread1"
    assert state["source_metadata"]["thread_id"] == "thread1"


@pytest.mark.asyncio
async def test_run_discord_pipeline_org_not_found() -> None:
    """Pipeline sends error message when org is not linked."""
    with (
        patch("src.database.get_pool", new_callable=AsyncMock),
        patch(
            "src.memory.organizations.get_org_by_discord",
            new_callable=AsyncMock,
        ) as mock_get_org,
        patch(
            "src.integrations.discord.send_discord_message",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        mock_get_org.return_value = None
        from src.agents.runners.discord_runner import run_discord_pipeline

        await run_discord_pipeline(
            guild_id="g1",
            channel_id="ch1",
            message_id="msg1",
            thread_id=None,
            text="Hello",
            user_id="user1",
        )
        mock_send.assert_called_once()
        assert "not linked" in mock_send.call_args[0][1]


@pytest.mark.asyncio
async def test_run_discord_pipeline_calls_graph() -> None:
    """Pipeline builds state and invokes the graph with a checkpointer."""
    mock_result = {"draft_content": "Draft docs", "human_decision": "approved"}

    with (
        patch("src.database.get_pool", new_callable=AsyncMock),
        patch(
            "src.memory.organizations.get_org_by_discord",
            new_callable=AsyncMock,
        ) as mock_get_org,
        patch(
            "src.memory.organizations.store_discord_workflow",
            new_callable=AsyncMock,
        ),
        patch(
            "src.memory.organizations.update_discord_workflow_status",
            new_callable=AsyncMock,
        ),
        patch(
            "src.integrations.discord.send_discord_thread_reply",
            new_callable=AsyncMock,
        ) as mock_reply,
    ):
        mock_get_org.return_value = {"id": "org1", "name": "Test Org"}

        # Mock the checkpointer context manager
        mock_checkpointer = AsyncMock()
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = mock_result
        mock_checkpointer.setup = AsyncMock()

        with (
            patch(
                "src.agents.runners.discord_runner.create_checkpointer"
            ) as MockFactory,
            patch("src.agents.runners.discord_runner.build_hybrid_graph") as mock_build,
        ):
            mock_saver_instance = AsyncMock()
            mock_saver_instance.__aenter__ = AsyncMock(
                return_value=mock_checkpointer
            )
            mock_saver_instance.__aexit__ = AsyncMock(return_value=False)
            MockFactory.return_value = mock_saver_instance
            mock_build.return_value.compile.return_value = mock_graph

            from src.agents.runners.discord_runner import run_discord_pipeline

            await run_discord_pipeline(
                guild_id="g1",
                channel_id="ch1",
                message_id="msg1",
                thread_id="thread1",
                text="How do I reset?",
                user_id="user1",
            )

        # Runner should NOT send draft reply — publish_node handles that
        mock_reply.assert_not_called()


@pytest.mark.asyncio
async def test_run_discord_pipeline_propagates_workflow_id() -> None:
    """Runner sets state.workflow_id, binds contextvars, and backfills doc link."""
    import structlog

    captured: dict = {}
    mock_result = {
        "draft_content": "Draft docs",
        "human_decision": "approved",
        "doc_id": "doc-1",
    }

    async def fake_ainvoke(state, config):
        captured["state"] = state
        captured["ctx"] = structlog.contextvars.get_contextvars()
        return mock_result

    with (
        patch("src.database.get_pool", new_callable=AsyncMock),
        patch(
            "src.memory.organizations.get_org_by_discord",
            new_callable=AsyncMock,
        ) as mock_get_org,
        patch(
            "src.memory.organizations.store_discord_workflow",
            new_callable=AsyncMock,
        ),
        patch(
            "src.memory.organizations.update_discord_workflow_status",
            new_callable=AsyncMock,
        ),
        patch(
            "src.memory.organizations.link_workflow_to_document",
            new_callable=AsyncMock,
        ) as mock_link,
    ):
        mock_get_org.return_value = {"id": "org1", "name": "Test Org"}

        mock_checkpointer = AsyncMock()
        mock_checkpointer.setup = AsyncMock()
        mock_graph = AsyncMock()
        mock_graph.ainvoke = fake_ainvoke

        with (
            patch(
                "src.agents.runners.discord_runner.create_checkpointer"
            ) as MockFactory,
            patch("src.agents.runners.discord_runner.build_hybrid_graph") as mock_build,
        ):
            mock_saver_instance = AsyncMock()
            mock_saver_instance.__aenter__ = AsyncMock(
                return_value=mock_checkpointer
            )
            mock_saver_instance.__aexit__ = AsyncMock(return_value=False)
            MockFactory.return_value = mock_saver_instance
            mock_build.return_value.compile.return_value = mock_graph

            from src.agents.runners.discord_runner import run_discord_pipeline

            await run_discord_pipeline(
                guild_id="g1",
                channel_id="ch1",
                message_id="msg1",
                thread_id="thread1",
                text="How do I reset?",
                user_id="user1",
            )

    assert captured["state"]["workflow_id"] != ""
    assert captured["ctx"].get("workflow_id") == captured["state"]["workflow_id"]
    assert captured["ctx"].get("org_id") == "org1"
    mock_link.assert_awaited_once()
    assert mock_link.await_args.args == (captured["state"]["workflow_id"], "doc-1")
    assert "workflow_id" not in structlog.contextvars.get_contextvars()

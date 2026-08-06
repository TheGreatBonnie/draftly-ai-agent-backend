from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.runners.github_runner import build_github_state


def _make_payload(
    issue_number: int = 42,
    title: str = "How to configure webhooks?",
    body: str = "I need help setting up webhooks in my application.",
    repo_full_name: str = "myorg/myrepo",
    repo_id: int = 12345,
    owner: str = "myorg",
    repo_name: str = "myrepo",
    installation_id: int = 99999,
) -> dict:
    return {
        "issue": {"number": issue_number, "title": title, "body": body},
        "repository": {
            "full_name": repo_full_name,
            "id": repo_id,
            "owner": {"login": owner},
            "name": repo_name,
        },
        "installation": {"id": installation_id},
    }


class TestBuildGithubState:
    """Tests for building GitHub state from payload."""

    def test_build_github_state_basic(self):
        """Test building state from basic GitHub issue payload."""
        payload = _make_payload()
        state = build_github_state(payload=payload, org_id="org-123")

        assert state["org_id"] == "org-123"
        assert state["source"] == "github"
        assert state["channel_id"] == "myorg/myrepo"
        assert state["thread_id"] == "42"
        assert "How to configure webhooks?" in state["question"]
        assert "I need help setting up webhooks" in state["question"]

    def test_build_github_state_empty_body(self):
        """Test building state when issue body is empty."""
        payload = _make_payload(
            issue_number=1,
            title="Bug report",
            body="",
            repo_full_name="org/repo",
            repo_id=100,
            owner="org",
            repo_name="repo",
        )
        state = build_github_state(payload=payload, org_id="org-456")

        assert state["question"] == "Bug report\n\n"
        assert state["thread_id"] == "1"

    def test_build_github_state_source_metadata(self):
        """Test that source_metadata is populated correctly."""
        payload = _make_payload(
            issue_number=7,
            installation_id=42424,
            owner="testorg",
            repo_name="testrepo",
        )
        state = build_github_state(payload=payload, org_id="org-1")

        metadata = state["source_metadata"]
        assert metadata["installation_id"] == 42424
        assert metadata["owner"] == "testorg"
        assert metadata["repo"] == "testrepo"
        assert metadata["issue_number"] == 7

    def test_build_github_state_initializes_defaults(self):
        """Test that all required state fields are initialized."""
        payload = _make_payload()
        state = build_github_state(payload=payload, org_id="org-1")

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
        assert state["source_metadata"] == {
            "installation_id": 99999,
            "owner": "myorg",
            "repo": "myrepo",
            "issue_number": 42,
        }


@pytest.mark.asyncio
async def test_run_github_pipeline_propagates_workflow_id() -> None:
    """Runner sets state.workflow_id, binds contextvars, and backfills doc link."""
    import structlog

    captured: dict = {}
    mock_result = {"draft_content": "Draft docs", "human_decision": "approved", "doc_id": "doc-1"}
    payload = _make_payload()

    async def fake_ainvoke(state, config):
        captured["state"] = state
        captured["ctx"] = structlog.contextvars.get_contextvars()
        return mock_result

    with (
        patch("src.database.get_pool", new_callable=AsyncMock),
        patch("src.database.close_pool", new_callable=AsyncMock),
        patch(
            "src.agents.runners.github_runner.get_org_by_github",
            new_callable=AsyncMock,
        ) as mock_get_org,
        patch(
            "src.agents.runners.github_runner.store_github_installation",
            new_callable=AsyncMock,
        ),
        patch(
            "src.agents.runners.github_runner.store_github_workflow",
            new_callable=AsyncMock,
        ),
        patch(
            "src.agents.runners.github_runner.update_github_workflow_status",
            new_callable=AsyncMock,
        ),
        patch(
            "src.agents.runners.github_runner.link_workflow_to_document",
            new_callable=AsyncMock,
        ) as mock_link,
        patch(
            "src.agents.runners.github_runner.create_checkpointer",
        ) as MockFactory,
        patch("src.agents.runners.github_runner.build_hybrid_graph") as mock_build,
    ):
        mock_get_org.return_value = {"id": "org-1", "name": "Test Org"}

        mock_checkpointer = AsyncMock()
        mock_checkpointer.setup = AsyncMock()
        mock_graph = AsyncMock()
        mock_graph.ainvoke = fake_ainvoke
        mock_saver_instance = AsyncMock()
        mock_saver_instance.__aenter__ = AsyncMock(return_value=mock_checkpointer)
        mock_saver_instance.__aexit__ = AsyncMock(return_value=False)
        MockFactory.return_value = mock_saver_instance
        mock_build.return_value.compile.return_value = mock_graph

        from src.agents.runners.github_runner import run_github_pipeline

        await run_github_pipeline(payload, "test-token")

    assert captured["state"]["workflow_id"] != ""
    assert captured["ctx"].get("workflow_id") == captured["state"]["workflow_id"]
    assert captured["ctx"].get("org_id") == "org-1"
    mock_link.assert_awaited_once()
    assert mock_link.await_args.args == (captured["state"]["workflow_id"], "doc-1")
    assert "workflow_id" not in structlog.contextvars.get_contextvars()

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.nodes.human import human_review_node

_HUMAN_MOD = "src.agents.nodes.human"


def _base_state(**overrides) -> dict:
    state = {
        "org_id": "org-1",
        "doc_id": "doc-abc",
        "draft_title": "Test Doc",
        "draft_content": "# Test\n\nContent here.",
        "confidence_score": 0.8,
        "source_type": "github",
        "question": "How do I test?",
        "graph_thread_id": "github-123-5",
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
@patch(f"{_HUMAN_MOD}.store_audit_log", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.notify_reviewers", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.create_review_session", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.get_pending_review_by_doc", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.interrupt")
async def test_first_run_creates_review_and_notifies(
    mock_interrupt,
    mock_get_pending,
    mock_create,
    mock_notify,
    mock_audit,
):
    """On first run, creates a new review session and sends notifications."""
    mock_get_pending.return_value = None
    mock_create.return_value = "review-new-123"
    mock_notify.return_value = {"rev1": {"slack": "sent"}}
    mock_interrupt.return_value = {"decision": "approve"}

    result = await human_review_node(_base_state())

    mock_get_pending.assert_called_once_with("doc-abc")
    mock_create.assert_called_once()
    mock_notify.assert_called_once()
    mock_audit.assert_called_once()
    assert result["human_decision"] == "approve"


@pytest.mark.asyncio
@patch(f"{_HUMAN_MOD}.store_audit_log", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.notify_reviewers", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.create_review_session", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.get_pending_review_by_doc", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.interrupt")
async def test_resume_skips_review_creation_and_notifications(
    mock_interrupt,
    mock_get_pending,
    mock_create,
    mock_notify,
    mock_audit,
):
    """On resume, skips creating a new review and sending notifications."""
    mock_get_pending.return_value = {"id": "review-existing", "status": "approved"}
    mock_interrupt.return_value = {"decision": "approve"}

    result = await human_review_node(_base_state())

    mock_get_pending.assert_called_once_with("doc-abc")
    mock_create.assert_not_called()
    mock_notify.assert_not_called()
    mock_audit.assert_not_called()
    assert result["human_decision"] == "approve"


@pytest.mark.asyncio
@patch(f"{_HUMAN_MOD}.store_audit_log", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.notify_reviewers", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.create_review_session", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.get_pending_review_by_doc", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.interrupt")
async def test_resume_with_reject_decision(
    mock_interrupt,
    mock_get_pending,
    mock_create,
    mock_notify,
    mock_audit,
):
    """On resume with reject, skips side effects and returns reject."""
    mock_get_pending.return_value = {"id": "review-existing", "status": "approved"}
    mock_interrupt.return_value = {"decision": "reject"}

    result = await human_review_node(_base_state())

    mock_create.assert_not_called()
    mock_notify.assert_not_called()
    assert result["human_decision"] == "reject"


@pytest.mark.asyncio
@patch(f"{_HUMAN_MOD}.store_audit_log", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.notify_reviewers", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.create_review_session", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.get_pending_review_by_doc", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.interrupt")
async def test_empty_doc_id_skips_existing_check(
    mock_interrupt,
    mock_get_pending,
    mock_create,
    mock_notify,
    mock_audit,
):
    """When doc_id is empty, treats as first run."""
    mock_create.return_value = "review-new-456"
    mock_notify.return_value = {}
    mock_interrupt.return_value = {"decision": "approve"}

    result = await human_review_node(_base_state(doc_id=""))

    mock_get_pending.assert_not_called()
    mock_create.assert_called_once()
    mock_notify.assert_called_once()
    assert result["human_decision"] == "approve"


@pytest.mark.asyncio
@patch(f"{_HUMAN_MOD}.store_audit_log", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.notify_reviewers", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.create_review_session", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.get_pending_review_by_doc", new_callable=AsyncMock)
@patch(f"{_HUMAN_MOD}.interrupt")
async def test_resume_passes_correct_review_id_to_interrupt(
    mock_interrupt,
    mock_get_pending,
    mock_create,
    mock_notify,
    mock_audit,
):
    """On resume, the existing review_id is passed to interrupt."""
    mock_get_pending.return_value = {"id": "review-existing-789", "status": "pending"}
    mock_interrupt.return_value = {"decision": "approve"}

    await human_review_node(_base_state())

    call_args = mock_interrupt.call_args[0][0]
    assert call_args["review_id"] == "review-existing-789"
    assert call_args["doc_id"] == "doc-abc"

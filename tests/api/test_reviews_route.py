"""Tests for the reviews route get_review linkage."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_review_includes_workflow_id() -> None:
    """get_review SELECTs d.workflow_id so per-draft traces can be fetched."""
    from src.api.routes.reviews import get_review

    row = {
        "id": "review-1",
        "title": "How to reset",
        "content": "body",
        "doc_type": "howto",
        "confidence_score": 0.9,
        "original_question": "question",
        "platform": "slack",
        "workflow_id": "wf-123",
    }
    with patch("src.database.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = row
        result = await get_review("review-1", token={"org_id": "org-1"})

    assert result["workflow_id"] == "wf-123"
    sql = mock_fetch.await_args.args[0]
    assert "d.workflow_id" in sql


@pytest.mark.asyncio
async def test_get_review_none_workflow_id() -> None:
    """Legacy docs (pre-015) expose workflow_id as None, not an error."""
    from src.api.routes.reviews import get_review

    row = {
        "id": "review-2",
        "title": "Legacy",
        "content": "body",
        "doc_type": "howto",
        "confidence_score": 0.5,
        "original_question": "q",
        "platform": "discord",
        "workflow_id": None,
    }
    with patch("src.database.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = row
        result = await get_review("review-2", token={"org_id": "org-1"})

    assert result["workflow_id"] is None

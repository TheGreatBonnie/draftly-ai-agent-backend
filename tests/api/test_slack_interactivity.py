"""Tests for Slack Bolt action handlers (review buttons)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.integrations.slack_app import _handle_review_action


@pytest.mark.asyncio
@patch("src.memory.reviewer.complete_review", new_callable=AsyncMock)
@patch("src.security.tokens.verify_review_token")
async def test_handle_approve_calls_complete_review(
    mock_verify_token: object, mock_complete: AsyncMock
) -> None:
    mock_verify_token.return_value = {"review_id": "review123", "reviewer_id": "U123"}
    action = {"value": "test_token_123"}

    await _handle_review_action(action, "approve_review")

    mock_verify_token.assert_called_once_with("test_token_123")
    mock_complete.assert_called_once_with(
        review_id="review123", status="approved", feedback=None
    )


@pytest.mark.asyncio
@patch("src.memory.reviewer.complete_review", new_callable=AsyncMock)
@patch("src.security.tokens.verify_review_token")
async def test_handle_reject_calls_complete_review(
    mock_verify_token: object, mock_complete: AsyncMock
) -> None:
    mock_verify_token.return_value = {"review_id": "review456", "reviewer_id": "U456"}
    action = {"value": "reject_token_456"}

    await _handle_review_action(action, "reject_review")

    mock_verify_token.assert_called_once_with("reject_token_456")
    mock_complete.assert_called_once_with(
        review_id="review456", status="rejected", feedback=None
    )


@pytest.mark.asyncio
@patch("src.memory.reviewer.complete_review", new_callable=AsyncMock)
@patch("src.security.tokens.verify_review_token")
async def test_handle_revise_calls_complete_review(
    mock_verify_token: object, mock_complete: AsyncMock
) -> None:
    mock_verify_token.return_value = {"review_id": "review789", "reviewer_id": "U789"}
    action = {"value": "revise_token_789"}

    await _handle_review_action(action, "revise_review")

    mock_verify_token.assert_called_once_with("revise_token_789")
    mock_complete.assert_called_once_with(
        review_id="review789", status="needs_changes", feedback=None
    )


@pytest.mark.asyncio
@patch("src.memory.reviewer.complete_review", new_callable=AsyncMock)
@patch("src.security.tokens.verify_review_token")
async def test_invalid_token_skips_complete_review(
    mock_verify_token: object, mock_complete: AsyncMock
) -> None:
    mock_verify_token.return_value = None
    action = {"value": "invalid_token"}

    await _handle_review_action(action, "approve_review")

    mock_complete.assert_not_called()

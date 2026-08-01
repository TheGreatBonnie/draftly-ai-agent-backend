"""Tests for Slack feedback buttons."""
from unittest.mock import AsyncMock, patch

import pytest


def test_build_feedback_blocks_structure():
    from src.integrations.slack_feedback import build_feedback_blocks

    blocks = build_feedback_blocks()
    assert len(blocks) >= 1
    block = blocks[0]
    assert block["type"] == "section"


@pytest.mark.asyncio
async def test_handle_feedback_logs():
    from src.integrations.slack_feedback import handle_feedback

    mock_ack = AsyncMock()
    action = {"value": "good-feedback"}
    body = {"user": {"id": "U123"}}

    with patch("src.integrations.slack_feedback.logger") as mock_logger:
        await handle_feedback(mock_ack, action, body)
        mock_ack.assert_called_once()
        mock_logger.info.assert_called_once()

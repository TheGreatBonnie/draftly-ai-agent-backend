from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.slack import send_slack_message


@pytest.mark.asyncio
@patch("src.integrations.slack.httpx.AsyncClient")
async def test_send_slack_message_with_blocks(mock_client_cls):
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_instance = MagicMock()
    mock_instance.post = AsyncMock(return_value=mock_response)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_instance
    mock_ctx.__aexit__.return_value = False
    mock_client_cls.return_value = mock_ctx

    blocks = [{"type": "header", "text": {"type": "plain_text", "text": "Test"}}]

    await send_slack_message("C123", "Fallback text", blocks=blocks)

    call_kwargs = mock_instance.post.call_args
    assert call_kwargs[1]["json"]["blocks"] == blocks
    assert call_kwargs[1]["json"]["text"] == "Fallback text"
    assert call_kwargs[1]["json"]["channel"] == "C123"


@pytest.mark.asyncio
@patch("src.integrations.slack.httpx.AsyncClient")
async def test_send_slack_message_without_blocks(mock_client_cls):
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_instance = MagicMock()
    mock_instance.post = AsyncMock(return_value=mock_response)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_instance
    mock_ctx.__aexit__.return_value = False
    mock_client_cls.return_value = mock_ctx

    await send_slack_message("C123", "Simple message")

    call_kwargs = mock_instance.post.call_args
    payload = call_kwargs[1]["json"]
    assert payload["text"] == "Simple message"
    assert "blocks" not in payload

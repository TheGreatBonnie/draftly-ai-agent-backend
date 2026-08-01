"""Tests for custom Slack OAuth callback."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
@patch("src.api.routes.slack.httpx.AsyncClient")
@patch("src.api.routes.slack.installation_store")
async def test_oauth_callback_exchanges_code(mock_store: AsyncMock, mock_httpx: AsyncMock) -> None:
    """Callback exchanges authorization code for tokens."""
    from src.api.routes.slack import slack_oauth_callback

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "ok": True,
        "access_token": "xoxb-fake-bot-token",
        "team": {"id": "T12345", "name": "Test Workspace"},
        "bot_user_id": "U_BOT",
        "scope": "chat:write,channels:read",
        "authed_user": {
            "id": "U12345",
            "access_token": "xoxp-fake-user-token",
            "scope": "search:read",
        },
    }
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_httpx.return_value = mock_client

    mock_store.async_save = AsyncMock()

    response = await slack_oauth_callback(code="test_code_123", state="")

    assert response.status_code == 307
    assert "team_id=T12345" in response.headers["location"]
    mock_store.async_save.assert_called_once()

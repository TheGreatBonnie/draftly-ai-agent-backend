"""Tests for Discord API routes (invite-url, link, status)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_invite_url_returns_url() -> None:
    """GET /api/discord/invite-url returns the bot invite URL."""
    from src.api.routes.discord import discord_invite_url

    with patch("src.api.routes.discord.settings") as mock_settings:
        mock_settings.discord_app_id = "1234567890"
        result = await discord_invite_url()

    assert "invite_url" in result
    assert "client_id=1234567890" in result["invite_url"]
    assert "permissions=36932" in result["invite_url"]


@pytest.mark.asyncio
async def test_invite_url_missing_app_id() -> None:
    """GET /api/discord/invite-url returns 500 if app ID not configured."""
    from fastapi import HTTPException

    from src.api.routes.discord import discord_invite_url

    with patch("src.api.routes.discord.settings") as mock_settings:
        mock_settings.discord_app_id = ""
        with pytest.raises(HTTPException) as exc_info:
            await discord_invite_url()
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_link_sets_guild_id() -> None:
    """POST /api/discord/link sets discord_guild_id on the org."""
    from src.api.routes.discord import LinkDiscordRequest, link_discord

    mock_token = {"org_id": "org_123"}

    with patch("src.api.routes.discord.execute", new_callable=AsyncMock) as mock_exec:
        request = LinkDiscordRequest(guild_id="9876543210")
        result = await link_discord(request, mock_token)

    assert result["guild_id"] == "9876543210"
    assert result["status"] == "linked"
    mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_link_no_org() -> None:
    """POST /api/discord/link returns 400 if no org_id in token."""
    from fastapi import HTTPException

    from src.api.routes.discord import LinkDiscordRequest, link_discord

    mock_token = {}

    with patch("src.api.routes.discord.execute", new_callable=AsyncMock):
        request = LinkDiscordRequest(guild_id="9876543210")
        with pytest.raises(HTTPException) as exc_info:
            await link_discord(request, mock_token)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_status_returns_connected() -> None:
    """GET /api/discord/status returns connected=true when guild_id is set."""
    from src.api.routes.discord import discord_status

    mock_token = {"org_id": "org_123"}

    with patch("src.api.routes.discord.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"discord_guild_id": "9876543210"}
        result = await discord_status(mock_token)

    assert result["connected"] is True
    assert result["guild_id"] == "9876543210"


@pytest.mark.asyncio
async def test_status_returns_not_connected() -> None:
    """GET /api/discord/status returns connected=false when no guild_id."""
    from src.api.routes.discord import discord_status

    mock_token = {"org_id": "org_123"}

    with patch("src.api.routes.discord.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"discord_guild_id": None}
        result = await discord_status(mock_token)

    assert result["connected"] is False
    assert result["guild_id"] is None

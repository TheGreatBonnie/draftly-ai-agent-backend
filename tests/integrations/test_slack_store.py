"""Tests for CockroachInstallationStore (Slack Bolt InstallationStore)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from slack_sdk.oauth.installation_store.models.installation import Installation


class MockRow:
    """Dict-like mock that supports __getitem__ and __contains__ for asyncpg Record interface."""

    def __init__(self, data: dict) -> None:
        self._data = data

    def __getitem__(self, key: str) -> object:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)


@pytest.fixture
def installation() -> Installation:
    return Installation(
        team_id="T12345",
        team_name="Test Workspace",
        bot_user_id="U_BOT",
        bot_token="xoxb-fake-bot-token",
        bot_scopes=["chat:write"],
        user_id="U12345",
        user_token="xoxp-fake-user-token",
        user_scopes=["channels:read"],
        token_type="bot",
        installed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def bot_only_installation() -> Installation:
    return Installation(
        team_id="T67890",
        team_name="Bot Only Workspace",
        bot_user_id="U_BOT2",
        bot_token="xoxb-fake-bot-token-2",
        bot_scopes=["chat:write"],
        user_id="U67890",
        token_type="bot",
        installed_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_save_and_find_installation(installation: Installation) -> None:
    from src.integrations.slack_store import CockroachInstallationStore

    store = CockroachInstallationStore()

    mock_execute = AsyncMock(return_value="INSERT 0 1")
    mock_fetchone = AsyncMock(
        return_value=MockRow(
            {
                "team_id": "T12345",
                "team_name": "Test Workspace",
                "bot_user_id": "U_BOT",
                "bot_token": "xoxb-fake-bot-token",
                "bot_scopes": "chat:write",
                "user_id": "U12345",
                "user_token": "xoxp-fake-user-token",
                "user_scopes": "channels:read",
                "token_type": "bot",
                "installed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
        )
    )

    with (
        patch("src.integrations.slack_store.execute", mock_execute),
        patch("src.integrations.slack_store.fetch_one", mock_fetchone),
    ):
        await store.async_save(installation)
        result = await store.async_find_installation(
            enterprise_id=None, team_id="T12345"
        )

    assert result is not None
    assert result.team_id == "T12345"
    assert result.bot_token == "xoxb-fake-bot-token"
    assert result.user_token == "xoxp-fake-user-token"


@pytest.mark.asyncio
async def test_find_installation_returns_none_when_not_found() -> None:
    from src.integrations.slack_store import CockroachInstallationStore

    store = CockroachInstallationStore()
    mock_fetchone = AsyncMock(return_value=None)

    with patch("src.integrations.slack_store.fetch_one", mock_fetchone):
        result = await store.async_find_installation(
            enterprise_id=None, team_id="T_NONEXISTENT"
        )

    assert result is None


@pytest.mark.asyncio
async def test_save_and_find_bot(bot_only_installation: Installation) -> None:
    from src.integrations.slack_store import CockroachInstallationStore

    store = CockroachInstallationStore()

    mock_execute = AsyncMock(return_value="INSERT 0 1")
    mock_fetchone = AsyncMock(
        return_value=MockRow(
            {
                "team_id": "T67890",
                "bot_user_id": "U_BOT2",
                "bot_token": "xoxb-fake-bot-token-2",
                "bot_scopes": "chat:write",
                "installed_at": datetime(2026, 6, 15, tzinfo=timezone.utc),
            }
        )
    )

    with (
        patch("src.integrations.slack_store.execute", mock_execute),
        patch("src.integrations.slack_store.fetch_one", mock_fetchone),
    ):
        await store.async_save(bot_only_installation)
        result = await store.async_find_bot(
            enterprise_id=None, team_id="T67890"
        )

    assert result is not None
    assert result.bot_token == "xoxb-fake-bot-token-2"


@pytest.mark.asyncio
async def test_find_bot_returns_none_when_not_found() -> None:
    from src.integrations.slack_store import CockroachInstallationStore

    store = CockroachInstallationStore()
    mock_fetchone = AsyncMock(return_value=None)

    with patch("src.integrations.slack_store.fetch_one", mock_fetchone):
        result = await store.async_find_bot(
            enterprise_id=None, team_id="T_NONEXISTENT"
        )

    assert result is None


@pytest.mark.asyncio
async def test_delete_installation() -> None:
    from src.integrations.slack_store import CockroachInstallationStore

    store = CockroachInstallationStore()
    mock_execute = AsyncMock(return_value="DELETE 1")

    with patch("src.integrations.slack_store.execute", mock_execute):
        await store.async_delete_installation(
            enterprise_id=None, team_id="T12345"
        )

    mock_execute.assert_called_once()


@pytest.mark.asyncio
async def test_delete_bot() -> None:
    from src.integrations.slack_store import CockroachInstallationStore

    store = CockroachInstallationStore()
    mock_execute = AsyncMock(return_value="DELETE 1")

    with patch("src.integrations.slack_store.execute", mock_execute):
        await store.async_delete_bot(
            enterprise_id=None, team_id="T12345"
        )

    mock_execute.assert_called_once()


@pytest.mark.asyncio
async def test_delete_all() -> None:
    from src.integrations.slack_store import CockroachInstallationStore

    store = CockroachInstallationStore()
    mock_execute = AsyncMock(return_value="DELETE 2")

    with patch("src.integrations.slack_store.execute", mock_execute):
        await store.async_delete_all(enterprise_id=None, team_id="T12345")

    assert mock_execute.call_count == 1


@pytest.mark.asyncio
async def test_save_bot_only_sets_null_user_token(
    bot_only_installation: Installation,
) -> None:
    from src.integrations.slack_store import CockroachInstallationStore

    store = CockroachInstallationStore()
    mock_execute = AsyncMock(return_value="INSERT 0 1")
    mock_fetchone = AsyncMock(return_value=None)

    with (
        patch("src.integrations.slack_store.execute", mock_execute),
        patch("src.integrations.slack_store.fetch_one", mock_fetchone),
    ):
        await store.async_save(bot_only_installation)

    call_args = mock_execute.call_args
    sql = call_args[0][0]
    assert "slack_installations" in sql


@pytest.mark.asyncio
async def test_find_installation_with_user_id(installation: Installation) -> None:
    from src.integrations.slack_store import CockroachInstallationStore

    store = CockroachInstallationStore()
    mock_fetchone = AsyncMock(
        return_value=MockRow(
            {
                "team_id": "T12345",
                "team_name": "Test Workspace",
                "bot_user_id": "U_BOT",
                "bot_token": "xoxb-fake-bot-token",
                "bot_scopes": "chat:write",
                "user_id": "U12345",
                "user_token": "xoxp-fake-user-token",
                "user_scopes": "channels:read",
                "token_type": "bot",
                "installed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
        )
    )

    with patch("src.integrations.slack_store.fetch_one", mock_fetchone):
        result = await store.async_find_installation(
            enterprise_id=None, team_id="T12345", user_id="U12345"
        )

    assert result is not None
    assert result.user_id == "U12345"

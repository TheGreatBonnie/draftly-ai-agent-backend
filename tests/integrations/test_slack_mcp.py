"""Tests for Slack MCP Server client."""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_slack_mcp_tools_returns_none_without_token():
    from src.integrations.slack_mcp import get_slack_mcp_tools

    result = await get_slack_mcp_tools("", "T123")
    assert result is None


@pytest.mark.asyncio
async def test_get_slack_mcp_tools_returns_client_with_token():
    from src.integrations.slack_mcp import get_slack_mcp_tools

    mock_client = AsyncMock()
    with patch("src.integrations.slack_mcp.SlackMCPClient") as MockClient:
        MockClient.return_value = mock_client
        result = await get_slack_mcp_tools("xoxp-test-token", "T123")
        assert result is not None
        mock_client.connect.assert_called_once()


@pytest.mark.asyncio
async def test_slack_mcp_client_call_tool():
    from src.integrations.slack_mcp import SlackMCPClient

    client = SlackMCPClient(url="https://test.com", headers={})
    mock_session = AsyncMock()
    mock_session.call_tool.return_value = "search results"
    client._session = mock_session

    result = await client.call_tool("search_messages", {"query": "test"})
    assert result == "search results"
    mock_session.call_tool.assert_called_once_with("search_messages", {"query": "test"})


@pytest.mark.asyncio
async def test_slack_mcp_client_call_tool_no_session():
    from src.integrations.slack_mcp import SlackMCPClient

    client = SlackMCPClient(url="https://test.com", headers={})
    result = await client.call_tool("search_messages", {"query": "test"})
    assert result is None


@pytest.mark.asyncio
async def test_find_search_tool():
    from src.integrations.slack_mcp import SlackMCPClient

    client = SlackMCPClient(url="https://test.com", headers={})
    client.tool_names = ["list_channels", "search_messages", "post_message"]
    assert client.find_search_tool() == "search_messages"


@pytest.mark.asyncio
async def test_find_search_tool_no_match():
    from src.integrations.slack_mcp import SlackMCPClient

    client = SlackMCPClient(url="https://test.com", headers={})
    client.tool_names = ["list_channels", "post_message"]
    assert client.find_search_tool() is None


@pytest.mark.asyncio
async def test_mcp_cache():
    from src.integrations.slack_mcp import SlackMCPClient, get_mcp_client, set_mcp_client

    client = SlackMCPClient(url="https://test.com", headers={})
    assert get_mcp_client("T_NONEXISTENT") is None
    set_mcp_client("T123", client)
    assert get_mcp_client("T123") is client

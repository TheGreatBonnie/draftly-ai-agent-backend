"""Slack MCP Server client for user-context operations."""
from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

SLACK_MCP_URL = "https://mcp.slack.com/mcp"

# Module-level cache: team_id -> SlackMCPClient (not serializable, can't go in state)
_mcp_clients: dict[str, SlackMCPClient] = {}


def get_mcp_client(team_id: str) -> SlackMCPClient | None:
    """Look up a cached MCP client for the given team."""
    return _mcp_clients.get(team_id)


def set_mcp_client(team_id: str, client: SlackMCPClient) -> None:
    """Cache an MCP client for the given team."""
    _mcp_clients[team_id] = client


class SlackMCPClient:
    """Wrapper around the MCP client for Slack MCP Server."""

    def __init__(self, url: str, headers: dict[str, str]) -> None:
        self.url = url
        self.headers = headers
        self._session: Any = None
        self._streams: Any = None
        self._cleanup: Any = None
        self._http_client: httpx.AsyncClient | None = None
        self.tool_names: list[str] = []

    async def connect(self) -> None:
        """Connect to the MCP server, initialize a session, and discover tools."""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        self._http_client = httpx.AsyncClient(headers=self.headers)
        streams_cm = streamable_http_client(
            url=self.url,
            http_client=self._http_client,
        )
        self._streams = await streams_cm.__aenter__()
        read_stream, write_stream, get_session_id = self._streams

        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        await self._session.initialize()
        self._cleanup = streams_cm

        # Discover available tools
        try:
            tools_result = await self._session.list_tools()
            self.tool_names = [t.name for t in tools_result.tools]
            logger.info("slack_mcp_connected", url=self.url, tools=self.tool_names)
        except Exception as e:
            logger.warning("slack_mcp_tools_list_failed", error=str(e))

    def find_search_tool(self) -> str | None:
        """Find a tool that looks like a message search tool."""
        search_keywords = ["search", "find", "query", "messages"]
        for name in self.tool_names:
            if any(kw in name.lower() for kw in search_keywords):
                return name
        return None

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Call a tool on the MCP server."""
        if not self._session:
            return None
        try:
            result = await self._session.call_tool(name, arguments)
            return result
        except Exception as e:
            logger.error("slack_mcp_tool_call_failed", tool=name, error=str(e))
            return None

    async def close(self) -> None:
        """Close the MCP connection."""
        try:
            if self._session:
                await self._session.__aexit__(None, None, None)
            if self._cleanup:
                await self._cleanup.__aexit__(None, None, None)
            if self._http_client:
                await self._http_client.aclose()
        except Exception:
            pass


async def get_slack_mcp_tools(user_token: str, team_id: str) -> SlackMCPClient | None:
    """Return an MCP client connected to Slack's MCP Server, or None if unavailable."""
    if not user_token:
        return None

    try:
        client = SlackMCPClient(
            url=SLACK_MCP_URL,
            headers={"Authorization": f"Bearer {user_token}"},
        )
        await client.connect()
        set_mcp_client(team_id, client)
        return client
    except ImportError:
        logger.warning("mcp_sdk_not_installed")
        return None
    except Exception as e:
        logger.error("slack_mcp_connection_failed", error=str(e))
        return None

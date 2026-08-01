from __future__ import annotations

from typing import Any

import httpx
from langchain_core.tools import tool

from src.config import settings


@tool
async def search_slack_messages(query: str, channel: str = "", limit: int = 5) -> str:
    """Search Slack messages for relevant support conversations."""
    token = settings.slack_bot_token.get_secret_value() if settings.slack_bot_token else ""
    headers = {"Authorization": f"Bearer {token}"}
    params: dict[str, Any] = {"query": query, "count": limit}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://slack.com/api/search.messages",
            headers=headers,
            params=params,
            timeout=10,
        )
        if resp.status_code != 200:
            return f"Slack search failed: {resp.status_code}"
        data = resp.json()

    if not data.get("ok"):
        return f"Slack API error: {data.get('error', 'unknown')}"

    messages = data.get("messages", {}).get("matches", [])
    if not messages:
        return "No relevant Slack messages found."

    return "\n".join(
        f"[{m.get('channel', {}).get('name', 'unknown')}] {m.get('text', '')[:200]}"
        for m in messages[:limit]
    )


SLACK_TOOLS = [search_slack_messages]

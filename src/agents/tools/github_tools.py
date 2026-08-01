from __future__ import annotations

from typing import Any

import httpx
from langchain_core.tools import tool

from src.config import settings


@tool
async def search_github_issues(query: str, org: str = "", limit: int = 5) -> str:
    """Search GitHub issues and discussions for relevant context."""
    token = settings.github_token.get_secret_value() if settings.github_token else None
    headers = {"Authorization": f"token {token}"} if token else {}
    search_url = "https://api.github.com/search/issues"
    params: dict[str, Any] = {"q": f"{query} is:issue", "per_page": limit}
    if org:
        params["q"] += f" org:{org}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(search_url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            return f"GitHub search failed: {resp.status_code}"
        data = resp.json()

    items = data.get("items", [])
    if not items:
        return "No relevant GitHub issues found."

    return "\n".join(
        f"[{item['state']}] {item['title']}\n{item['html_url']}\n{item.get('body', '')[:200]}"
        for item in items[:limit]
    )


@tool
async def get_github_issue(owner: str, repo: str, issue_number: int) -> str:
    """Get a specific GitHub issue with full body and comments."""
    token = settings.github_token.get_secret_value() if settings.github_token else None
    headers = {"Authorization": f"token {token}"} if token else {}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}",
            headers=headers,
            timeout=10,
        )
        if resp.status_code != 200:
            return f"Failed to fetch issue: {resp.status_code}"
        issue = resp.json()

    return f"#{issue['number']}: {issue['title']}\n\n{issue.get('body', '')}"


GITHUB_TOOLS = [search_github_issues, get_github_issue]

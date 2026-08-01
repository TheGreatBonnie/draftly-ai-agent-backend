from __future__ import annotations

from typing import cast

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()


async def post_github_comment(owner: str, repo: str, issue_number: int, body: str) -> dict:
    token = settings.github_token.get_secret_value()
    headers = {"Authorization": f"token {token}", "Content-Type": "application/json"}
    payload = {"body": body}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments",
            headers=headers,
            json=payload,
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            logger.error("github_comment_failed", status=resp.status_code, body=resp.text)
        return cast(dict, resp.json())


async def get_github_issue(owner: str, repo: str, issue_number: int) -> dict:
    headers = {"Authorization": f"token {settings.github_token.get_secret_value()}"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}",
            headers=headers,
            timeout=10,
        )
        return cast(dict, resp.json())

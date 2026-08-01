from __future__ import annotations

from typing import cast

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()


async def send_slack_message(
    channel: str,
    text: str,
    thread_ts: str | None = None,
    blocks: list[dict] | None = None,
    token: str | None = None,
) -> dict:
    if not token:
        token = settings.slack_bot_token.get_secret_value()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload: dict = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    if blocks:
        payload["blocks"] = blocks

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json=payload,
            timeout=10,
        )
        result = resp.json()
        if not result.get("ok"):
            logger.error("slack_send_failed", error=result.get("error"))
        return cast(dict, result)


async def send_dm(user_id: str, text: str) -> dict:
    token = settings.slack_bot_token.get_secret_value()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"channel": user_id, "text": text}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json=payload,
            timeout=10,
        )
        return cast(dict, resp.json())


async def add_reaction(channel: str, timestamp: str, emoji: str) -> dict:
    token = settings.slack_bot_token.get_secret_value()
    if not token:
        logger.error("add_reaction_no_token")
        return {"ok": False, "error": "no_bot_token"}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"channel": channel, "timestamp": timestamp, "name": emoji}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/reactions.add",
            headers=headers,
            json=payload,
            timeout=10,
        )
        result = resp.json()
        if not result.get("ok"):
            logger.warning("slack_reaction_failed", error=result.get("error"), channel=channel)
        return cast(dict, result)

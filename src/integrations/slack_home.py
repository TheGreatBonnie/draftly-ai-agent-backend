"""App Home view builder for the Draftly Slack bot."""
from __future__ import annotations

from typing import Any


def build_app_home(team_name: str = "", pipeline_count: int = 0) -> dict[str, Any]:
    """Build the App Home Block Kit view."""
    header_text = "**Draftly** — Your AI documentation assistant"
    workspace_text = f"Workspace: {team_name}" if team_name else ""
    stats_text = f"Completed pipelines: {pipeline_count}"

    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": "Draftly"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": header_text}},
        {"type": "divider"},
    ]

    if workspace_text:
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": f"_{workspace_text}_"}}
        )

    blocks.append(
        {"type": "section", "text": {"type": "mrkdwn", "text": stats_text}}
    )

    blocks.append({"type": "divider"})

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Get started by mentioning me in a channel or sending a DM.\n"
                    "I'll generate documentation from your conversations."
                ),
            },
        }
    )

    return {"type": "home", "blocks": blocks}


def build_suggested_prompts() -> list[dict[str, str]]:
    """Build suggested prompts for the Messages tab."""
    return [
        {"text": "Generate docs for this conversation"},
        {"text": "Summarize the last messages"},
        {"text": "What's the status of my recent requests?"},
    ]

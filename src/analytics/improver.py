from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog

from src.config import settings
from src.database import execute, fetch_all, fetch_one
from src.integrations.llm import call_llm, stage_llm_kwargs

logger = structlog.get_logger()

IMPROVEMENT_PROMPT = (
    "Based on this analysis, generate specific improvements for the agent harness.\n"
    "\n"
    "## Analysis\n"
    "{analysis}\n"
    "\n"
    "## Current Configuration\n"
    "{current_config}\n"
    "\n"
    "Generate improvements for:\n"
    "1. **Prompt Improvements**: Rewrite underperforming prompts\n"
    "2. **Tool Suggestions**: New tools to address research gaps\n"
    "3. **Rubric Updates**: Adjust criteria based on failure patterns\n"
    "\n"
    "Return a JSON object with:\n"
    "{{\n"
    '    "prompts": [\n'
    '        {{"node": "string", "current_prompt": "string",\n'
    '          "improved_prompt": "string", "rationale": "string"}}\n'
    "    ],\n"
    '    "tools": [\n'
    '        {{"name": "string", "description": "string",\n'
    '          "implementation_type": "http_get",\n'
    '          "config": {{}}, "rationale": "string"}}\n'
    "    ],\n"
    '    "rubrics": [\n'
    '        {{"criterion": "string", "current_text": "string",\n'
    '          "improved_text": "string", "rationale": "string"}}\n'
    "    ]\n"
    "}}\n"
    "\n"
    "Return ONLY valid JSON."
)


@dataclass
class ImprovementProposal:
    id: str
    org_id: str
    improvement_type: str
    proposed_changes: dict
    rationale: str
    status: str = "pending"
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


async def generate_improvements(analysis: dict, current_config: dict) -> dict:
    try:
        response = await call_llm(
            prompt=IMPROVEMENT_PROMPT.format(
                analysis=json.dumps(analysis, indent=2),
                current_config=json.dumps(current_config, indent=2),
            ),
            system_prompt=(
                "You are an expert at optimizing AI agent systems."
                " Generate specific, actionable improvements."
            ),
            **stage_llm_kwargs("analysis"),
        )
        return _parse_json_response(response)
    except Exception as e:
        logger.error("improvement_generation_failed", error=str(e))
        return {"error": str(e)}


async def create_improvement_proposals(
    org_id: str, improvements: dict, analysis: dict | None = None,
) -> list[ImprovementProposal]:
    proposals = []

    for prompt_change in improvements.get("prompts", []):
        proposal = ImprovementProposal(
            id=str(uuid4()),
            org_id=org_id,
            improvement_type="prompt",
            proposed_changes=prompt_change,
            rationale=prompt_change.get("rationale", ""),
        )
        await _store_proposal(proposal)
        proposals.append(proposal)

    for tool in improvements.get("tools", []):
        proposal = ImprovementProposal(
            id=str(uuid4()),
            org_id=org_id,
            improvement_type="tool",
            proposed_changes=tool,
            rationale=tool.get("rationale", ""),
        )
        await _store_proposal(proposal)
        proposals.append(proposal)

    for rubric_change in improvements.get("rubrics", []):
        proposal = ImprovementProposal(
            id=str(uuid4()),
            org_id=org_id,
            improvement_type="rubric",
            proposed_changes=rubric_change,
            rationale=rubric_change.get("rationale", ""),
        )
        await _store_proposal(proposal)
        proposals.append(proposal)

    logger.info("improvement_proposals_created", org_id=org_id, count=len(proposals))

    await notify_improvement_proposals(org_id, proposals, analysis)
    return proposals


async def apply_improvement(proposal_id: str) -> bool:
    row = await fetch_one(
        "SELECT * FROM harness_improvements WHERE id = $1", proposal_id,
    )
    if not row:
        logger.error("proposal_not_found", proposal_id=proposal_id)
        return False

    proposal_data = row["proposed_changes"]
    imp_type = row["improvement_type"]
    org_id = row["org_id"]

    try:
        if imp_type == "prompt":
            node = proposal_data.get("node", "unknown")
            improved = proposal_data.get("improved_prompt", "")
            await execute(
                "UPDATE prompt_versions SET is_active = false"
                " WHERE org_id = $1 AND node_name = $2 AND is_active = true",
                org_id, node,
            )
            max_version = await fetch_val(
                "SELECT COALESCE(MAX(version), 0)"
                " FROM prompt_versions WHERE org_id = $1 AND node_name = $2",
                org_id, node,
            )
            await execute(
                """
                INSERT INTO prompt_versions (org_id, node_name, prompt_text, version, is_active)
                VALUES ($1, $2, $3, $4, true)
                """,
                org_id, node, improved, max_version + 1,
            )

        elif imp_type == "rubric":
            criterion = proposal_data.get("criterion", "unknown")
            improved = proposal_data.get("improved_text", "")
            await execute(
                "UPDATE rubric_versions SET is_active = false"
                " WHERE org_id = $1 AND criterion_name = $2 AND is_active = true",
                org_id, criterion,
            )
            max_version = await fetch_val(
                "SELECT COALESCE(MAX(version), 0)"
                " FROM rubric_versions WHERE org_id = $1 AND criterion_name = $2",
                org_id, criterion,
            )
            await execute(
                """
                INSERT INTO rubric_versions
                (org_id, criterion_name, criterion_text, version, is_active)
                VALUES ($1, $2, $3, $4, true)
                """,
                org_id, criterion, improved, max_version + 1,
            )

        elif imp_type == "tool":
            name = proposal_data.get("name", "unknown")
            existing = await fetch_one(
                "SELECT id FROM tool_configs WHERE org_id = $1 AND name = $2",
                org_id, name,
            )
            if existing:
                await execute(
                    """
                    UPDATE tool_configs
                    SET description = $1, config = $2, version = version + 1
                    WHERE org_id = $3 AND name = $4
                    """,
                    proposal_data.get("description", ""),
                    json.dumps(proposal_data.get("config", {})),
                    org_id, name,
                )
            else:
                await execute(
                    """
                    INSERT INTO tool_configs
                    (org_id, name, description, implementation_type, config)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    org_id,
                    name,
                    proposal_data.get("description", ""),
                    proposal_data.get("implementation_type", "http_get"),
                    json.dumps(proposal_data.get("config", {})),
                )

        await _update_proposal_status(proposal_id, "applied")
        logger.info("improvement_applied", proposal_id=proposal_id, imp_type=imp_type)
        return True

    except Exception as e:
        logger.error("improvement_apply_failed", proposal_id=proposal_id, error=str(e))
        await _update_proposal_status(proposal_id, "failed")
        return False


async def load_current_config(org_id: str) -> dict:
    prompts = await fetch_all(
        "SELECT node_name, prompt_text FROM prompt_versions WHERE org_id = $1 AND is_active = true",
        org_id,
    )
    rubrics = await fetch_all(
        "SELECT criterion_name, criterion_text"
        " FROM rubric_versions WHERE org_id = $1 AND is_active = true",
        org_id,
    )
    tools = await fetch_all(
        "SELECT name, description, implementation_type, config"
        " FROM tool_configs WHERE org_id = $1 AND enabled = true",
        org_id,
    )
    return {
        "prompts": {r["node_name"]: r["prompt_text"] for r in prompts},
        "rubrics": {r["criterion_name"]: r["criterion_text"] for r in rubrics},
        "tools": [
            {"name": t["name"], "description": t["description"],
             "type": t["implementation_type"], "config": t["config"]}
            for t in tools
        ],
    }


async def fetch_pending_proposals(org_id: str) -> list[dict]:
    rows = await fetch_all(
        "SELECT * FROM harness_improvements"
        " WHERE org_id = $1 AND status = 'pending' ORDER BY created_at DESC",
        org_id,
    )
    return [dict(r) for r in rows]


async def update_proposal_status(
    proposal_id: str, status: str, reviewed_by: str | None = None, reason: str = "",
) -> None:
    await _update_proposal_status(proposal_id, status, reviewed_by, reason)


async def _store_proposal(proposal: ImprovementProposal) -> None:
    await execute(
        """
        INSERT INTO harness_improvements
        (id, org_id, improvement_type, proposed_changes, rationale, status)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        proposal.id, proposal.org_id, proposal.improvement_type,
        json.dumps(proposal.proposed_changes),
        proposal.rationale, proposal.status,
    )


async def _update_proposal_status(
    proposal_id: str, status: str, reviewed_by: str | None = None, reason: str = "",
) -> None:
    await execute(
        """
        UPDATE harness_improvements
        SET status = $1, reviewed_by = $2, reviewed_at = now(), review_reason = $3
        WHERE id = $4
        """,
        status, reviewed_by or "", reason, proposal_id,
    )


async def notify_improvement_proposals(
    org_id: str,
    proposals: list[ImprovementProposal],
    analysis: dict | None = None,
) -> None:
    from src.integrations.discord import get_or_create_dm_channel, send_discord_message
    from src.integrations.slack import send_slack_message
    from src.integrations.slack_blocks import build_improvement_card
    from src.memory.reviewers import get_reviewers_by_org
    from src.security.tokens import generate_review_token

    reviewers = await get_reviewers_by_org(org_id)
    if not reviewers:
        logger.info("no_reviewers_to_notify", org_id=org_id)
        return

    prompt_count = sum(1 for p in proposals if p.improvement_type == "prompt")
    rubric_count = sum(1 for p in proposals if p.improvement_type == "rubric")
    tool_count = sum(1 for p in proposals if p.improvement_type == "tool")

    summary = ""
    if analysis:
        health = analysis.get("overall_health", "unknown")
        summary = f"Overall health: {health}."

    dashboard_url = settings.app_url

    tokens = []
    for p in proposals[:5]:
        token = generate_review_token("system", p.id)
        tokens.append({"id": p.id, "token": token, "proposal": {
            "id": p.id,
            "improvement_type": p.improvement_type,
            "proposed_changes": p.proposed_changes,
        }})

    card = build_improvement_card(
        summary=summary,
        proposal_count=len(proposals),
        prompt_count=prompt_count,
        rubric_count=rubric_count,
        tool_count=tool_count,
        dashboard_url=dashboard_url,
        tokens=tokens,
    )

    from src.integrations.discord_blocks import build_discord_improvement_card
    from src.integrations.email import send_improvement_notification

    discord_card = build_discord_improvement_card(
        summary=summary,
        proposal_count=len(proposals),
        prompt_count=prompt_count,
        rubric_count=rubric_count,
        tool_count=tool_count,
        dashboard_url=dashboard_url,
        tokens=tokens,
    )

    for reviewer in reviewers:
        try:
            if reviewer.get("notify_slack") and reviewer.get("slack_user_id"):
                await send_slack_message(
                    reviewer["slack_user_id"],
                    card["blocks"][0]["text"]["text"],
                    blocks=card["blocks"],
                )

            if reviewer.get("notify_discord") and reviewer.get("discord_user_id"):
                channel_id = await get_or_create_dm_channel(reviewer["discord_user_id"])
                await send_discord_message(
                    channel_id,
                    embed=discord_card["embeds"][0],
                    components=discord_card["components"],
                )

            if reviewer.get("notify_email") and reviewer.get("email"):
                await send_improvement_notification(
                    to=reviewer["email"],
                    reviewer_name=reviewer.get("name", "Reviewer"),
                    proposal_count=len(proposals),
                    prompt_count=prompt_count,
                    rubric_count=rubric_count,
                    tool_count=tool_count,
                    summary=summary,
                    dashboard_url=dashboard_url,
                    tokens=tokens,
                )
        except Exception as e:
            logger.error(
                "improvement_notification_failed",
                reviewer_id=reviewer.get("id"),
                error=str(e),
            )

    logger.info("improvement_notifications_sent", org_id=org_id, reviewer_count=len(reviewers))


def _parse_json_response(response: str) -> dict:
    try:
        return json.loads(response)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            return json.loads(match.group())  # type: ignore[no-any-return]
        return {"error": "Failed to parse response"}


async def fetch_val(query: str, *args: Any) -> Any:
    from src.database import fetch_val as _fetch_val
    return await _fetch_val(query, *args)

from __future__ import annotations

from typing import cast

import asyncpg  # type: ignore[import-untyped]
import structlog

from src.database import execute, fetch_all, fetch_one

logger = structlog.get_logger()


async def link_workflow_to_document(workflow_id: str, doc_id: str) -> None:
    """Backfill the workflow_id on a documentation row if it is still unset."""
    await execute(
        "UPDATE documentation SET workflow_id = $1 WHERE id = $2 AND workflow_id IS NULL",
        workflow_id,
        doc_id,
    )


async def get_org_by_github(github_org: str) -> dict | None:
    """Find organization by GitHub org name."""
    row = await fetch_one(
        "SELECT clerk_org_id as id, clerk_org_name as name, github_org, created_at "
        "FROM organizations WHERE github_org = $1",
        github_org,
    )
    return dict(row) if row else None


async def store_github_installation(
    org_id: str,
    installation_id: int,
    github_org: str,
    repositories: list[dict] | None = None,
) -> str:
    """Store or update a GitHub App installation."""
    import json

    existing = await fetch_one(
        "SELECT id::text FROM github_installations WHERE installation_id = $1",
        installation_id,
    )

    if existing:
        await fetch_one(
            """UPDATE github_installations
               SET repositories = $1, updated_at = now()
               WHERE installation_id = $2""",
            json.dumps(repositories or []),
            installation_id,
        )
        return cast(str, existing["id"])

    row = await fetch_one(
        """INSERT INTO github_installations (org_id, installation_id, github_org, repositories)
           VALUES ($1, $2, $3, $4) RETURNING id::text""",
        org_id,
        installation_id,
        github_org,
        json.dumps(repositories or []),
    )
    logger.info(
        "github_installation_stored",
        org_id=org_id,
        installation_id=installation_id,
        github_org=github_org,
    )
    if row is None:
        raise RuntimeError("github installation row missing after insert")
    return cast(str, row["id"])


async def remove_github_installation(installation_id: int) -> None:
    """Delete a GitHub App installation record."""
    from src.database import execute

    await execute(
        "DELETE FROM github_installations WHERE installation_id = $1",
        installation_id,
    )
    logger.info("github_installation_removed", installation_id=installation_id)


async def get_or_create_org_by_clerk(clerk_org_id: str, name: str) -> str:
    """Get or create an organization from a Clerk webhook. Returns clerk_org_id."""
    existing = await fetch_one(
        "SELECT clerk_org_id FROM organizations WHERE clerk_org_id = $1",
        clerk_org_id,
    )
    if existing:
        return cast(str, existing["clerk_org_id"])

    existing = await fetch_one(
        "SELECT clerk_org_id FROM organizations WHERE clerk_org_name = $1",
        name,
    )
    if existing:
        await fetch_one(
            "UPDATE organizations SET clerk_org_id = $1 WHERE clerk_org_id = $2",
            clerk_org_id,
            existing["clerk_org_id"],
        )
        return clerk_org_id

    try:
        row = await fetch_one(
            "INSERT INTO organizations (clerk_org_name, clerk_org_id) "
            "VALUES ($1, $2) RETURNING clerk_org_id",
            name,
            clerk_org_id,
        )
    except asyncpg.UniqueViolationError:
        existing = await fetch_one(
            "SELECT clerk_org_id FROM organizations WHERE clerk_org_id = $1",
            clerk_org_id,
        )
        if existing is None:
            raise RuntimeError("organization missing after unique violation")
        return cast(str, existing["clerk_org_id"])

    logger.info("org_created_from_clerk", name=name, clerk_org_id=clerk_org_id)
    if row is None:
        raise RuntimeError("organization row missing after insert")
    return cast(str, row["clerk_org_id"])


async def list_github_installations() -> list[dict]:
    """List all GitHub App installations with org names."""
    import json

    rows = await fetch_all(
        """SELECT gi.id::text, gi.installation_id, gi.github_org, gi.repositories,
                  gi.created_at, gi.updated_at, o.clerk_org_name as org_name
           FROM github_installations gi
           JOIN organizations o ON o.clerk_org_id = gi.org_id
           ORDER BY gi.created_at DESC"""
    )
    result = []
    for row in rows:
        d = dict(row)
        if isinstance(d.get("repositories"), str):
            d["repositories"] = json.loads(d["repositories"])
        result.append(d)
    return result


async def store_github_workflow(
    org_id: str,
    workflow_id: str,
    installation_id: int,
    owner: str,
    repo: str,
    issue_number: int,
) -> str:
    """Store a GitHub workflow for tracking."""
    row = await fetch_one(
        """INSERT INTO github_workflows
           (org_id, workflow_id, installation_id, owner, repo, issue_number)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING id::text""",
        org_id,
        workflow_id,
        installation_id,
        owner,
        repo,
        issue_number,
    )
    logger.info(
        "github_workflow_stored",
        org_id=org_id,
        workflow_id=workflow_id,
        owner=owner,
        repo=repo,
        issue=issue_number,
    )
    if row is None:
        raise RuntimeError("github workflow row missing after insert")
    return cast(str, row["id"])


async def get_github_workflow_by_issue(owner: str, repo: str, issue_number: int) -> dict | None:
    """Get workflow by GitHub issue identifiers."""
    row = await fetch_one(
        """SELECT id::text, workflow_id, installation_id, owner, repo, issue_number, status
           FROM github_workflows
           WHERE owner = $1 AND repo = $2 AND issue_number = $3
           ORDER BY created_at DESC LIMIT 1""",
        owner,
        repo,
        issue_number,
    )
    return dict(row) if row else None


async def update_github_workflow_status(workflow_id: str, status: str) -> None:
    """Update workflow status."""
    from src.database import execute

    await execute(
        """UPDATE github_workflows
           SET status = $1,
               completed_at = CASE
                   WHEN $1 IN ('completed', 'failed') THEN now()
                   ELSE completed_at
               END
           WHERE workflow_id = $2""",
        status,
        workflow_id,
    )


# --- Slack ---


async def get_org_by_slack(team_id: str) -> dict | None:
    """Find organization by Slack team_id via slack_installations."""
    row = await fetch_one(
        """SELECT o.clerk_org_id as id, o.clerk_org_name as name,
                  si.team_id, si.team_name
           FROM slack_installations si
           JOIN organizations o ON o.clerk_org_id = si.org_id
           WHERE si.team_id = $1""",
        team_id,
    )
    return dict(row) if row else None


async def store_slack_workflow(
    org_id: str,
    workflow_id: str,
    channel_id: str,
    thread_ts: str,
) -> str:
    """Store a Slack workflow for tracking."""
    row = await fetch_one(
        """INSERT INTO slack_workflows
           (org_id, workflow_id, channel_id, thread_ts)
           VALUES ($1, $2, $3, $4) RETURNING id::text""",
        org_id,
        workflow_id,
        channel_id,
        thread_ts,
    )
    logger.info("slack_workflow_stored", org_id=org_id, workflow_id=workflow_id)
    if row is None:
        raise RuntimeError("slack workflow row missing after insert")
    return cast(str, row["id"])


async def update_slack_workflow_status(workflow_id: str, status: str) -> None:
    """Update Slack workflow status."""
    from src.database import execute

    await execute(
        """UPDATE slack_workflows
           SET status = $1,
               completed_at = CASE WHEN $1 IN ('completed', 'failed') THEN now()
                                    ELSE completed_at END
           WHERE workflow_id = $2""",
        status,
        workflow_id,
    )


async def list_slack_installations() -> list[dict]:
    """List all Slack installations with org names."""
    rows = await fetch_all(
        """SELECT si.id::text, si.team_id, si.team_name, si.bot_user_id,
                  si.org_id, si.installed_at, si.updated_at,
                  o.clerk_org_name as org_name
           FROM slack_installations si
           LEFT JOIN organizations o ON o.clerk_org_id = si.org_id
           ORDER BY si.installed_at DESC"""
    )
    return [dict(r) for r in rows]


async def link_slack_installation(team_id: str, org_id: str) -> bool:
    """Link a Slack installation to a Draftly organization."""
    from src.database import execute

    await execute(
        "UPDATE slack_installations SET org_id = $1 WHERE team_id = $2",
        org_id,
        team_id,
    )
    logger.info("slack_installation_linked", team_id=team_id, org_id=org_id)
    return True


# --- Discord ---


async def get_org_by_discord(guild_id: str) -> dict | None:
    """Find organization by Discord guild_id."""
    row = await fetch_one(
        """SELECT clerk_org_id as id, clerk_org_name as name, discord_guild_id,
                  discord_trigger_channels
           FROM organizations WHERE discord_guild_id = $1""",
        guild_id,
    )
    return dict(row) if row else None


async def store_discord_workflow(
    org_id: str,
    workflow_id: str,
    channel_id: str,
    message_id: str,
    thread_id: str | None = None,
    source_message: str = "",
) -> str:
    """Store a Discord workflow for tracking."""
    row = await fetch_one(
        """INSERT INTO discord_workflows
           (org_id, workflow_run_id, discord_channel_id, discord_message_id,
            discord_thread_id, source_message)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING id::text""",
        org_id,
        workflow_id,
        channel_id,
        message_id,
        thread_id,
        source_message,
    )
    logger.info("discord_workflow_stored", org_id=org_id, workflow_id=workflow_id)
    if row is None:
        raise RuntimeError("discord workflow row missing after insert")
    return cast(str, row["id"])


async def update_discord_workflow_status(workflow_id: str, status: str) -> None:
    """Update Discord workflow status."""
    from src.database import execute

    await execute(
        """UPDATE discord_workflows
           SET status = $1,
               updated_at = now()
           WHERE workflow_run_id = $2""",
        status,
        workflow_id,
    )


async def is_discord_message_processed(message_id: str) -> bool:
    """Check if a Discord message has already been processed (dedup guard)."""
    row = await fetch_one(
        """SELECT id FROM discord_workflows
           WHERE discord_message_id = $1 AND status IN ('running', 'completed')""",
        message_id,
    )
    return row is not None

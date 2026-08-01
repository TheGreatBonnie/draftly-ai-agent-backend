from __future__ import annotations

import structlog

from src.database import execute, fetch_one

logger = structlog.get_logger()

_PROMPT_NODES = [
    "write_docs",
    "synthesize",
    "research",
    "ai_review",
    "ingest",
]

_RUBRIC_CRITERIA = [
    "Accuracy",
    "Completeness",
    "Clarity",
    "Code Accuracy",
    "Missing Steps",
]


async def seed_prompt_version(org_id: str, node_name: str, prompt_text: str) -> None:
    """Insert version 1 of a prompt if it doesn't exist for this org/node."""
    existing = await fetch_one(
        "SELECT id FROM prompt_versions WHERE org_id = $1 AND node_name = $2 AND version = 1",
        org_id,
        node_name,
    )
    if existing:
        return
    await execute(
        """
        INSERT INTO prompt_versions (org_id, node_name, prompt_text, version, is_active)
        VALUES ($1, $2, $3, 1, true)
        """,
        org_id,
        node_name,
        prompt_text,
    )
    logger.info("prompt_version_seeded", org_id=org_id, node_name=node_name, version=1)


async def seed_rubric_version(org_id: str, criterion_name: str, criterion_text: str) -> None:
    """Insert version 1 of a rubric criterion if it doesn't exist."""
    existing = await fetch_one(
        "SELECT id FROM rubric_versions WHERE org_id = $1 AND criterion_name = $2 AND version = 1",
        org_id,
        criterion_name,
    )
    if existing:
        return
    await execute(
        """
        INSERT INTO rubric_versions (org_id, criterion_name, criterion_text, version, is_active)
        VALUES ($1, $2, $3, 1, true)
        """,
        org_id,
        criterion_name,
        criterion_text,
    )
    logger.info("rubric_version_seeded", org_id=org_id, criterion_name=criterion_name, version=1)


async def seed_all_versions(org_id: str) -> None:
    """Seed all prompt and rubric versions for a given org."""
    for node in _PROMPT_NODES:
        await seed_prompt_version(org_id, node, f"Prompt for {node} (version 1)")

    for criterion in _RUBRIC_CRITERIA:
        await seed_rubric_version(org_id, criterion, f"Criterion: {criterion} (version 1)")

    logger.info("all_versions_seeded", org_id=org_id)

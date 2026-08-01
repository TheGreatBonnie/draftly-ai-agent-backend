from __future__ import annotations

import json

import structlog

from src.agents.state import DocumentationState
from src.database import fetch_one
from src.integrations.llm import call_bedrock

logger = structlog.get_logger()

WRITE_PROMPT = """You are a technical documentation writer. Generate production-ready documentation.

## Knowledge Package
{knowledge_package}

## Original Question
{question}

## Doc Type: {doc_type}

## Reviewer Feedback (from previous iterations)
{review_feedback}

Write clear, accurate documentation. Include:
1. A concise title
2. An introduction explaining what this covers
3. Prerequisites (if applicable)
4. Step-by-step instructions with code examples
5. Common troubleshooting tips
6. A brief FAQ section

Write in a professional but approachable tone. Use markdown formatting.
Include real code examples where possible. Be specific, not generic."""


async def write_docs_node(state: DocumentationState) -> dict:
    logger.info("write_docs_started", org_id=state["org_id"], doc_type=state.get("doc_type"))

    prompt = WRITE_PROMPT.format(
        knowledge_package=json.dumps(state.get("knowledge_package", {}), indent=2),
        question=state["question"],
        doc_type=state.get("doc_type", "howto"),
        review_feedback=(
            state.get("rubric_feedback")
            or state.get("human_feedback")
            or "None"
        ),
    )

    content = await call_bedrock(prompt, max_tokens=4096)

    # Extract title from first line
    lines = content.strip().split("\n")
    title = lines[0].lstrip("# ").strip() if lines else "Untitled Documentation"

    # Store draft in documentation table
    org_id = state["org_id"]
    row = await fetch_one(
        """
        INSERT INTO documentation
            (org_id, title, content, doc_type, status, source_thread_id, confidence_score)
        VALUES ($1, $2, $3, $4, 'draft', $5, 0.0)
        RETURNING id::text
        """,
        org_id,
        title,
        content,
        state.get("doc_type", "howto"),
        state.get("support_thread_id"),
    )
    if row is None:
        raise RuntimeError("Failed to persist documentation draft")
    doc_id = row["id"]

    logger.info("write_docs_completed", doc_id=doc_id, title=title, content_length=len(content))

    return {
        "draft_content": content,
        "draft_title": title,
        "doc_id": doc_id,
    }

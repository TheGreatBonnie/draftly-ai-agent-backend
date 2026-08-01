from __future__ import annotations

import json

import structlog

from src.agents.state import DocumentationState
from src.integrations.llm import call_bedrock

logger = structlog.get_logger()

SYNTHESIZE_PROMPT = """You are a knowledge synthesis agent. Merge the following
research into a unified knowledge package for documentation.

## Original Question
{question}

## Semantic Context (similar documentation)
{semantic_context}

## Similar Support Threads
{similar_threads}

## Existing Documentation
{existing_docs}

## GitHub Context
{github_context}

## Slack Context
{slack_context}

## Reviewer Feedback History
{reviewer_feedback_history}

Create a JSON knowledge package with:
- "key_facts": list of verified facts from the sources
- "solutions": list of solutions found
- "code_examples": any code snippets found
- "gaps": information that's missing or contradictory
- "sources": list of source references
- "recommended_doc_type": one of "howto", "faq", "tutorial",
  "troubleshooting", "reference"

Return ONLY valid JSON, no other text."""


async def synthesize_node(state: DocumentationState) -> dict:
    logger.info("synthesize_started", org_id=state["org_id"])

    prompt = SYNTHESIZE_PROMPT.format(
        question=state["question"],
        semantic_context=json.dumps(state.get("semantic_context", [])[:3], indent=2),
        similar_threads=json.dumps(state.get("similar_threads", [])[:3], indent=2),
        existing_docs=json.dumps(state.get("existing_docs", [])[:3], indent=2),
        github_context="\n".join(str(c) for c in state.get("github_context", [])[:2]),
        slack_context="\n".join(str(c) for c in state.get("slack_context", [])[:2]),
        reviewer_feedback_history=json.dumps(
            state.get("reviewer_feedback_history", [])[:3], indent=2
        ),
    )

    response = await call_bedrock(prompt)

    try:
        knowledge_package = json.loads(response)
    except json.JSONDecodeError:
        import re

        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            knowledge_package = json.loads(json_match.group())
        else:
            knowledge_package = {
                "key_facts": [response],
                "solutions": [],
                "code_examples": [],
                "gaps": [],
                "sources": [],
                "recommended_doc_type": "howto",
            }

    doc_type = knowledge_package.get("recommended_doc_type", "howto")

    facts = knowledge_package.get("key_facts", [])
    logger.info("synthesize_completed", doc_type=doc_type, facts=len(facts))

    return {
        "knowledge_package": knowledge_package,
        "doc_type": doc_type,
    }

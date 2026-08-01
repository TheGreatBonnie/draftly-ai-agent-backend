from __future__ import annotations

import json

import structlog

from src.agents.state import DocumentationState
from src.database import execute
from src.integrations.llm import call_llm, stage_llm_kwargs

logger = structlog.get_logger()


def _check_research_needed(evaluations: list) -> bool:
    """Check if any rubric evaluation indicates research is needed."""
    for evaluation in evaluations:
        for criterion in evaluation.get("criteria", []):
            if not criterion.get("passed", True):
                if criterion.get("needs_research"):
                    return True
                gap = str(criterion.get("gap") or "").lower()
                if "source" in gap or "citation" in gap or "grounding" in gap:
                    return True
    return False


def _build_evidence(state: DocumentationState) -> str:
    """Build an evidence string from the knowledge package for the grader."""
    knowledge_package = state.get("knowledge_package", {})
    if not isinstance(knowledge_package, dict):
        knowledge_package = {}
    summary = knowledge_package.get("summary", "")
    sources = knowledge_package.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    source_lines = []
    for source in sources:
        if isinstance(source, dict):
            url = source.get("url", "")
            title = source.get("title", "")
            source_lines.append(f"- {title}: {url}" if title else f"- {url}")
        elif isinstance(source, str):
            source_lines.append(f"- {source}")
    parts = [summary] if isinstance(summary, str) and summary else ["No summary provided."]
    if source_lines:
        parts.append("## Sources")
        parts.extend(source_lines)
    return "\n".join(parts)


REVIEW_PROMPT = """You are a documentation reviewer. Evaluate the quality of this documentation.

## Original Question
{question}

## Documentation to Review
{content}

## Knowledge Package (ground truth)
{knowledge_package}

Review for:
1. Factual accuracy — does it match the knowledge package?
2. Completeness — does it answer the original question?
3. Code accuracy — are code examples syntactically correct?
4. Clarity — is it easy to follow?
5. Missing steps — are there gaps in the instructions?

Return a JSON object with:
- "confidence": float between 0.0 and 1.0
- "issues": list of specific issues found
- "suggestions": list of improvement suggestions
- "passed": boolean

Return ONLY valid JSON, no other text."""


async def ai_review_node_hybrid(state: DocumentationState) -> dict:
    """Review node: generates review via call_llm, grades with rubric, runs deterministic checks."""
    from src.agents.middleware.rubric import get_active_rubric, grade_with_rubric
    from src.agents.rubrics import (
        DOCUMENTATION_RUBRIC,
        extract_confidence_from_rubric_result,
        extract_feedback_from_rubric,
    )
    from src.agents.verification import format_verification_feedback, run_verification_pipeline

    logger.info("ai_review_hybrid_started", org_id=state["org_id"])

    draft_content = state.get("draft_content", "")

    # Generate review via LLM
    prompt = REVIEW_PROMPT.format(
        question=state["question"],
        content=draft_content,
        knowledge_package=json.dumps(state.get("knowledge_package", {}), indent=2),
    )

    review_response = await call_llm(
        prompt=prompt,
        system_prompt=(
            "You are a documentation reviewer. Evaluate the quality of documentation "
            "against the provided rubric criteria. Be thorough, accurate, and constructive."
        ),
        **stage_llm_kwargs("review"),
    )

    # Parse review from response
    try:
        review = json.loads(review_response)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r"\{[\s\S]*\}", review_response)
        if json_match:
            review = json.loads(json_match.group())
        else:
            review = {
                "confidence": 0.5,
                "issues": ["Review parsing failed"],
                "suggestions": [],
                "passed": False,
            }

    # Grade with rubric (Loop 2: LLM-based verification)
    rubric = await get_active_rubric(state["org_id"], DOCUMENTATION_RUBRIC)
    rubric_result = await grade_with_rubric(
        content=draft_content,
        rubric=rubric,
        evidence=_build_evidence(state),
    )

    rubric_status = rubric_result["status"]
    rubric_evaluations = rubric_result["evaluations"]

    # Run deterministic verification (Loop 2: deterministic checks)
    knowledge_package = state.get("knowledge_package", {})
    raw_sources = (
        knowledge_package.get("sources", []) if isinstance(knowledge_package, dict) else []
    )
    sources = [
        {"url": s} if isinstance(s, str) else s for s in raw_sources if isinstance(s, (dict, str))
    ]
    verification_result = await run_verification_pipeline(
        content=draft_content,
        rubric_result=rubric_result,
        sources=sources,
    )

    # Combine rubric and deterministic feedback
    verification_feedback = format_verification_feedback(verification_result)

    # Calculate confidence from rubric status and deterministic checks
    confidence = extract_confidence_from_rubric_result(
        rubric_result, critical_count=verification_result.critical_count
    )

    # Extract feedback from last rubric evaluation
    feedback = review.get("issues", [])
    if rubric_evaluations:
        last_eval = rubric_evaluations[-1]
        feedback = extract_feedback_from_rubric(last_eval)

    # Combine feedback
    combined_feedback = {
        "rubric_feedback": feedback,
        "verification_feedback": verification_feedback,
        "deterministic_issues": verification_result.to_dict(),
    }

    # Update documentation
    doc_id = state.get("doc_id")
    if doc_id:
        await execute(
            "UPDATE documentation SET confidence_score = $1 WHERE id = $2",
            confidence,
            doc_id,
        )

    logger.info(
        "ai_review_hybrid_completed",
        confidence=confidence,
        rubric_status=rubric_status,
        deterministic_passed=verification_result.deterministic_passed,
        critical_issues=verification_result.critical_count,
    )

    return {
        "confidence_score": confidence,
        "review_result": review,
        "review_feedback": json.dumps(combined_feedback),
        "rubric_feedback": feedback if rubric_status == "needs_revision" else "",
        "rubric_evaluations": rubric_evaluations,
        "rubric_status": {
            "satisfied": rubric_status == "satisfied"
            and verification_result.deterministic_passed,
            "needs_revision": rubric_status == "needs_revision"
            or not verification_result.deterministic_passed,
            "research_needed": _check_research_needed(rubric_evaluations),
            "feedback": combined_feedback,
            "verification_passed": verification_result.passed,
        },
    }

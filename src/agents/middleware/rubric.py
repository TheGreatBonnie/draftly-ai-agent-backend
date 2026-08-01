from __future__ import annotations

import json
import re
from typing import Any, Literal

import structlog
from pydantic import BaseModel

from src.agents.rubrics import DOCUMENTATION_RUBRIC
from src.config import settings
from src.database import fetch_all
from src.integrations.llm import call_llm, call_llm_structured, stage_llm_kwargs

logger = structlog.get_logger()

GRADER_SYSTEM_PROMPT = (
    "You are a documentation quality reviewer. Evaluate the documentation against "
    "the provided rubric criteria. Be strict but fair. First write a short overall "
    "explanation, then give a verdict for every criterion with a specific, "
    "actionable gap description for each failure."
)

GRADER_FEWSHOT = """Example 1:
Content: "To install, run npm install."
Rubric: "Completeness: all steps documented."
Explanation: The content gives a single install command but omits prerequisite
steps and configuration, so a reader cannot reproduce the setup.
Result: needs_revision
Criterion "Completeness": passed=false, gap="Missing prerequisite and configuration steps"

Example 2:
Content: "Run `docker compose up -d` after creating the .env file from .env.example."
Rubric: "Completeness: all steps documented."
Explanation: The content covers prerequisites and the single run step in order.
Result: satisfied
Criterion "Completeness": passed=true"""

GRADING_PROMPT = """Evaluate the documentation content against each rubric criterion.

## Evidence / Ground Truth
{evidence}

## Content to Evaluate
{content}

## Rubric
{rubric}

First write a short explanation of the overall quality, then grade every
criterion as passed (true) or not (false). For each failure provide a specific,
actionable gap and set needs_research=true when the draft would need additional
source material (citations, grounding) to fix it.

{fewshot}
"""


class Criterion(BaseModel):
    name: str
    passed: bool
    gap: str | None = None
    needs_research: bool = False


class GraderVerdict(BaseModel):
    explanation: str
    result: Literal["satisfied", "needs_revision"]
    criteria: list[Criterion]


def _verdict_to_dict(verdict: GraderVerdict, iteration: int) -> dict:
    return {
        "result": verdict.result,
        "explanation": verdict.explanation,
        "criteria": [
            {
                "name": c.name,
                "passed": c.passed,
                "gap": c.gap,
                "needs_research": c.needs_research,
            }
            for c in verdict.criteria
        ],
        "iteration": iteration,
        "grading_run_id": f"rubric-{iteration}",
    }


def _truncate_for_grader(content: str, limit: int | None = None) -> str:
    limit = limit or settings.rubric_max_content_chars
    if len(content) <= limit:
        return content
    return f"{content[:limit]}\n\n[TRUNCATED]"


async def get_active_rubric(org_id: str, default: str = DOCUMENTATION_RUBRIC) -> str:
    """Return the org's active rubric criteria appended to the default rubric."""
    rows = await fetch_all(
        "SELECT criterion_name, criterion_text FROM rubric_versions"
        " WHERE org_id = $1 AND is_active = true ORDER BY criterion_name",
        org_id,
    )
    if not rows:
        return default
    section = "\n".join(
        f"- {r['criterion_name']}: {r['criterion_text']}" for r in rows
    )
    return f"{default}\n\n### Org-Specific Criteria\n{section}"


async def grade_with_rubric(
    content: str,
    rubric: str,
    system_prompt: str = "",
    max_iterations: int | None = None,
    evidence: str = "",
) -> dict:
    """Grade content against a rubric using an LLM-as-a-judge.

    Returns:
        {
            "status": "satisfied" | "needs_revision" | "max_iterations_reached"
                      | "failed" | "grader_error",
            "evaluations": list of evaluation dicts,
            "final_content": str (the last reviewed content),
            "error": str (only when status is "failed" or "grader_error"),
        }
    """
    max_iterations = max_iterations or settings.rubric_max_iterations
    evaluations: list[dict] = []
    current_content = content

    if not content.strip() or not rubric.strip():
        return {
            "status": "failed",
            "evaluations": evaluations,
            "final_content": current_content,
            "error": "empty_content_or_rubric",
        }

    run_token_budget = settings.rubric_max_run_tokens

    for iteration in range(1, max_iterations + 1):
        prompt = GRADING_PROMPT.format(
            evidence=evidence or "No external evidence provided.",
            content=_truncate_for_grader(current_content),
            rubric=rubric,
            fewshot=GRADER_FEWSHOT,
        )

        estimated_tokens = len(prompt) // 4
        if run_token_budget - estimated_tokens < 0:
            logger.info(
                "rubric_token_budget_exhausted",
                iteration=iteration,
                estimated_tokens=estimated_tokens,
            )
            return {
                "status": "max_iterations_reached",
                "evaluations": evaluations,
                "final_content": current_content,
            }
        run_token_budget -= estimated_tokens

        parsed, error = await call_llm_structured(
            prompt=prompt,
            schema=GraderVerdict,
            system_prompt=system_prompt or GRADER_SYSTEM_PROMPT,
            **stage_llm_kwargs("rubric_grader"),
        )

        verdict: GraderVerdict | None
        repaired = False
        if isinstance(parsed, GraderVerdict):
            verdict = parsed
        else:
            verdict = await _repair_verdict(prompt, system_prompt)
            repaired = True

        if verdict is None:
            logger.error(
                "rubric_grader_error",
                iteration=iteration,
                error=error or "repair_failed",
            )
            return {
                "status": "grader_error",
                "evaluations": evaluations,
                "final_content": current_content,
                "error": error or "repair_failed",
            }

        evaluation = _verdict_to_dict(verdict, iteration)
        evaluations.append(evaluation)

        logger.info(
            "rubric_evaluation",
            iteration=iteration,
            result=evaluation["result"],
            explanation=evaluation["explanation"][:200],
            criteria_count=len(evaluation["criteria"]),
        )

        if repaired or evaluation["result"] == "satisfied":
            return {
                "status": evaluation["result"],
                "evaluations": evaluations,
                "final_content": current_content,
            }

    return {
        "status": "max_iterations_reached",
        "evaluations": evaluations,
        "final_content": current_content,
    }


async def _repair_verdict(prompt: str, system_prompt: str) -> GraderVerdict | None:
    """One free-text repair attempt after structured output fails."""
    try:
        response = await call_llm(
            prompt=prompt,
            system_prompt=system_prompt or GRADER_SYSTEM_PROMPT,
            temperature=0.0,
            **stage_llm_kwargs("rubric_grader"),
        )
    except Exception:
        return None
    return _parse_verdict_fallback(response)


def _parse_verdict_fallback(response: str) -> GraderVerdict | None:
    """Parse a free-text grader response into a GraderVerdict, or None."""
    try:
        evaluation = _parse_grading_response(response, iteration=0)
        criteria = evaluation.get("criteria")
        result = evaluation.get("result")
        if result not in ("satisfied", "needs_revision") or not criteria:
            return None
        return GraderVerdict(
            explanation=evaluation.get("explanation", ""),
            result=result,
            criteria=[
                Criterion(
                    name=c.get("name", "Unknown"),
                    passed=_coerce_bool(c.get("passed", False)),
                    gap=c.get("gap"),
                    needs_research=_coerce_bool(c.get("needs_research", False)),
                )
                for c in criteria
            ],
        )
    except (TypeError, ValueError, AttributeError):
        return None


def _coerce_bool(value: Any) -> bool:
    """Coerce a free-text field value to bool, treating "false" as False."""
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return bool(value)


def _parse_grading_response(response: str, iteration: int) -> dict:
    """Parse the grader LLM response into a structured evaluation."""
    try:
        evaluation: dict[str, Any] = json.loads(response)
    except json.JSONDecodeError:
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            try:
                evaluation = json.loads(json_match.group())
            except json.JSONDecodeError:
                evaluation = {
                    "result": "needs_revision",
                    "explanation": "Failed to parse grader response",
                    "criteria": [],
                }
        else:
            evaluation = {
                "result": "needs_revision",
                "explanation": "No JSON found in grader response",
                "criteria": [],
            }

    evaluation["iteration"] = iteration
    evaluation["grading_run_id"] = f"rubric-{iteration}"
    return dict(evaluation)

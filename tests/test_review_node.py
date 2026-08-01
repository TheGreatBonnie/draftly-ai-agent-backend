from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.nodes.review import _build_evidence, _check_research_needed


def test_check_research_needed_structured_field_first():
    evaluations = [
        {
            "criteria": [
                {
                    "name": "Completeness",
                    "passed": False,
                    "gap": "add a summary",
                    "needs_research": True,
                }
            ]
        }
    ]
    assert _check_research_needed(evaluations) is True


def test_check_research_needed_keyword_fallback():
    evaluations = [
        {
            "criteria": [
                {
                    "name": "Grounding",
                    "passed": False,
                    "gap": "Missing citations",
                    "needs_research": False,
                }
            ]
        }
    ]
    assert _check_research_needed(evaluations) is True


def test_check_research_needed_no_research():
    evaluations = [
        {
            "criteria": [
                {
                    "name": "Completeness",
                    "passed": False,
                    "gap": "add examples",
                    "needs_research": False,
                }
            ]
        }
    ]
    assert _check_research_needed(evaluations) is False


def test_build_evidence_includes_summary_and_sources():
    state = {
        "knowledge_package": {
            "summary": "How X works.",
            "sources": [
                {"title": "Docs", "url": "https://example.com/docs"},
                "https://example.com/guide",
            ],
        }
    }
    evidence = _build_evidence(state)
    assert "How X works." in evidence
    assert "https://example.com/docs" in evidence
    assert "https://example.com/guide" in evidence


def test_build_evidence_empty_knowledge_package():
    evidence = _build_evidence({"knowledge_package": {}})
    assert "No summary provided." in evidence


def test_build_evidence_none_sources():
    evidence = _build_evidence({"knowledge_package": {"summary": "s", "sources": None}})
    assert "s" in evidence


def test_check_research_needed_none_gap():
    evaluations = [
        {
            "criteria": [
                {"name": "Completeness", "passed": False, "gap": None, "needs_research": False}
            ]
        }
    ]
    assert _check_research_needed(evaluations) is False


class _FakeVerificationResult:
    deterministic_passed = True
    critical_count = 0
    passed = True
    rubric_passed = True
    issues = []

    def to_dict(self) -> dict:
        return {
            "passed": True,
            "critical_count": 0,
            "deterministic_passed": True,
            "rubric_passed": True,
            "issues": [],
        }


@pytest.mark.asyncio
async def test_ai_review_node_returns_rubric_feedback_and_evaluations():
    state = {
        "org_id": "org-1",
        "question": "How to deploy?",
        "draft_content": "# Deploy",
        "knowledge_package": {"summary": "s", "sources": []},
        "doc_id": "doc-1",
    }

    async def fake_grade(content, rubric, system_prompt="", max_iterations=None, evidence=""):
        return {
            "status": "needs_revision",
            "evaluations": [
                {
                    "result": "needs_revision",
                    "explanation": "needs work",
                    "criteria": [
                        {
                            "name": "Completeness",
                            "passed": False,
                            "gap": "missing step",
                            "needs_research": False,
                        }
                    ],
                    "iteration": 1,
                    "grading_run_id": "rubric-1",
                }
            ],
            "final_content": "# Deploy",
        }

    with (
        patch("src.agents.nodes.review.call_llm", new_callable=AsyncMock) as mock_call,
        patch("src.agents.middleware.rubric.grade_with_rubric", fake_grade),
        patch(
            "src.agents.middleware.rubric.get_active_rubric",
            new_callable=AsyncMock,
        ) as mock_rubric,
        patch(
            "src.agents.verification.run_verification_pipeline",
            new_callable=AsyncMock,
        ) as mock_verify,
        patch("src.agents.nodes.review.execute", new_callable=AsyncMock),
    ):
        mock_call.return_value = (
            '{"confidence": 0.5, "issues": [], "suggestions": [], "passed": false}'
        )
        mock_rubric.return_value = "## rubric"
        mock_verify.return_value = _FakeVerificationResult()

        from src.agents.nodes.review import ai_review_node_hybrid

        result = await ai_review_node_hybrid(state)

    assert "missing step" in result["rubric_feedback"]
    assert result["rubric_evaluations"][0]["criteria"][0]["name"] == "Completeness"
    assert result["rubric_status"]["needs_revision"] is True


async def test_ai_review_node_clears_rubric_feedback_when_satisfied():
    state = {
        "org_id": "org-1",
        "question": "How to deploy?",
        "draft_content": "# Deploy",
        "knowledge_package": {"summary": "s", "sources": []},
        "doc_id": "doc-1",
    }

    async def fake_grade(content, rubric, system_prompt="", max_iterations=None, evidence=""):
        return {
            "status": "satisfied",
            "evaluations": [
                {
                    "result": "satisfied",
                    "explanation": "looks good",
                    "criteria": [
                        {
                            "name": "Completeness",
                            "passed": True,
                            "gap": None,
                            "needs_research": False,
                        }
                    ],
                    "iteration": 1,
                    "grading_run_id": "rubric-1",
                }
            ],
            "final_content": "# Deploy",
        }

    with (
        patch("src.agents.nodes.review.call_llm", new_callable=AsyncMock) as mock_call,
        patch("src.agents.middleware.rubric.grade_with_rubric", fake_grade),
        patch(
            "src.agents.middleware.rubric.get_active_rubric",
            new_callable=AsyncMock,
        ) as mock_rubric,
        patch(
            "src.agents.verification.run_verification_pipeline",
            new_callable=AsyncMock,
        ) as mock_verify,
        patch("src.agents.nodes.review.execute", new_callable=AsyncMock),
    ):
        mock_call.return_value = (
            '{"confidence": 0.5, "issues": [], "suggestions": [], "passed": false}'
        )
        mock_rubric.return_value = "## rubric"
        mock_verify.return_value = _FakeVerificationResult()

        from src.agents.nodes.review import ai_review_node_hybrid

        result = await ai_review_node_hybrid(state)

    assert result["rubric_feedback"] == ""
    assert result["rubric_status"]["satisfied"] is True

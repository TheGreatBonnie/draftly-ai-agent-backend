from __future__ import annotations

from unittest.mock import AsyncMock, patch  # noqa: F401

import pytest

from src.agents.middleware.rubric import (
    Criterion,
    GraderVerdict,
    _truncate_for_grader,
    _verdict_to_dict,
    get_active_rubric,
    grade_with_rubric,
)


def test_verdict_to_dict_includes_structured_fields():
    verdict = GraderVerdict(
        explanation="Looks good",
        result="satisfied",
        criteria=[Criterion(name="Accuracy", passed=True, needs_research=True)],
    )
    data = _verdict_to_dict(verdict, iteration=1)
    assert data["result"] == "satisfied"
    assert data["explanation"] == "Looks good"
    assert data["criteria"][0]["name"] == "Accuracy"
    assert data["criteria"][0]["passed"] is True
    assert data["criteria"][0]["needs_research"] is True
    assert data["iteration"] == 1
    assert data["grading_run_id"] == "rubric-1"


def test_truncate_for_grader_short_content_unchanged():
    assert _truncate_for_grader("hello", limit=50) == "hello"


def test_truncate_for_grader_long_content_adds_marker():
    result = _truncate_for_grader("x" * 100, limit=50)
    assert result.endswith("[TRUNCATED]")
    assert len(result) == 50 + 2 + len("[TRUNCATED]")


def test_grader_verdict_rejects_invalid_result():
    with pytest.raises(ValueError):
        GraderVerdict(explanation="e", result="banana", criteria=[])


def _satisfied() -> GraderVerdict:
    return GraderVerdict(
        explanation="All good",
        result="satisfied",
        criteria=[Criterion(name="Accuracy", passed=True)],
    )


def _needs_revision(gap: str = "missing step") -> GraderVerdict:
    return GraderVerdict(
        explanation="needs work",
        result="needs_revision",
        criteria=[
            Criterion(
                name="Completeness",
                passed=False,
                gap=gap,
                needs_research=False,
            )
        ],
    )


async def test_grade_satisfied_returns_early(monkeypatch):
    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        return _satisfied(), ""

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    result = await grade_with_rubric("draft", "rubric", max_iterations=3)
    assert result["status"] == "satisfied"
    assert len(result["evaluations"]) == 1
    assert result["evaluations"][0]["criteria"][0]["name"] == "Accuracy"


async def test_grade_max_iterations_reached(monkeypatch):
    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        return _needs_revision(), ""

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    result = await grade_with_rubric("draft", "rubric", max_iterations=2)
    assert result["status"] == "max_iterations_reached"
    assert len(result["evaluations"]) == 2


async def test_grade_empty_content_returns_failed():
    result = await grade_with_rubric("", "rubric")
    assert result["status"] == "failed"
    assert "error" in result


async def test_grade_grader_error_after_repair_failure(monkeypatch):
    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        return None, "structured_output_failed"

    async def fake_llm(prompt, system_prompt="", **kwargs):
        return "no json here"

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    monkeypatch.setattr("src.agents.middleware.rubric.call_llm", fake_llm)
    result = await grade_with_rubric("draft", "rubric")
    assert result["status"] == "grader_error"
    assert "error" in result


async def test_grade_recovers_via_free_text_repair(monkeypatch):
    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        return None, "structured_output_failed"

    async def fake_llm(prompt, system_prompt="", **kwargs):
        return (
            '{"result": "needs_revision", "explanation": "add detail", '
            '"criteria": [{"name": "Completeness", "passed": false, '
            '"gap": "missing steps"}]}'
        )

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    monkeypatch.setattr("src.agents.middleware.rubric.call_llm", fake_llm)
    result = await grade_with_rubric("draft", "rubric")
    assert result["status"] == "needs_revision"
    assert len(result["evaluations"]) == 1
    assert result["evaluations"][0]["criteria"][0]["name"] == "Completeness"


async def test_grade_passes_evidence_into_prompt(monkeypatch):
    captured: dict = {}

    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        captured["prompt"] = prompt
        return _satisfied(), ""

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    await grade_with_rubric("draft", "rubric", evidence="GROUND TRUTH X")
    assert "GROUND TRUTH X" in captured["prompt"]


async def test_grade_truncates_long_content(monkeypatch):
    captured: dict = {}

    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        captured["prompt"] = prompt
        return _satisfied(), ""

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    await grade_with_rubric("x" * 50000, "rubric")
    assert "[TRUNCATED]" in captured["prompt"]


async def test_grade_uses_one_repair_attempt_per_iteration(monkeypatch):
    calls = {"structured": 0, "repair": 0}

    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        calls["structured"] += 1
        return None, "structured_output_failed"

    async def fake_llm(prompt, system_prompt="", **kwargs):
        calls["repair"] += 1
        return "garbage"

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    monkeypatch.setattr("src.agents.middleware.rubric.call_llm", fake_llm)
    result = await grade_with_rubric("draft", "rubric", max_iterations=3)
    assert result["status"] == "grader_error"
    assert calls["structured"] == 1
    assert calls["repair"] == 1


async def test_grade_handles_braces_in_content_and_rubric(monkeypatch):
    captured: dict = {}

    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        captured["prompt"] = prompt
        return _satisfied(), ""

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    content = 'print({"key": "value"})  # {unbalanced'
    rubric = "Criterion {1}: {2} with {nested braces"
    evidence = 'json = {"a": 1}'
    result = await grade_with_rubric(content, rubric, evidence=evidence)
    assert result["status"] == "satisfied"
    assert 'print({"key": "value"})' in captured["prompt"]
    assert "Criterion {1}" in captured["prompt"]
    assert 'json = {"a": 1}' in captured["prompt"]


async def test_grade_repair_handles_malformed_criteria(monkeypatch):
    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        return None, "structured_output_failed"

    async def fake_llm(prompt, system_prompt="", **kwargs):
        return (
            '{"result": "needs_revision", "explanation": "x", '
            '"criteria": "missing"}'
        )

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    monkeypatch.setattr("src.agents.middleware.rubric.call_llm", fake_llm)
    result = await grade_with_rubric("draft", "rubric")
    assert result["status"] == "grader_error"
    assert "error" in result


async def test_grade_repair_handles_top_level_list_json(monkeypatch):
    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        return None, "structured_output_failed"

    async def fake_llm(prompt, system_prompt="", **kwargs):
        return "[1, 2, 3]"

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    monkeypatch.setattr("src.agents.middleware.rubric.call_llm", fake_llm)
    result = await grade_with_rubric("draft", "rubric")
    assert result["status"] == "grader_error"


async def test_grade_repair_handles_string_false_passed(monkeypatch):
    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        return None, "structured_output_failed"

    async def fake_llm(prompt, system_prompt="", **kwargs):
        return (
            '{"result": "needs_revision", "explanation": "x", '
            '"criteria": [{"name": "Completeness", "passed": "false", '
            '"gap": "missing"}]}'
        )

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    monkeypatch.setattr("src.agents.middleware.rubric.call_llm", fake_llm)
    result = await grade_with_rubric("draft", "rubric")
    assert result["status"] == "needs_revision"
    assert result["evaluations"][0]["criteria"][0]["passed"] is False


async def test_grade_token_budget_exhausted_stops_early(monkeypatch):
    calls: dict = {"structured": 0}

    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        calls["structured"] += 1
        return _satisfied(), ""

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    monkeypatch.setattr(
        "src.agents.middleware.rubric.settings.rubric_max_run_tokens", 1
    )
    result = await grade_with_rubric("draft", "rubric", max_iterations=3)
    assert result["status"] == "max_iterations_reached"
    assert result["evaluations"] == []
    assert calls["structured"] == 0


async def test_grade_token_budget_allows_first_call(monkeypatch):
    calls: dict = {"structured": 0}

    async def fake_structured(prompt, schema, system_prompt="", **kwargs):
        calls["structured"] += 1
        return _satisfied(), ""

    monkeypatch.setattr(
        "src.agents.middleware.rubric.call_llm_structured", fake_structured
    )
    monkeypatch.setattr(
        "src.agents.middleware.rubric.settings.rubric_max_run_tokens", 100000
    )
    result = await grade_with_rubric("draft", "rubric", max_iterations=3)
    assert result["status"] == "satisfied"
    assert calls["structured"] == 1


@pytest.mark.asyncio
async def test_get_active_rubric_appends_org_criteria():
    with patch(
        "src.agents.middleware.rubric.fetch_all", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = [
            {
                "criterion_name": "SEO",
                "criterion_text": "Title includes the question.",
            }
        ]
        rubric = await get_active_rubric("org-1")
        assert "Org-Specific Criteria" in rubric
        assert "SEO" in rubric
        mock_fetch.assert_awaited_once_with(
            "SELECT criterion_name, criterion_text FROM rubric_versions"
            " WHERE org_id = $1 AND is_active = true ORDER BY criterion_name",
            "org-1",
        )


@pytest.mark.asyncio
async def test_get_active_rubric_falls_back_to_default():
    from src.agents.rubrics import DOCUMENTATION_RUBRIC

    with patch(
        "src.agents.middleware.rubric.fetch_all", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = []
        rubric = await get_active_rubric("org-1", DOCUMENTATION_RUBRIC)
        assert rubric == DOCUMENTATION_RUBRIC

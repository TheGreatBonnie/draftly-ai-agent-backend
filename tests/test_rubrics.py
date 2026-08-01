import pytest

from src.agents.rubrics import (
    DOCUMENTATION_RUBRIC,
    RESEARCH_RUBRIC,
    SYNTHESIS_RUBRIC,
    extract_confidence_from_rubric,
    extract_confidence_from_rubric_result,
    extract_feedback_from_rubric,
    get_rubric_for_node,
)


def test_documentation_rubric_exists():
    """Test that documentation rubric is defined."""
    assert DOCUMENTATION_RUBRIC is not None
    assert "Accuracy" in DOCUMENTATION_RUBRIC
    assert "Completeness" in DOCUMENTATION_RUBRIC


def test_research_rubric_exists():
    """Test that research rubric is defined."""
    assert RESEARCH_RUBRIC is not None
    assert "Coverage" in RESEARCH_RUBRIC


def test_synthesis_rubric_exists():
    """Test that synthesis rubric is defined."""
    assert SYNTHESIS_RUBRIC is not None
    assert "Coherence" in SYNTHESIS_RUBRIC


def test_get_rubric_for_node():
    """Test getting rubric by node name."""
    assert get_rubric_for_node("ai_review") == DOCUMENTATION_RUBRIC
    assert get_rubric_for_node("research") == RESEARCH_RUBRIC
    assert get_rubric_for_node("synthesize") == SYNTHESIS_RUBRIC
    assert get_rubric_for_node("unknown") == DOCUMENTATION_RUBRIC


def test_extract_confidence_from_rubric():
    """Test extracting confidence score from rubric results."""
    # All passed
    result_all_passed = {
        "criteria": [
            {"name": "Accuracy", "passed": True},
            {"name": "Completeness", "passed": True},
            {"name": "Clarity", "passed": True},
        ]
    }
    assert extract_confidence_from_rubric(result_all_passed) == 1.0

    # Some passed
    result_some_passed = {
        "criteria": [
            {"name": "Accuracy", "passed": True},
            {"name": "Completeness", "passed": False},
            {"name": "Clarity", "passed": True},
        ]
    }
    assert extract_confidence_from_rubric(result_some_passed) == pytest.approx(2 / 3)

    # None passed
    result_none_passed = {
        "criteria": [
            {"name": "Accuracy", "passed": False},
            {"name": "Completeness", "passed": False},
        ]
    }
    assert extract_confidence_from_rubric(result_none_passed) == 0.0

    # Empty result
    assert extract_confidence_from_rubric({}) == 0.5
    assert extract_confidence_from_rubric(None) == 0.5


def test_extract_feedback_from_rubric():
    """Test extracting feedback from rubric results."""
    # With explanation
    result_with_explanation = {
        "explanation": "Good documentation overall",
        "criteria": [
            {"name": "Accuracy", "passed": True},
        ],
    }
    feedback = extract_feedback_from_rubric(result_with_explanation)
    assert "Good documentation overall" in feedback

    # With failing criteria
    result_with_failures = {
        "explanation": "Needs improvement",
        "criteria": [
            {"name": "Accuracy", "passed": False, "gap": "Missing citations"},
            {"name": "Completeness", "passed": True},
        ],
    }
    feedback = extract_feedback_from_rubric(result_with_failures)
    assert "Issues found" in feedback
    assert "Accuracy" in feedback
    assert "Missing citations" in feedback

    # Empty result
    assert extract_feedback_from_rubric({}) == "No rubric evaluation available"
    assert extract_feedback_from_rubric(None) == "No rubric evaluation available"


def test_confidence_satisfied_is_one():
    assert extract_confidence_from_rubric_result(
        {"status": "satisfied", "evaluations": []}
    ) == 1.0


def test_confidence_needs_revision_is_pass_ratio():
    result = {
        "status": "needs_revision",
        "evaluations": [
            {
                "criteria": [
                    {"name": "Accuracy", "passed": True},
                    {"name": "Completeness", "passed": True},
                    {"name": "Clarity", "passed": False},
                ]
            }
        ],
    }
    assert extract_confidence_from_rubric_result(result) == pytest.approx(2 / 3)


def test_confidence_max_iterations_capped_at_point_four():
    result = {
        "status": "max_iterations_reached",
        "evaluations": [
            {
                "criteria": [
                    {"name": "Accuracy", "passed": True},
                    {"name": "Completeness", "passed": True},
                ]
            }
        ],
    }
    assert extract_confidence_from_rubric_result(result) == pytest.approx(0.4)


def test_confidence_critical_count_caps_at_point_three():
    result = {
        "status": "satisfied",
        "evaluations": [{"criteria": [{"name": "Accuracy", "passed": True}]}],
    }
    assert extract_confidence_from_rubric_result(result, critical_count=2) == pytest.approx(
        0.3
    )


def test_confidence_unknown_status_maps_to_status():
    assert extract_confidence_from_rubric_result({}) == pytest.approx(0.5)

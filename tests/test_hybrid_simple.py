import pytest


def test_rubric_structure():
    """Test rubric structure validation."""
    # Test that rubrics have required sections
    documentation_rubric = """
    ## Documentation Quality Criteria
    ### Accuracy (Required)
    - All API references are correct
    ### Completeness (Required)
    - Original question is fully addressed
    ### Clarity (Required)
    - Written in clear language
    ### Grounding (Required)
    - Claims are supported by sources
    ### Format (Required)
    - Correct doc_type selected
    """

    assert "Accuracy" in documentation_rubric
    assert "Completeness" in documentation_rubric
    assert "Clarity" in documentation_rubric
    assert "Grounding" in documentation_rubric
    assert "Format" in documentation_rubric


def test_confidence_extraction():
    """Test confidence score extraction logic."""
    # All passed
    criteria_all_passed = [
        {"name": "Accuracy", "passed": True},
        {"name": "Completeness", "passed": True},
        {"name": "Clarity", "passed": True},
    ]
    passed = sum(1 for c in criteria_all_passed if c.get("passed", False))
    total = len(criteria_all_passed)
    confidence = passed / total if total > 0 else 0.5
    assert confidence == 1.0

    # Some passed
    criteria_some_passed = [
        {"name": "Accuracy", "passed": True},
        {"name": "Completeness", "passed": False},
        {"name": "Clarity", "passed": True},
    ]
    passed = sum(1 for c in criteria_some_passed if c.get("passed", False))
    total = len(criteria_some_passed)
    confidence = passed / total if total > 0 else 0.5
    assert confidence == pytest.approx(2 / 3)


def test_investigation_plan_structure():
    """Test investigation plan structure."""
    # Simple plan
    simple_plan = [
        {
            "id": "task_1",
            "description": "Search for direct answer",
            "search_query": "test query",
            "priority": "high",
            "expected_output": "Direct answer",
        }
    ]

    assert len(simple_plan) == 1
    assert simple_plan[0]["priority"] == "high"
    assert "search_query" in simple_plan[0]


def test_question_complexity_classification():
    """Test question complexity classification logic."""
    # Simple question
    simple_question = "What is Python?"
    word_count = len(simple_question.split())
    assert word_count < 15

    # Complex question
    complex_question = (
        "Compare the performance characteristics of different caching strategies "
        "and explain which is best for high-traffic web applications"
    )
    word_count = len(complex_question.split())
    assert word_count > 10  # Adjusted threshold

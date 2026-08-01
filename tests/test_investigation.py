import pytest

from src.agents.planners.investigation import (
    _classify_complexity,
    _create_complex_plan,
    _create_moderate_plan,
    _create_simple_plan,
    create_investigation_plan,
    format_plan_for_display,
)


@pytest.mark.asyncio
async def test_classify_simple_question():
    """Test classifying a simple question."""
    complexity = await _classify_complexity("What is Python?")
    assert complexity == "simple"


@pytest.mark.asyncio
async def test_classify_complex_question():
    """Test classifying a complex question."""
    complexity = await _classify_complexity(
        "Compare the performance characteristics of different caching strategies "
        "and explain which is best for high-traffic web applications"
    )
    assert complexity == "complex"


@pytest.mark.asyncio
async def test_classify_moderate_question():
    """Test classifying a moderate question."""
    complexity = await _classify_complexity("How do I configure database connections?")
    assert complexity == "moderate"


def test_create_simple_plan():
    """Test creating a simple investigation plan."""
    plan = _create_simple_plan("What is Flask?")
    assert len(plan) == 2
    assert plan[0]["priority"] == "high"
    assert "Flask" in plan[0]["search_query"]


def test_create_moderate_plan():
    """Test creating a moderate investigation plan."""
    plan = _create_moderate_plan("How do I use SQLAlchemy with Flask?")
    assert len(plan) == 4
    assert any("example" in t["description"].lower() for t in plan)


def test_create_complex_plan():
    """Test creating a complex investigation plan."""
    plan = _create_complex_plan(
        "Compare Django vs Flask for large-scale applications"
    )
    assert len(plan) == 7
    assert any("comparison" in t["description"].lower() for t in plan)


def test_format_plan_for_display():
    """Test formatting plan for display."""
    plan = [
        {
            "id": "task_1",
            "description": "Test task",
            "search_query": "test query",
            "priority": "high",
            "expected_output": "Test output",
        }
    ]
    display = format_plan_for_display(plan)
    assert "Test task" in display
    assert "test query" in display
    assert "🔴" in display  # High priority icon


def test_create_investigation_plan():
    """Test creating an investigation plan."""
    plan = create_investigation_plan("How do I use Flask?")
    # Should return a list of tasks
    assert isinstance(plan, list)
    assert len(plan) >= 2

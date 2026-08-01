from __future__ import annotations

import structlog

logger = structlog.get_logger()


INVESTIGATION_PLAN_PROMPT = """
Break this documentation question into a structured research plan.

Question: {question}

Create a todo list of specific tasks to investigate:
1. Search queries to run
2. Documentation pages to check
3. Code examples to find
4. Validation steps to perform

Return as a JSON array of tasks with this structure:
[
    {{
        "id": "task_1",
        "description": "Search for API documentation",
        "search_query": "specific search query",
        "priority": "high|medium|low",
        "expected_output": "What to find"
    }}
]

Be specific and actionable. Focus on finding accurate, current information.
"""


def create_investigation_plan(question: str) -> list[dict]:
    """Create a todo-driven investigation plan for a question."""
    # Classify question complexity
    question_lower = question.lower()

    # Simple indicators
    simple_patterns = [
        "what is", "can you", "does",
        "is there", "where is", "when was",
    ]

    # Moderate indicators
    moderate_patterns = [
        "how do i", "how to", "configure", "setup", "install",
    ]

    # Complex indicators
    complex_patterns = [
        "compare", "difference between", "which is better",
        "best practices", "architecture", "design pattern",
        "optimize", "performance", "scale",
    ]

    # Count patterns
    simple_count = sum(1 for p in simple_patterns if p in question_lower)
    moderate_count = sum(1 for p in moderate_patterns if p in question_lower)
    complex_count = sum(1 for p in complex_patterns if p in question_lower)
    word_count = len(question.split())

    # Classify
    if complex_count > 0 or word_count > 25:
        complexity = "complex"
    elif moderate_count > 0 or (simple_count > 0 and word_count > 10):
        complexity = "moderate"
    elif simple_count > 0 and word_count < 15:
        complexity = "simple"
    else:
        complexity = "moderate"

    # Generate plan based on complexity
    if complexity == "simple":
        return _create_simple_plan(question)
    elif complexity == "moderate":
        return _create_moderate_plan(question)
    else:
        return _create_complex_plan(question)


async def _classify_complexity(question: str) -> str:
    """Classify question complexity based on characteristics."""
    # Simple indicators
    simple_patterns = [
        "what is", "can you", "does",
        "is there", "where is", "when was",
    ]

    # Moderate indicators
    moderate_patterns = [
        "how do i", "how to", "configure", "setup", "install",
    ]

    # Complex indicators
    complex_patterns = [
        "compare", "difference between", "which is better",
        "best practices", "architecture", "design pattern",
        "optimize", "performance", "scale",
    ]

    question_lower = question.lower()

    # Count simple patterns
    simple_count = sum(1 for p in simple_patterns if p in question_lower)

    # Count moderate patterns
    moderate_count = sum(1 for p in moderate_patterns if p in question_lower)

    # Count complex patterns
    complex_count = sum(1 for p in complex_patterns if p in question_lower)

    # Check question length
    word_count = len(question.split())

    if complex_count > 0 or word_count > 25:
        return "complex"
    elif moderate_count > 0 or (simple_count > 0 and word_count > 10):
        return "moderate"
    elif simple_count > 0 and word_count < 15:
        return "simple"
    else:
        return "moderate"


def _create_simple_plan(question: str) -> list[dict]:
    """Create a simple investigation plan."""
    return [
        {
            "id": "task_1",
            "description": f"Search for direct answer to: {question[:100]}",
            "search_query": question,
            "priority": "high",
            "expected_output": "Direct answer or definition",
        },
        {
            "id": "task_2",
            "description": "Verify answer with official documentation",
            "search_query": f"{question[:50]} official documentation",
            "priority": "medium",
            "expected_output": "Official confirmation",
        },
    ]


def _create_moderate_plan(question: str) -> list[dict]:
    """Create a moderate investigation plan."""
    return [
        {
            "id": "task_1",
            "description": "Search for primary documentation",
            "search_query": question,
            "priority": "high",
            "expected_output": "Main documentation page",
        },
        {
            "id": "task_2",
            "description": "Find code examples",
            "search_query": f"{question[:50]} example code",
            "priority": "high",
            "expected_output": "Working code examples",
        },
        {
            "id": "task_3",
            "description": "Check for common issues",
            "search_query": f"{question[:50]} common issues",
            "priority": "medium",
            "expected_output": "Known problems and solutions",
        },
        {
            "id": "task_4",
            "description": "Look for best practices",
            "search_query": f"{question[:50]} best practices",
            "priority": "low",
            "expected_output": "Recommended approaches",
        },
    ]


def _create_complex_plan(question: str) -> list[dict]:
    """Create a complex investigation plan."""
    return [
        {
            "id": "task_1",
            "description": "Research core concepts and definitions",
            "search_query": f"{question[:50]} explained",
            "priority": "high",
            "expected_output": "Conceptual understanding",
        },
        {
            "id": "task_2",
            "description": "Find official documentation",
            "search_query": f"{question[:50]} official docs",
            "priority": "high",
            "expected_output": "Primary documentation",
        },
        {
            "id": "task_3",
            "description": "Gather multiple perspectives and comparisons",
            "search_query": f"{question[:50]} comparison",
            "priority": "high",
            "expected_output": "Different approaches compared",
        },
        {
            "id": "task_4",
            "description": "Find real-world examples and use cases",
            "search_query": f"{question[:50]} examples",
            "priority": "medium",
            "expected_output": "Practical implementations",
        },
        {
            "id": "task_5",
            "description": "Check community discussions and feedback",
            "search_query": f"{question[:50]} stackoverflow",
            "priority": "medium",
            "expected_output": "Community insights",
        },
        {
            "id": "task_6",
            "description": "Research performance and scalability implications",
            "search_query": f"{question[:50]} performance",
            "priority": "low",
            "expected_output": "Performance considerations",
        },
        {
            "id": "task_7",
            "description": "Validate findings with authoritative sources",
            "search_query": f"{question[:50]} verification",
            "priority": "medium",
            "expected_output": "Confirmed information",
        },
    ]


def format_plan_for_display(plan: list[dict]) -> str:
    """Format investigation plan for display."""
    lines = ["## Investigation Plan\n"]
    for task in plan:
        priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
            task.get("priority", "medium"), "⚪"
        )
        lines.append(f"{priority_icon} **{task['id']}**: {task['description']}")
        lines.append(f"   - Search: `{task.get('search_query', 'N/A')}`")
        lines.append(f"   - Expected: {task.get('expected_output', 'N/A')}\n")
    return "\n".join(lines)

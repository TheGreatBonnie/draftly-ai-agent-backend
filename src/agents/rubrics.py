from __future__ import annotations

# Documentation quality rubric for LLM-as-a-judge grading
DOCUMENTATION_RUBRIC = """
## Documentation Quality Criteria

### Accuracy (Required)
- All API references are correct and exist in the codebase
- Code examples are syntactically valid and runnable
- Configuration options match actual settings
- No hallucinated functions, classes, or methods

### Completeness (Required)
- Original question is fully addressed
- All steps are clearly documented in logical order
- Edge cases and error handling are covered
- Prerequisites and dependencies listed

### Clarity (Required)
- Written in clear, concise language
- Logical structure with descriptive headings
- Appropriate for target audience (beginner/intermediate/advanced)
- No unnecessary jargon without explanation

### Grounding (Required)
- Claims are supported by retrieved sources
- Citations provided for external references
- Code examples are from official docs or verified sources
- No unverified claims or assumptions

### Format (Required)
- Correct doc_type selected (faq, tutorial, reference, troubleshooting)
- Appropriate length for content type
- Proper markdown formatting
- Code blocks have correct language tags
"""


# Research quality rubric
RESEARCH_RUBRIC = """
## Research Quality Criteria

### Coverage
- Multiple sources consulted
- Official documentation prioritized
- Community resources checked when appropriate
- Different perspectives considered

### Relevance
- All sources directly relate to the question
- No tangential or outdated information
- Focus on current versions and APIs
- Examples are practical and applicable

### Citation Quality
- All sources have valid URLs
- Sources are from reputable origins
- Publication dates noted where relevant
- Conflicting information highlighted
"""


# Synthesis quality rubric
SYNTHESIS_RUBRIC = """
## Synthesis Quality Criteria

### Coherence
- Information flows logically
- No contradictions between sections
- Consistent terminology used
- Smooth transitions between topics

### Actionability
- Reader can follow steps immediately
- Clear next steps provided
- Common pitfalls mentioned
- Success criteria defined

### Completeness
- All research findings incorporated
- No important details omitted
- Multiple approaches presented when applicable
- Trade-offs explained
"""


def get_rubric_for_node(node_name: str) -> str:
    """Get appropriate rubric for a pipeline node."""
    rubrics = {
        "ai_review": DOCUMENTATION_RUBRIC,
        "research": RESEARCH_RUBRIC,
        "synthesize": SYNTHESIS_RUBRIC,
    }
    return rubrics.get(node_name, DOCUMENTATION_RUBRIC)


STATUS_TO_CONFIDENCE = {
    "satisfied": 1.0,
    "needs_revision": 0.6,
    "max_iterations_reached": 0.4,
    "failed": 0.3,
    "grader_error": 0.5,
    "unknown": 0.5,
}


def extract_confidence_from_status(status: str) -> float:
    """Map rubric terminal status to a confidence score."""
    return STATUS_TO_CONFIDENCE.get(status, 0.5)


def extract_confidence_from_rubric_result(
    rubric_result: dict, critical_count: int = 0
) -> float:
    """Continuous confidence from a grade_with_rubric result and deterministic checks.

    - ``satisfied`` → 1.0
    - ``needs_revision`` → criterion pass-ratio
    - ``max_iterations_reached`` → min(pass-ratio, 0.4)
    - anything else → ``extract_confidence_from_status`` map
    - ``critical_count > 0`` caps the result at 0.3
    """
    if not rubric_result:
        return extract_confidence_from_status("unknown")

    status = rubric_result.get("status", "unknown")
    evaluations = rubric_result.get("evaluations", [])
    last_eval = evaluations[-1] if evaluations else {}
    criteria = last_eval.get("criteria", [])
    if criteria:
        pass_ratio = sum(1 for c in criteria if c.get("passed", False)) / len(criteria)
    else:
        pass_ratio = extract_confidence_from_status("unknown")

    if status == "satisfied":
        confidence = 1.0
    elif status == "needs_revision":
        confidence = pass_ratio
    elif status == "max_iterations_reached":
        confidence = min(pass_ratio, 0.4)
    else:
        confidence = extract_confidence_from_status(status)

    if critical_count > 0:
        confidence = min(confidence, 0.3)
    return confidence


def extract_confidence_from_rubric(rubric_result: dict) -> float:
    """Extract confidence score from rubric evaluation results."""
    if not rubric_result:
        return 0.5

    criteria = rubric_result.get("criteria", [])
    if not criteria:
        return 0.5

    passed = sum(1 for c in criteria if c.get("passed", False))
    total = len(criteria)

    return passed / total if total > 0 else 0.5


def extract_feedback_from_rubric(rubric_result: dict) -> str:
    """Extract human-readable feedback from rubric evaluation."""
    if not rubric_result:
        return "No rubric evaluation available"

    explanation = rubric_result.get("explanation", "")
    criteria = rubric_result.get("criteria", [])

    feedback_parts = []
    if explanation:
        feedback_parts.append(f"Overall: {explanation}")

    failing = [c for c in criteria if not c.get("passed", False)]
    if failing:
        feedback_parts.append("Issues found:")
        for c in failing:
            name = c.get("name", "Unknown")
            gap = c.get("gap", "No details")
            feedback_parts.append(f"- {name}: {gap}")

    return "\n".join(feedback_parts) if feedback_parts else "All criteria passed"

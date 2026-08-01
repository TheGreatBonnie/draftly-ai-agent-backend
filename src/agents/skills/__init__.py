from __future__ import annotations

# Research strategies for different question types
RESEARCH_SKILLS = {
    "api_question": """
# API Research Strategy

## Search Priority
1. Official documentation first (docs.python.org, docs.flask.org, etc.)
2. API reference pages
3. GitHub repository examples
4. Stack Overflow for common issues
5. Blog posts for tutorials

## Search Queries
- "{question}" site:docs.python.org
- "{question}" API reference
- "{question}" example code
- "{question}" tutorial

## Validation
- Verify API exists in current version
- Check for deprecation notices
- Confirm parameter types and defaults
- Test code examples mentally

## Citation Format
- Official docs: [Source](URL)
- Stack Overflow: [Stack Overflow](URL)
- GitHub: [GitHub](URL)
""",

    "configuration": """
# Configuration Research Strategy

## Search Priority
1. Official configuration documentation
2. Environment variable reference
3. Docker/Kubernetes examples
4. GitHub templates and examples
5. Best practices blog posts

## Search Queries
- "{question}" configuration
- "{question}" environment variables
- "{question}" settings
- "{question}" docker compose

## Validation
- Verify configuration format (YAML, JSON, env)
- Check for required vs optional settings
- Confirm default values
- Look for security considerations

## Citation Format
- Official docs: [Source](URL)
- GitHub examples: [Example](URL)
- Blog posts: [Guide](URL)
""",

    "troubleshooting": """
# Troubleshooting Research Strategy

## Search Priority
1. Search exact error message
2. GitHub issues with same problem
3. Stack Overflow solutions
4. Community forum posts
5. Official troubleshooting guides

## Search Queries
- "{error_message}" exact
- "{error_message}" solution
- "{error_message}" fix
- "{question}" troubleshooting

## Validation
- Verify error is reproducible
- Check for known issues/bugs
- Confirm solution applies to version
- Look for workarounds

## Citation Format
- GitHub issues: [Issue](URL)
- Stack Overflow: [Solution](URL)
- Forums: [Discussion](URL)
""",

    "tutorial": """
# Tutorial Research Strategy

## Search Priority
1. Official getting started guides
2. Step-by-step tutorials
3. Video walkthroughs
4. Blog post tutorials
5. Community examples

## Search Queries
- "{question}" tutorial
- "{question}" step by step
- "{question}" getting started
- "{question}" example project

## Validation
- Verify tutorial is current
- Check for completeness
- Confirm code examples work
- Look for prerequisites

## Citation Format
- Official tutorials: [Tutorial](URL)
- Video guides: [Video](URL)
- Blog posts: [Guide](URL)
""",

    "conceptual": """
# Conceptual Research Strategy

## Search Priority
1. Official concept documentation
2. Architecture explanations
3. Design pattern articles
4. Comparison posts
5. Deep dive blog posts

## Search Queries
- "{question}" explained
- "{question}" overview
- "{question}" how it works
- "{question}" architecture

## Validation
- Verify accuracy of explanations
- Check for multiple perspectives
- Confirm technical depth
- Look for diagrams/visuals

## Citation Format
- Official docs: [Concept](URL)
- Articles: [Article](URL)
- Deep dives: [Analysis](URL)
""",
}


def get_skill_for_question_type(question_type: str) -> str:
    """Get research skill for a question type."""
    return RESEARCH_SKILLS.get(question_type, RESEARCH_SKILLS["api_question"])


def get_skill_for_question(question: str, skill_type: str = "research") -> dict:
    """Get research skill based on question content."""
    question_lower = question.lower()

    if any(w in question_lower for w in ["error", "exception", "fail", "bug", "issue"]):
        skill_name = "troubleshooting"
    elif any(w in question_lower for w in ["config", "setting", "env", "environment"]):
        skill_name = "configuration"
    elif any(w in question_lower for w in ["tutorial", "how to", "guide", "step by step"]):
        skill_name = "tutorial"
    elif any(w in question_lower for w in ["what is", "explain", "concept", "overview"]):
        skill_name = "conceptual"
    else:
        skill_name = "api_question"

    return {
        "name": skill_name,
        "strategy": RESEARCH_SKILLS.get(skill_name, RESEARCH_SKILLS["api_question"]),
    }


def select_documentation_type(question: str) -> str:
    """Select documentation type based on question content."""
    question_lower = question.lower()

    error_terms = ["error", "exception", "fail", "bug", "issue", "problem"]
    tutorial_terms = ["tutorial", "how to", "guide", "step", "getting started"]
    faq_terms = ["what is", "explain", "concept", "difference", "overview"]
    reference_terms = ["api", "reference", "parameter", "method", "function"]

    if any(w in question_lower for w in error_terms):
        return "troubleshooting"
    elif any(w in question_lower for w in tutorial_terms):
        return "tutorial"
    elif any(w in question_lower for w in faq_terms):
        return "faq"
    elif any(w in question_lower for w in reference_terms):
        return "reference"
    else:
        return "howto"


def get_all_skills() -> dict:
    """Get all available research skills."""
    return RESEARCH_SKILLS.copy()

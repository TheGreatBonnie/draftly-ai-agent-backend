"""Verification pipeline combining deterministic and rubric-based checks."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import structlog

from src.agents.verification.deterministic import DeterministicVerifier, VerificationIssue

logger = structlog.get_logger()


@dataclass
class VerificationResult:
    """Combined result from all verification checks."""

    passed: bool
    issues: list[VerificationIssue] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    deterministic_passed: bool = True
    rubric_passed: bool = True

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "deterministic_passed": self.deterministic_passed,
            "rubric_passed": self.rubric_passed,
            "issues": [
                {
                    "check": i.check,
                    "severity": i.severity,
                    "message": i.message,
                    "line_number": i.line_number,
                }
                for i in self.issues
            ],
        }


async def run_verification_pipeline(
    content: str,
    rubric_result: dict | None = None,
    sources: Sequence[dict | str] | None = None,
) -> VerificationResult:
    """Run deterministic verification checks and combine with rubric results.

    Args:
        content: Documentation content to verify
        rubric_result: Optional rubric evaluation result from LLM grading
        sources: Optional list of research sources for citation verification

    Returns:
        VerificationResult with combined checks
    """
    verifier = DeterministicVerifier()
    issues = await verifier.verify_all(content, sources)

    critical_issues = [i for i in issues if i.severity == "critical"]
    warning_issues = [i for i in issues if i.severity == "warning"]
    info_issues = [i for i in issues if i.severity == "info"]

    deterministic_passed = len(critical_issues) == 0

    rubric_passed = True
    if rubric_result:
        rubric_status = rubric_result.get("status", "unknown")
        rubric_passed = rubric_status == "satisfied"

    overall_passed = deterministic_passed and rubric_passed

    result = VerificationResult(
        passed=overall_passed,
        issues=issues,
        critical_count=len(critical_issues),
        warning_count=len(warning_issues),
        info_count=len(info_issues),
        deterministic_passed=deterministic_passed,
        rubric_passed=rubric_passed,
    )

    logger.info(
        "verification_pipeline_completed",
        passed=overall_passed,
        deterministic_passed=deterministic_passed,
        rubric_passed=rubric_passed,
        critical=len(critical_issues),
        warnings=len(warning_issues),
        info=len(info_issues),
    )

    return result


def format_verification_feedback(result: VerificationResult) -> str:
    """Format verification result as human-readable feedback."""
    if result.passed and result.critical_count == 0:
        return "All verification checks passed."

    parts = []

    if result.critical_count > 0:
        critical = [i for i in result.issues if i.severity == "critical"]
        parts.append(f"Critical issues ({result.critical_count}):")
        for issue in critical[:5]:
            loc = f" (line {issue.line_number})" if issue.line_number else ""
            parts.append(f"  - {issue.message}{loc}")

    if result.warning_count > 0:
        warnings = [i for i in result.issues if i.severity == "warning"]
        parts.append(f"Warnings ({result.warning_count}):")
        for issue in warnings[:5]:
            loc = f" (line {issue.line_number})" if issue.line_number else ""
            parts.append(f"  - {issue.message}{loc}")

    if not result.rubric_passed:
        parts.append("Rubric evaluation: FAILED")

    return "\n".join(parts)

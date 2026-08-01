"""Deterministic verification checks for documentation quality."""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import structlog

logger = structlog.get_logger()


@dataclass
class VerificationIssue:
    """A single verification issue."""

    check: str
    severity: Literal["critical", "warning", "info"]
    message: str
    line_number: int | None = None
    details: dict | None = None


def _source_url(source: dict | str) -> str:
    """Extract a URL from a source that may be a dict or a bare string."""
    if isinstance(source, dict):
        return str(source.get("url", "")).strip()
    return source.strip()


class DeterministicVerifier:
    """Runs deterministic checks on documentation content."""

    async def verify_all(
        self, content: str, sources: Sequence[dict | str] | None = None
    ) -> list[VerificationIssue]:
        """Run all deterministic verification checks."""
        issues: list[VerificationIssue] = []

        issues.extend(self.verify_links(content))
        issues.extend(self.verify_code_blocks(content))
        issues.extend(self.verify_citations(content, sources or []))
        issues.extend(self.verify_format(content))

        logger.info(
            "deterministic_verification_completed",
            total_issues=len(issues),
            critical=sum(1 for i in issues if i.severity == "critical"),
            warnings=sum(1 for i in issues if i.severity == "warning"),
        )

        return issues

    def verify_links(self, content: str) -> list[VerificationIssue]:
        """Check markdown links for obvious issues."""
        issues: list[VerificationIssue] = []
        link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            for match in link_pattern.finditer(line):
                text, url = match.groups()

                if not text.strip():
                    issues.append(
                        VerificationIssue(
                            check="link_text",
                            severity="warning",
                            message="Link has empty text",
                            line_number=line_num,
                        )
                    )

                if not url.strip():
                    issues.append(
                        VerificationIssue(
                            check="link_url",
                            severity="critical",
                            message="Link has empty URL",
                            line_number=line_num,
                        )
                    )
                elif url.startswith("#"):
                    continue  # Internal anchor, skip
                elif not url.startswith(("http://", "https://", "/", "./", "../")):
                    issues.append(
                        VerificationIssue(
                            check="link_url",
                            severity="warning",
                            message=f"Link URL may be invalid: {url}",
                            line_number=line_num,
                        )
                    )

        return issues

    def verify_code_blocks(self, content: str) -> list[VerificationIssue]:
        """Validate code blocks have language tags and balanced fences."""
        issues: list[VerificationIssue] = []
        lines = content.split("\n")
        in_code_block = False
        fence_char = None
        fence_line = 0

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            if not in_code_block:
                if stripped.startswith("```") and len(stripped) >= 3:
                    in_code_block = True
                    fence_char = stripped[0]
                    fence_line = line_num
                    lang = stripped[3:].strip()
                    if not lang:
                        issues.append(
                            VerificationIssue(
                                check="code_language",
                                severity="warning",
                                message="Code block missing language tag",
                                line_number=line_num,
                            )
                        )
            else:
                if fence_char and stripped.startswith(fence_char * 3) and len(stripped) >= 3:
                    in_code_block = False
                    fence_char = None

        if in_code_block:
            issues.append(
                VerificationIssue(
                    check="code_fence",
                    severity="critical",
                    message=f"Unclosed code block starting at line {fence_line}",
                    line_number=fence_line,
                )
            )

        return issues

    def verify_citations(
        self, content: str, sources: Sequence[dict | str]
    ) -> list[VerificationIssue]:
        """Check that claims have supporting sources when required."""
        issues: list[VerificationIssue] = []

        claim_patterns = [
            (r"(?:according to|as documented in|per the docs)", "citation_claim"),
            (r"(?:the API supports|the library provides|the function returns)", "api_claim"),
        ]

        citation_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        citations = citation_pattern.findall(content)
        citation_urls = {url for _, url in citations}

        lines = content.split("\n")
        for line_num, line in enumerate(lines, 1):
            for pattern, check_type in claim_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    has_citation = citation_pattern.search(line)
                    next_line = lines[line_num] if line_num < len(lines) else ""
                    has_citation_next = citation_pattern.search(next_line)

                    if not has_citation and not has_citation_next:
                        issues.append(
                            VerificationIssue(
                                check=check_type,
                                severity="info",
                                message="Claim may benefit from a citation",
                                line_number=line_num,
                            )
                        )

        if sources:
            source_urls = {url for s in sources if (url := _source_url(s))}
            unreferenced = source_urls - citation_urls
            if unreferenced:
                issues.append(
                    VerificationIssue(
                        check="source_coverage",
                        severity="warning",
                        message=f"{len(unreferenced)} source(s) not cited in documentation",
                        details={"unreferenced_urls": list(unreferenced)[:5]},
                    )
                )

        return issues

    def verify_format(self, content: str) -> list[VerificationIssue]:
        """Check markdown formatting issues."""
        issues: list[VerificationIssue] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            if len(line) > 200 and not line.strip().startswith("```"):
                issues.append(
                    VerificationIssue(
                        check="line_length",
                        severity="info",
                        message=f"Line exceeds 200 characters ({len(line)} chars)",
                        line_number=line_num,
                    )
                )

            if line.rstrip() != line and line.strip():
                issues.append(
                    VerificationIssue(
                        check="trailing_whitespace",
                        severity="info",
                        message="Trailing whitespace",
                        line_number=line_num,
                    )
                )

        if not content.strip():
            issues.append(
                VerificationIssue(
                    check="empty_content",
                    severity="critical",
                    message="Documentation content is empty",
                )
            )

        headings = [line for line in lines if line.strip().startswith("#")]
        if not headings:
            issues.append(
                VerificationIssue(
                    check="no_headings",
                    severity="warning",
                    message="No headings found in documentation",
                )
            )

        return issues

import pytest

from src.agents.verification.deterministic import DeterministicVerifier
from src.agents.verification.pipeline import run_verification_pipeline


@pytest.fixture
def verifier() -> DeterministicVerifier:
    return DeterministicVerifier()


def test_verify_citations_dict_sources(verifier):
    """Dict sources with a url key are handled correctly."""
    content = "See the docs at [source](https://example.com/docs)."
    sources = [{"url": "https://example.com/docs"}]
    issues = verifier.verify_citations(content, sources)
    assert not any(i.check == "source_coverage" for i in issues)


def test_verify_citations_string_sources_do_not_crash(verifier):
    """String sources (bare URLs) must not raise AttributeError."""
    content = "Some documentation without citations."
    sources = ["https://example.com/docs", "https://example.com/guide"]
    issues = verifier.verify_citations(content, sources)
    coverage = [i for i in issues if i.check == "source_coverage"]
    assert len(coverage) == 1
    assert len(coverage[0].details["unreferenced_urls"]) == 2


def test_verify_citations_mixed_sources(verifier):
    """Mixed dict and string sources are normalized."""
    content = "One claim. [cited](https://example.com/a)"
    sources = ["https://example.com/a", {"url": "https://example.com/b"}]
    issues = verifier.verify_citations(content, sources)
    coverage = [i for i in issues if i.check == "source_coverage"]
    assert len(coverage) == 1
    unreferenced = coverage[0].details["unreferenced_urls"]
    assert "https://example.com/a" not in unreferenced
    assert "https://example.com/b" in unreferenced


def test_verify_citations_empty_sources(verifier):
    """Empty sources produce no issues."""
    issues = verifier.verify_citations("Some documentation.", [])
    assert not any(i.check == "source_coverage" for i in issues)


def test_verify_citations_string_sources_in_details_dict(verifier):
    """String sources without a url attribute are ignored safely."""
    issues = verifier.verify_citations("Content.", [{"title": "no url"}, ""])
    assert not any(i.check == "source_coverage" for i in issues)


async def test_run_verification_pipeline_with_string_sources():
    """Full verification pipeline tolerates string sources."""
    result = await run_verification_pipeline(
        content="# Doc\n\nSee [a](https://example.com/a).",
        rubric_result={"status": "satisfied"},
        sources=["https://example.com/a", "https://example.com/b"],
    )
    assert result.passed
    assert result.rubric_passed
    assert result.deterministic_passed

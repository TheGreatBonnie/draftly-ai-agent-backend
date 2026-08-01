from unittest.mock import AsyncMock, patch

import pytest

from src.analytics.analyzer import (
    _summarize_traces,
    analyze_production_traces,
    _parse_json_response,
)
from src.analytics.traces import AgentTrace, NodeTrace


def make_trace(node_names: list[str], confidence: float = 0.8, published: bool = True):
    traces = [
        NodeTrace(node_name=n, duration_ms=100.0)
        for n in node_names
    ]
    return AgentTrace(
        trace_id="t1", org_id="o1", workflow_id="w1",
        question="q", question_type="simple", source="cli",
        node_traces=traces, final_confidence=confidence, published=published,
    )


def test_summarize_traces_empty():
    assert _summarize_traces([]) == "No traces available."


def test_summarize_traces_with_data():
    traces = [make_trace(["research", "write_docs"], confidence=0.9, published=True)]
    summary = _summarize_traces(traces)
    assert '"total_traces": 1' in summary
    assert "research" in summary
    assert "write_docs" in summary


def test_parse_json_response_direct():
    result = _parse_json_response('{"overall_health": "good"}')
    assert result["overall_health"] == "good"


def test_parse_json_response_with_fence():
    result = _parse_json_response('```json\n{"overall_health": "good"}\n```')
    assert result["overall_health"] == "good"


def test_parse_json_response_fallback():
    text = 'Some text before {"overall_health": "good"} some after'
    result = _parse_json_response(text)
    assert result["overall_health"] == "good"


def test_parse_json_response_invalid():
    result = _parse_json_response("not json at all")
    assert "error" in result


@pytest.mark.asyncio
async def test_analyze_empty_traces():
    result = await analyze_production_traces([])
    assert result["error"] == "no_traces"


@pytest.mark.asyncio
async def test_analyze_with_llm_response():
    traces = [make_trace(["research"], confidence=0.9)]
    mock_response = (
        '{"failure_patterns": [], "quality_patterns": [], '
        '"performance_patterns": [], "improvements": {}, '
        '"confidence_trend": 0.0, "overall_health": "good"}'
    )
    with patch("src.analytics.analyzer.call_llm", new_callable=AsyncMock, return_value=mock_response):
        result = await analyze_production_traces(traces)
        assert result["overall_health"] == "good"
        assert result["metrics"]["total_traces"] == 1


@pytest.mark.asyncio
async def test_analyze_llm_failure_fallback():
    traces = [make_trace(["research"], confidence=0.9)]
    with patch("src.analytics.analyzer.call_llm", side_effect=Exception("LLM down")):
        result = await analyze_production_traces(traces)
        assert result["overall_health"] == "unknown"
        assert "error" in result

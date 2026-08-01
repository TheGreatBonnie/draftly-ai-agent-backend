from unittest.mock import AsyncMock, patch

import pytest

from src.analytics.hill_climber import HillClimber
from src.analytics.traces import TraceCollector, AgentTrace


def make_trace():
    return AgentTrace(
        trace_id="t1", org_id="o1", workflow_id="w1",
        question="q", question_type="simple", source="cli",
        final_confidence=0.9, published=True,
    )


@pytest.mark.asyncio
async def test_hill_climber_should_analyze_threshold():
    collector = TraceCollector()
    climber = HillClimber(collector, "org1", analysis_interval=3)
    assert await climber.should_analyze() is False
    assert await climber.should_analyze() is False
    assert await climber.should_analyze() is True
    assert await climber.should_analyze() is False  # resets after trigger


@pytest.mark.asyncio
async def test_hill_climber_cycle_no_traces():
    collector = TraceCollector()
    climber = HillClimber(collector, "org1")
    with patch.object(collector, "get_traces_for_analysis", new_callable=AsyncMock, return_value=[]):
        result = await climber.run_analysis_cycle()
        assert result["status"] == "no_traces"


@pytest.mark.asyncio
async def test_hill_climber_cycle_success():
    collector = TraceCollector()
    climber = HillClimber(collector, "org1")
    traces = [make_trace()]

    with (
        patch.object(collector, "get_traces_for_analysis", new_callable=AsyncMock, return_value=traces),
        patch("src.analytics.hill_climber.analyze_production_traces", new_callable=AsyncMock, return_value={
            "overall_health": "good", "metrics": {}, "failure_patterns": [],
        }),
        patch("src.analytics.hill_climber.load_current_config", new_callable=AsyncMock, return_value={}),
        patch("src.analytics.hill_climber.generate_improvements", new_callable=AsyncMock, return_value={"prompts": [], "tools": [], "rubrics": []}),
        patch("src.analytics.hill_climber.create_improvement_proposals", new_callable=AsyncMock, return_value=[]),
    ):
        result = await climber.run_analysis_cycle()
        assert result["status"] == "completed"
        assert result["traces_analyzed"] == 1

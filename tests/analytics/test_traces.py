from unittest.mock import AsyncMock, patch

import pytest

from src.analytics.traces import AgentTrace, NodeTrace, TraceCollector


def test_node_trace_defaults():
    trace = NodeTrace(node_name="research")
    assert trace.node_name == "research"
    assert trace.duration_ms == 0.0
    assert trace.error is None


def test_agent_trace_defaults():
    trace = AgentTrace(
        trace_id="t1",
        org_id="org1",
        workflow_id="w1",
        question="How to deploy?",
        question_type="simple",
        source="cli",
    )
    assert trace.trace_id == "t1"
    assert trace.nodes_executed == []
    assert trace.final_confidence == 0.0
    assert trace.published is False


@pytest.mark.asyncio
async def test_collector_buffers():
    collector = TraceCollector(flush_threshold=3)
    assert len(collector._buffer) == 0

    t1 = AgentTrace(
        trace_id="t1", org_id="o1", workflow_id="w1",
        question="q", question_type="s", source="cli",
    )
    t2 = AgentTrace(
        trace_id="t2", org_id="o1", workflow_id="w1",
        question="q", question_type="s", source="cli",
    )

    # First two traces don't trigger flush (threshold is 3)
    await collector.collect(t1)
    assert len(collector._buffer) == 1
    await collector.collect(t2)
    assert len(collector._buffer) == 2


@pytest.mark.asyncio
async def test_collector_flush_calls_storage():
    collector = TraceCollector(flush_threshold=1)
    with patch("src.analytics.traces._store_traces", new_callable=AsyncMock) as mock_store:
        trace = AgentTrace(
            trace_id="t1", org_id="o1", workflow_id="w1",
            question="q", question_type="s", source="cli",
        )
        await collector.collect(trace)
        mock_store.assert_awaited_once()
        assert len(collector._buffer) == 0


@pytest.mark.asyncio
async def test_collector_flush_empty_buffer():
    collector = TraceCollector()
    with patch("src.analytics.traces._store_traces", new_callable=AsyncMock) as mock_store:
        await collector.flush()
        mock_store.assert_not_awaited()


@pytest.mark.asyncio
async def test_collector_on_flush_callback():
    callback = AsyncMock()
    collector = TraceCollector(flush_threshold=1)
    collector.set_on_flush_callback(callback)
    with patch("src.analytics.traces._store_traces", new_callable=AsyncMock):
        trace = AgentTrace(
            trace_id="t1", org_id="o1", workflow_id="w1",
            question="q", question_type="s", source="cli",
        )
        await collector.collect(trace)
        callback.assert_awaited_once()


@pytest.mark.asyncio
async def test_collector_flush_error_does_not_raise():
    collector = TraceCollector(flush_threshold=1)
    with patch("src.analytics.traces._store_traces", side_effect=Exception("DB down")):
        trace = AgentTrace(
            trace_id="t1", org_id="o1", workflow_id="w1",
            question="q", question_type="s", source="cli",
        )
        # Should not raise
        await collector.collect(trace)


@pytest.mark.asyncio
async def test_collect_trace_node_populates_rubric_results():
    from src.agents.graph import collect_trace_node

    captured: list = []

    class _FakeCollector:
        async def collect(self, trace):
            captured.append(trace)

    with patch("src.agents.graph._trace_collector", _FakeCollector()):
        await collect_trace_node(
            {
                "org_id": "org-1",
                "workflow_id": "w-1",
                "question": "q",
                "question_type": "simple",
                "source": "cli",
                "confidence_score": 0.6,
                "published_urls": [],
                "rubric_evaluations": [
                    {"result": "needs_revision", "criteria": [], "iteration": 1}
                ],
                "_node_traces": [],
            }
        )

    assert len(captured) == 1
    assert captured[0].rubric_results == [
        {"result": "needs_revision", "criteria": [], "iteration": 1}
    ]

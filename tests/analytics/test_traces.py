import json
from datetime import datetime
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

    with patch("src.agents.graph._trace_collector", _FakeCollector()), patch(
        "src.agents.graph.store_episode", new_callable=AsyncMock, return_value="ep-1"
    ):
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


@pytest.mark.asyncio
async def test_purge_expired_traces_deletes_by_retention_window():
    from src.analytics import traces as traces_module

    with patch(
        "src.analytics.traces.fetch_all", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = [{"id": "t1"}, {"id": "t2"}]
        deleted = await traces_module._purge_expired_traces()

    assert deleted == 2
    sql = mock_fetch.await_args.args[0]
    assert "DELETE FROM agent_traces" in sql
    assert "$1::INT * INTERVAL '1 day'" in sql


@pytest.mark.asyncio
async def test_start_trace_retention_idempotent():
    from src.analytics import traces as traces_module

    await traces_module.stop_trace_retention()
    with patch("src.analytics.traces._trace_retention_loop", new_callable=AsyncMock):
        await traces_module.start_trace_retention()
        first = traces_module._trace_retention_task
        assert first is not None
        await traces_module.start_trace_retention()
        assert traces_module._trace_retention_task is first
        await traces_module.stop_trace_retention()
        assert traces_module._trace_retention_task is None


@pytest.mark.asyncio
async def test_purge_expired_traces_no_rows():
    from src.analytics import traces as traces_module

    with patch(
        "src.analytics.traces.fetch_all",
        new_callable=AsyncMock,
        return_value=[],
    ):
        count = await traces_module._purge_expired_traces()

    assert count == 0


@pytest.mark.asyncio
async def test_retention_loop_runs_once_and_stops():
    import asyncio

    from src.analytics import traces as traces_module

    stop_event = asyncio.Event()
    with (
        patch(
            "src.analytics.traces._purge_expired_traces",
            new_callable=AsyncMock,
            return_value=3,
        ) as mock_purge,
        patch(
            "src.analytics.traces.asyncio.Event",
            return_value=stop_event,
        ),
        patch("src.analytics.traces.logger") as mock_logger,
    ):
        stop_event.set()
        await traces_module._trace_retention_loop(
            interval_hours=0.0, stop_event=stop_event
        )

    mock_purge.assert_awaited_once()
    mock_logger.info.assert_called_once()
    assert mock_logger.info.call_args.args[0] == "trace_retention"
    assert mock_logger.info.call_args.kwargs["deleted"] == 3


@pytest.mark.asyncio
async def test_retention_loop_logs_failure():
    import asyncio

    from src.analytics import traces as traces_module

    stop_event = asyncio.Event()
    with (
        patch(
            "src.analytics.traces._purge_expired_traces",
            side_effect=Exception("DB down"),
        ),
        patch("src.analytics.traces.logger") as mock_logger,
    ):
        stop_event.set()
        await traces_module._trace_retention_loop(
            interval_hours=0.0, stop_event=stop_event
        )
    mock_logger.error.assert_called_once()
    assert mock_logger.error.call_args.args[0] == "trace_retention_failed"


@pytest.mark.asyncio
async def test_collect_trace_node_writes_episode():
    from src.agents.graph import collect_trace_node

    captured: list = []

    class _FakeCollector:
        async def collect(self, trace):
            captured.append(trace)

    state = {
        "org_id": "org-1",
        "workflow_id": "w-1",
        "question": "q",
        "question_type": "simple",
        "source": "cli",
        "confidence_score": 0.6,
        "published_urls": [{"platform": "draftly"}],
        "rubric_evaluations": [],
        "_node_traces": [],
    }

    with patch("src.agents.graph._trace_collector", _FakeCollector()), patch(
        "src.agents.graph.store_episode", new_callable=AsyncMock, return_value="ep-1"
    ) as mock_ep:
        result = await collect_trace_node(state)

    assert result["episode_id"] == "ep-1"
    mock_ep.assert_awaited_once()
    assert mock_ep.await_args.kwargs["outcome"] == "published"


@pytest.mark.asyncio
async def test_collect_trace_node_rejected_outcome():
    from src.agents.graph import collect_trace_node

    captured: list = []

    class _FakeCollector:
        async def collect(self, trace):
            captured.append(trace)

    state = {
        "org_id": "org-1",
        "workflow_id": "w-1",
        "question": "q",
        "question_type": "simple",
        "source": "cli",
        "confidence_score": 0.6,
        "rubric_evaluations": [],
        "_node_traces": [],
    }

    with patch("src.agents.graph._trace_collector", _FakeCollector()), patch(
        "src.agents.graph.store_episode", new_callable=AsyncMock, return_value="ep-1"
    ) as mock_ep:
        result = await collect_trace_node(state)

    assert result["episode_id"] == "ep-1"
    mock_ep.assert_awaited_once()
    assert mock_ep.await_args.kwargs["outcome"] == "rejected"


@pytest.mark.asyncio
async def test_collect_trace_node_swallows_episode_failure():
    from src.agents.graph import collect_trace_node

    captured: list = []

    class _FakeCollector:
        async def collect(self, trace):
            captured.append(trace)

    state = {
        "org_id": "org-1",
        "workflow_id": "w-1",
        "question": "q",
        "question_type": "simple",
        "source": "cli",
        "confidence_score": 0.6,
        "published_urls": [{"platform": "draftly"}],
        "rubric_evaluations": [],
        "_node_traces": [],
    }

    with patch("src.agents.graph._trace_collector", _FakeCollector()), patch(
        "src.agents.graph.store_episode",
        new_callable=AsyncMock,
        side_effect=RuntimeError("db down"),
    ) as mock_ep:
        result = await collect_trace_node(state)

    assert "episode_id" not in result
    assert result["_trace_collected"] is True
    mock_ep.assert_awaited_once()
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_collect_trace_node_episode_without_collector():
    from src.agents.graph import collect_trace_node

    state = {
        "org_id": "org-1",
        "workflow_id": "w-1",
        "question": "q",
        "question_type": "simple",
        "source": "cli",
        "confidence_score": 0.6,
        "published_urls": [{"platform": "draftly"}],
        "rubric_evaluations": [],
        "_node_traces": [],
    }

    with patch("src.agents.graph._trace_collector", None), patch(
        "src.agents.graph.store_episode", new_callable=AsyncMock, return_value="ep-1"
    ) as mock_ep:
        result = await collect_trace_node(state)

    assert result["episode_id"] == "ep-1"
    mock_ep.assert_awaited_once()


def test_node_trace_token_usage_survives_payload_roundtrip():
    from src.analytics import traces

    trace = traces.AgentTrace(
        trace_id="t1", org_id="org-1", workflow_id="w1",
        question="q", question_type="how_to", source="cli",
        nodes_executed=["ai_review"],
        node_traces=[traces.NodeTrace(
            node_name="ai_review",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=100.0,
            token_usage=42,
        )],
        total_duration_ms=100.0,
    )
    payload = json.loads(traces._trace_to_payload(trace))
    restored = traces._dict_to_trace(payload)
    assert restored.node_traces[0].token_usage == 42

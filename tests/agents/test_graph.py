from unittest.mock import AsyncMock, patch

import pytest

from src.agents import graph as graph_module
from src.agents.graph import _wrap_node_with_tracing
from src.agents.state import DocumentationState
from src.integrations import llm as llm_module


class _FakeCollector:
    def __init__(self) -> None:
        self.traces: list = []

    async def collect(self, trace) -> None:
        self.traces.append(trace)


def _state(**overrides: object) -> DocumentationState:
    base: DocumentationState = {
        "org_id": "org-1",
        "source": "cli",
        "channel_id": "chan-1",
        "thread_id": "thread-1",
        "question": "How do I deploy?",
        "workflow_id": "wf-1",
        "confidence_score": 0.0,
        "human_decision": "",
        "human_feedback": "",
        "published_urls": [],
        "question_type": "moderate",
        "rubric_status": {},
        "rubric_evaluations": [],
        "node_traces": [],
        "_node_traces": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


@pytest.mark.asyncio
async def test_collect_trace_node_records_human_decisions():
    collector = _FakeCollector()
    graph_module._trace_collector = collector

    state = _state(
        human_decision="revise",
        human_feedback="Add a table",
        confidence_score=0.7,
    )
    with patch("src.agents.graph.store_episode", new_callable=AsyncMock) as mock_episode:
        mock_episode.return_value = "episode-1"
        await graph_module.collect_trace_node(state)

    assert len(collector.traces) == 1
    trace = collector.traces[0]
    assert trace.human_decisions == [
        {"decision": "revise", "feedback": "Add a table"}
    ]


@pytest.mark.asyncio
async def test_collect_trace_node_records_verification_results():
    collector = _FakeCollector()
    graph_module._trace_collector = collector

    rubric_status = {"satisfied": False, "needs_revision": True, "research_needed": False}
    state = _state(rubric_status=rubric_status)
    with patch("src.agents.graph.store_episode", new_callable=AsyncMock) as mock_episode:
        mock_episode.return_value = "episode-1"
        await graph_module.collect_trace_node(state)

    trace = collector.traces[0]
    assert trace.verification_results == [rubric_status]


@pytest.mark.asyncio
async def test_collect_trace_node_empty_optional_fields():
    collector = _FakeCollector()
    graph_module._trace_collector = collector

    state = _state()
    with patch("src.agents.graph.store_episode", new_callable=AsyncMock) as mock_episode:
        mock_episode.return_value = "episode-1"
        await graph_module.collect_trace_node(state)

    trace = collector.traces[0]
    assert trace.human_decisions == []
    assert trace.verification_results == []


@pytest.mark.asyncio
async def test_wrapped_node_records_isolated_token_usage():
    async def noisy(state):
        llm_module._token_usage.set(99)
        return {"ok": True}

    wrapped = _wrap_node_with_tracing("probe", noisy)
    state: dict = {}
    await wrapped(state)
    assert state["_node_traces"][0].node_name == "probe"
    assert state["_node_traces"][0].token_usage == 99

    async def silent(state):
        return {"ok": True}

    await _wrap_node_with_tracing("probe2", silent)({})
    assert llm_module.get_token_usage() == 0

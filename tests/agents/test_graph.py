import pytest

from src.agents.graph import _wrap_node_with_tracing
from src.integrations import llm as llm_module


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

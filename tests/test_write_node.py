from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_write_node_prefers_rubric_feedback():
    from src.agents.nodes.write import write_docs_node

    with (
        patch("src.agents.nodes.write.fetch_one", new_callable=AsyncMock) as mock_fetch,
        patch("src.agents.nodes.write.call_bedrock", new_callable=AsyncMock) as mock_llm,
    ):
        mock_fetch.return_value = {"id": "doc-1"}
        mock_llm.return_value = "# Title\n\nBody"
        state = {
            "org_id": "org-1",
            "question": "q",
            "knowledge_package": {},
            "doc_type": "howto",
            "support_thread_id": "",
            "rubric_feedback": "RUBRIC GAP: missing step",
            "human_feedback": "HUMAN NOTE",
        }
        result = await write_docs_node(state)

    prompt = mock_llm.await_args.args[0]
    assert "RUBRIC GAP: missing step" in prompt
    assert "HUMAN NOTE" not in prompt
    assert result["doc_id"] == "doc-1"


@pytest.mark.asyncio
async def test_write_node_falls_back_to_human_feedback():
    from src.agents.nodes.write import write_docs_node

    with (
        patch("src.agents.nodes.write.fetch_one", new_callable=AsyncMock) as mock_fetch,
        patch("src.agents.nodes.write.call_bedrock", new_callable=AsyncMock) as mock_llm,
    ):
        mock_fetch.return_value = {"id": "doc-2"}
        mock_llm.return_value = "# Title\n\nBody"
        state = {
            "org_id": "org-1",
            "question": "q",
            "knowledge_package": {},
            "doc_type": "howto",
            "support_thread_id": "",
            "human_feedback": "HUMAN NOTE",
        }
        await write_docs_node(state)

    prompt = mock_llm.await_args.args[0]
    assert "HUMAN NOTE" in prompt

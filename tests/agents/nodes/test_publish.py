from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_publish_wraps_relational_writes_in_transaction():
    from src.agents.nodes.publish import publish_node

    mock_conn = MagicMock()
    order: list[str] = []

    class FakeTx:
        async def __aenter__(self):
            order.append("tx_start")
            return mock_conn

        async def __aexit__(self, exc_type, exc, tb):
            order.append("tx_end")

    def fake_transaction():
        return FakeTx()

    state = {
        "org_id": "org-1",
        "doc_id": "doc-1",
        "draft_title": "How to deploy",
        "draft_content": "content here",
        "doc_type": "howto",
        "confidence_score": 0.9,
        "source": "cli",
        "source_metadata": {},
        "human_feedback": "looks good",
        "human_decision": "approve",
        "support_thread_id": "thread-1",
    }

    with patch(
        "src.agents.nodes.publish.transaction", side_effect=fake_transaction
    ), patch(
        "src.agents.nodes.publish.execute_conn", new_callable=AsyncMock
    ) as mock_exec, patch(
        "src.agents.nodes.publish.store_memory", new_callable=AsyncMock
    ) as mock_mem, patch(
        "src.agents.nodes.publish.store_audit_log", new_callable=AsyncMock
    ) as mock_audit, patch(
        "src.agents.nodes.publish.store_document_chunks", new_callable=AsyncMock
    ) as mock_chunks:
        async def _chunks(**kwargs):
            order.append("chunks")

        mock_chunks.side_effect = _chunks
        await publish_node(state)

    assert order == ["tx_start", "tx_end", "chunks"]
    for call in mock_mem.call_args_list:
        assert call.kwargs["conn"] is mock_conn
    assert mock_audit.call_args.kwargs["conn"] is mock_conn
    for call in mock_exec.call_args_list:
        assert call.args[0] is mock_conn


@pytest.mark.asyncio
async def test_publish_skips_embedding_when_transaction_fails():
    from src.agents.nodes.publish import publish_node

    def fail_transaction():
        raise RuntimeError("db down")

    state = {
        "org_id": "org-1",
        "doc_id": "doc-1",
        "draft_title": "T",
        "draft_content": "c",
        "doc_type": "howto",
        "confidence_score": 0.5,
        "source": "cli",
        "source_metadata": {},
    }

    with patch("src.agents.nodes.publish.transaction", side_effect=fail_transaction), patch(
        "src.agents.nodes.publish.store_document_chunks", new_callable=AsyncMock
    ) as mock_chunks, patch(
        "src.agents.nodes.publish.store_memory", new_callable=AsyncMock
    ), patch("src.agents.nodes.publish.store_audit_log", new_callable=AsyncMock):
        with pytest.raises(RuntimeError):
            await publish_node(state)

    mock_chunks.assert_not_awaited()

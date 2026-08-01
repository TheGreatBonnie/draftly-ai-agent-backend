"""Tests for organization/document persistence helpers."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.memory.organizations import link_workflow_to_document


@pytest.mark.asyncio
async def test_link_workflow_to_document_backfills_only_when_unset() -> None:
    """UPDATE targets the row and only fills a NULL workflow_id."""
    with patch("src.memory.organizations.execute", new_callable=AsyncMock) as mock_execute:
        await link_workflow_to_document("wf-123", "doc-456")

    mock_execute.assert_awaited_once()
    sql, wf, doc = mock_execute.await_args.args
    assert "UPDATE documentation" in sql
    assert "workflow_id" in sql
    assert "AND workflow_id IS NULL" in sql
    assert wf == "wf-123"
    assert doc == "doc-456"

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_search_organizational_memory_touches_last_accessed():
    from src.agents.tools.memory_tools import search_organizational_memory

    rows = [
        {"id": "mem-1", "memory_type": "organizational", "key": "k1", "value": {"v": 1}},
        {"id": "mem-2", "memory_type": "organizational", "key": "k2", "value": {"v": 2}},
    ]
    with patch(
        "src.agents.tools.memory_tools.search_memory",
        new_callable=AsyncMock,
        return_value=rows,
    ), patch(
        "src.agents.tools.memory_tools.update_memory_access", new_callable=AsyncMock
    ) as mock_update:
        result = await search_organizational_memory.ainvoke(
            {"org_id": "org-1", "key": "deploy"}
        )

    assert "k1" in result and "k2" in result
    assert mock_update.await_count == 2
    mock_update.assert_any_await("mem-1")
    mock_update.assert_any_await("mem-2")

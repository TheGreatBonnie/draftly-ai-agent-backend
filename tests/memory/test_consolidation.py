from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_consolidate_increments_frequency_on_repeat_lesson():
    from src.memory import consolidation

    episodes = [
        {"id": "ep-1", "input_summary": "Always use transactions."},
        {"id": "ep-2", "input_summary": "Always use transactions."},
    ]
    with patch(
        "src.memory.consolidation.fetch_all", new_callable=AsyncMock, return_value=episodes
    ), patch(
        "src.memory.consolidation.store_reflection", new_callable=AsyncMock
    ) as mock_store, patch(
        "src.memory.consolidation.increment_reflection_frequency",
        new_callable=AsyncMock,
    ) as mock_inc:
        created = await consolidation.consolidate("org-1")

    assert created == 1  # only the unique lesson is stored once
    mock_store.assert_awaited_once()
    mock_inc.assert_awaited_once()


@pytest.mark.asyncio
async def test_consolidation_loop_respects_enabled_flag():
    from src.analytics import consolidation_loop

    with patch(
        "src.analytics.consolidation_loop.consolidate", new_callable=AsyncMock
    ) as mock_cons, patch(
        "src.analytics.consolidation_loop.settings"
    ) as mock_settings:
        mock_settings.consolidation_enabled = False
        mock_settings.consolidation_interval_hours = 6
        await consolidation_loop._run_consolidation_once(["org-1"])

    mock_cons.assert_not_awaited()

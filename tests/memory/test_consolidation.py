from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_consolidate_stores_reflections_and_links_in_transaction():
    from src.memory.consolidation import (
        ConsolidatedReflection,
        ConsolidationOutput,
        consolidate,
    )

    episodes = [
        {"id": "ep-1", "input_summary": "Always use transactions."},
        {"id": "ep-2", "input_summary": "Verify rollback on partial failure."},
    ]
    output = ConsolidationOutput(reflections=[
        ConsolidatedReflection(
            lesson="Always use transactions.", confidence=0.9,
            tags=["db"], episode_indices=[0],
        ),
        ConsolidatedReflection(
            lesson="Verify rollback on partial failure.", confidence=0.8,
            tags=[], episode_indices=[1],
        ),
    ])

    mock_tx = AsyncMock()
    mock_conn = mock_tx.__aenter__.return_value
    with patch(
        "src.memory.consolidation.fetch_all", new_callable=AsyncMock,
        return_value=episodes,
    ), patch(
        "src.memory.consolidation.call_llm_structured", new_callable=AsyncMock,
        return_value=(output, ""),
    ), patch(
        "src.memory.consolidation.transaction", return_value=mock_tx,
    ), patch(
        "src.memory.consolidation.find_active_reflection", new_callable=AsyncMock,
        return_value=None,
    ) as mock_find, patch(
        "src.memory.consolidation.store_reflection", new_callable=AsyncMock,
        return_value="ref-1",
    ) as mock_store, patch(
        "src.memory.consolidation.link_episode_reflection", new_callable=AsyncMock,
    ) as mock_link:
        created = await consolidate("org-1")

    assert created == 2
    assert mock_store.await_count == 2
    assert mock_link.await_count == 2
    assert mock_find.await_count == 2
    for call in mock_store.await_args_list:
        assert call.kwargs["conn"] is mock_conn


@pytest.mark.asyncio
async def test_consolidate_dedupes_exact_lesson():
    from src.memory.consolidation import (
        ConsolidatedReflection,
        ConsolidationOutput,
        consolidate,
    )

    episodes = [{"id": "ep-1", "input_summary": "Always use transactions."}]
    output = ConsolidationOutput(reflections=[
        ConsolidatedReflection(
            lesson="Always use transactions.", confidence=0.9,
            tags=["db"], episode_indices=[0],
        ),
    ])

    with patch(
        "src.memory.consolidation.fetch_all", new_callable=AsyncMock,
        return_value=episodes,
    ), patch(
        "src.memory.consolidation.call_llm_structured", new_callable=AsyncMock,
        return_value=(output, ""),
    ), patch(
        "src.memory.consolidation.transaction", return_value=AsyncMock(),
    ), patch(
        "src.memory.consolidation.find_active_reflection", new_callable=AsyncMock,
        return_value="ref-existing",
    ), patch(
        "src.memory.consolidation.store_reflection", new_callable=AsyncMock,
    ) as mock_store, patch(
        "src.memory.consolidation.increment_reflection_frequency", new_callable=AsyncMock,
    ) as mock_inc:
        created = await consolidate("org-1")

    assert created == 0
    mock_store.assert_not_awaited()
    mock_inc.assert_awaited_once()


@pytest.mark.asyncio
async def test_consolidate_writes_nothing_on_parse_failure():
    from src.memory.consolidation import consolidate

    episodes = [{"id": "ep-1", "input_summary": "Always use transactions."}]
    with patch(
        "src.memory.consolidation.fetch_all", new_callable=AsyncMock,
        return_value=episodes,
    ), patch(
        "src.memory.consolidation.call_llm_structured", new_callable=AsyncMock,
        return_value=(None, "parse error"),
    ), patch(
        "src.memory.consolidation.transaction", new_callable=AsyncMock,
    ) as mock_tx, patch(
        "src.memory.consolidation.store_reflection", new_callable=AsyncMock,
    ) as mock_store:
        created = await consolidate("org-1")

    assert created == 0
    mock_store.assert_not_awaited()
    mock_tx.assert_not_awaited()


@pytest.mark.asyncio
async def test_consolidate_slices_into_batches_of_batch_size():
    from src.memory.consolidation import ConsolidationOutput, consolidate

    episodes = [{"id": f"ep-{i}", "input_summary": f"Lesson {i}"} for i in range(5)]
    calls = []

    async def fake_llm(prompt, schema, system_prompt, model, provider, temperature):
        calls.append(prompt)
        return (ConsolidationOutput(), "")

    with patch(
        "src.memory.consolidation.fetch_all", new_callable=AsyncMock,
        return_value=episodes,
    ), patch(
        "src.memory.consolidation.call_llm_structured", new_callable=AsyncMock,
        side_effect=fake_llm,
    ), patch(
        "src.memory.consolidation.settings", consolidation_batch_size=2,
    ), patch(
        "src.memory.consolidation.transaction", return_value=AsyncMock(),
    ):
        await consolidate("org-1")

    assert len(calls) == 3  # ceil(5 / 2)
    assert "0." in calls[0] and "Lesson 0" in calls[0]
    assert "0. Lesson 4" in calls[2]


@pytest.mark.asyncio
async def test_consolidate_uses_llm_model_and_requesty_provider():
    from src.memory.consolidation import ConsolidationOutput, consolidate

    with patch(
        "src.memory.consolidation.fetch_all", new_callable=AsyncMock,
        return_value=[{"id": "ep-1", "input_summary": "Lesson 1"}],
    ), patch(
        "src.memory.consolidation.call_llm_structured", new_callable=AsyncMock,
        return_value=(ConsolidationOutput(), ""),
    ) as mock_llm, patch(
        "src.memory.consolidation.settings", consolidation_batch_size=20, llm_model="model-x",
    ), patch(
        "src.memory.consolidation.transaction", return_value=AsyncMock(),
    ):
        await consolidate("org-1")

    kwargs = mock_llm.await_args.kwargs
    assert kwargs["model"] == "model-x"
    assert kwargs["provider"] == "requesty"
    assert kwargs["temperature"] == 0.0


@pytest.mark.asyncio
async def test_consolidate_skips_episodes_with_existing_reflections():
    from src.memory import consolidation

    with patch(
        "src.memory.consolidation.fetch_all", new_callable=AsyncMock, return_value=[],
    ) as mock_fetch, patch(
        "src.memory.consolidation.call_llm_structured", new_callable=AsyncMock,
    ) as mock_llm:
        created = await consolidation.consolidate("org-1")

    assert created == 0
    mock_llm.assert_not_awaited()
    sql = mock_fetch.await_args.args[0]
    assert "NOT EXISTS" in sql
    assert "episode_id = episodes.id" in sql


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

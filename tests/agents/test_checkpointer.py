from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents import checkpointer


@pytest.mark.asyncio
async def test_create_checkpointer_forces_pipeline_off() -> None:
    mock_saver = MagicMock()
    mock_saver.supports_pipeline = True
    mock_saver.setup = AsyncMock()
    mock_saver.__aenter__ = AsyncMock(return_value=mock_saver)
    mock_saver.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("src.agents.checkpointer.AsyncCockroachDBSaver") as mock_saver_class,
        patch.object(
            checkpointer.settings, "cockroachdb_url", "postgresql://u:h@c:26257/db"
        ),
    ):
        mock_saver_class.from_conn_string.return_value = mock_saver

        async with checkpointer.create_checkpointer() as saver:
            assert saver is mock_saver
            assert saver.supports_pipeline is False

    mock_saver_class.from_conn_string.assert_called_once_with("postgresql://u:h@c:26257/db")

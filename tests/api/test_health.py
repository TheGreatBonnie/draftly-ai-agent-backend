"""Tests for GET /api/health endpoint."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok():
    from src.api.routes.health import health

    result = await health()
    assert result == {"status": "ok"}

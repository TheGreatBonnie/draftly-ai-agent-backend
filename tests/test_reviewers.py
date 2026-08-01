from unittest.mock import AsyncMock, patch

import pytest

from src.memory.reviewers import (
    create_reviewer,
    get_reviewers_by_org,
    update_reviewer,
)


@pytest.mark.asyncio
async def test_create_reviewer():
    """Test creating a reviewer."""
    mock_row = {
        "id": "test-id",
        "org_id": "org-123",
        "name": "John Doe",
        "email": "john@example.com",
        "slack_user_id": "U123456",
        "discord_user_id": None,
        "notify_slack": True,
        "notify_discord": False,
        "notify_email": False,
        "is_active": True,
        "created_at": "2025-07-19T00:00:00",
        "updated_at": "2025-07-19T00:00:00",
    }

    with patch("src.memory.reviewers.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_row
        reviewer = await create_reviewer(
            org_id="org-123",
            name="John Doe",
            email="john@example.com",
            slack_user_id="U123456",
        )
        assert reviewer["name"] == "John Doe"
        assert reviewer["email"] == "john@example.com"


@pytest.mark.asyncio
async def test_get_reviewers_by_org():
    """Test getting reviewers by organization."""
    mock_rows = [
        {"id": "1", "name": "John", "is_active": True},
        {"id": "2", "name": "Jane", "is_active": True},
    ]

    with patch("src.memory.reviewers.fetch_all", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_rows
        reviewers = await get_reviewers_by_org("org-123")
        assert len(reviewers) == 2


@pytest.mark.asyncio
async def test_update_reviewer():
    """Test updating a reviewer."""
    mock_row = {
        "id": "test-id",
        "name": "John Updated",
        "notify_slack": False,
        "notify_email": True,
    }

    with patch("src.memory.reviewers.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_row
        updated = await update_reviewer(
            reviewer_id="test-id",
            name="John Updated",
            notify_slack=False,
            notify_email=True,
        )
        assert updated["name"] == "John Updated"
        assert updated["notify_email"] is True

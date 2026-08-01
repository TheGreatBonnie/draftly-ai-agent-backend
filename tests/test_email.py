from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.email import send_email, send_review_notification


@pytest.mark.asyncio
async def test_send_email():
    """Test sending email via SendGrid."""
    mock_response = MagicMock()
    mock_response.status_code = 202

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.integrations.email.settings") as mock_settings:
        mock_settings.sendgrid_api_key = MagicMock()
        mock_settings.sendgrid_api_key.get_secret_value.return_value = "test-key"
        mock_settings.sendgrid_from_email = "test@example.com"
        mock_settings.sendgrid_from_name = "Test"

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await send_email(
                to="recipient@example.com",
                subject="Test Subject",
                html_content="<h1>Test</h1>",
            )
            assert result["ok"] is True


@pytest.mark.asyncio
async def test_send_review_notification():
    """Test sending review notification email."""
    state = {
        "draft_title": "Test Doc",
        "confidence_score": 0.75,
        "source_type": "github_issue",
        "question": "How do I configure webhooks?",
    }

    with patch("src.integrations.email.send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"ok": True}
        result = await send_review_notification(
            to="reviewer@example.com",
            reviewer_name="John Doe",
            state=state,
            review_id="review-123",
            token="test-token",
        )
        assert result["ok"] is True
        mock_send.assert_called_once()

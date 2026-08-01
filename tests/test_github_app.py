from __future__ import annotations

import hashlib
import hmac
from unittest.mock import MagicMock, patch

from src.integrations.github_app import (
    generate_jwt,
    verify_webhook_signature,
)


class TestGenerateJwt:
    """Tests for JWT generation."""

    @patch("src.integrations.github_app.settings")
    @patch("src.integrations.github_app.jwt.encode")
    def test_generate_jwt_success(self, mock_encode, mock_settings):
        """Test successful JWT generation."""
        mock_settings.github_app_id = "12345"
        mock_settings.github_private_key_path = "/tmp/test_key.pem"

        with patch("builtins.open", MagicMock(return_value=b"test-key")):
            with patch("pathlib.Path.read_text", return_value="test-key"):
                mock_encode.return_value = "test-jwt-token"
                token = generate_jwt()
                assert token == "test-jwt-token"
                mock_encode.assert_called_once()


class TestVerifyWebhookSignature:
    """Tests for webhook signature verification."""

    @patch("src.integrations.github_app.settings")
    def test_valid_signature(self, mock_settings):
        """Test valid webhook signature."""
        mock_settings.github_webhook_secret.get_secret_value.return_value = "test-secret"

        payload = b"test-payload"
        secret = b"test-secret"
        mac = hmac.new(secret, msg=payload, digestmod=hashlib.sha256)
        signature = f"sha256={mac.hexdigest()}"

        assert verify_webhook_signature(payload, signature) is True

    @patch("src.integrations.github_app.settings")
    def test_invalid_signature(self, mock_settings):
        """Test invalid webhook signature."""
        mock_settings.github_webhook_secret.get_secret_value.return_value = "test-secret"

        payload = b"test-payload"
        signature = "sha256=invalidsignature"

        assert verify_webhook_signature(payload, signature) is False

    def test_missing_signature(self):
        """Test missing signature."""
        assert verify_webhook_signature(b"payload", "") is False
        assert verify_webhook_signature(b"payload", None) is False

    @patch("src.integrations.github_app.settings")
    def test_wrong_algorithm(self, mock_settings):
        """Test signature with wrong algorithm."""
        mock_settings.github_webhook_secret.get_secret_value.return_value = "test-secret"

        payload = b"test-payload"
        signature = "sha512=something"

        assert verify_webhook_signature(payload, signature) is False

    @patch("src.integrations.github_app.settings")
    def test_malformed_signature(self, mock_settings):
        """Test malformed signature string."""
        mock_settings.github_webhook_secret.get_secret_value.return_value = "test-secret"

        assert verify_webhook_signature(b"payload", "nodelimiter") is False

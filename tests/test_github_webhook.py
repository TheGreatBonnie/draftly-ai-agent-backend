from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def webhook_payload():
    """Sample webhook payload."""
    return {
        "action": "opened",
        "issue": {
            "number": 42,
            "title": "How to configure webhooks?",
            "body": "I need help setting up webhooks.",
        },
        "repository": {
            "full_name": "myorg/myrepo",
            "id": 12345,
            "owner": {"login": "myorg"},
        },
        "installation": {
            "id": 99999,
        },
    }


class TestGithubWebhook:
    """Tests for GitHub webhook endpoint."""

    @patch("src.api.routes.github.verify_webhook_signature")
    @patch("src.api.routes.github.get_installation_token", new_callable=AsyncMock)
    @patch("src.api.routes.github.run_github_pipeline", new_callable=AsyncMock)
    def test_webhook_valid_issue_event(
        self,
        mock_run_pipeline,
        mock_get_token,
        mock_verify,
        client,
        webhook_payload,
    ):
        """Test webhook processing for valid issue opened event."""
        mock_verify.return_value = True
        mock_get_token.return_value = "test-token"

        response = client.post(
            "/api/github/webhook",
            content=json.dumps(webhook_payload),
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "issues",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Processing issue event"

    @patch("src.api.routes.github.verify_webhook_signature")
    def test_webhook_invalid_signature(self, mock_verify, client):
        """Test webhook rejects invalid signature."""
        mock_verify.return_value = False

        response = client.post(
            "/api/github/webhook",
            content=json.dumps({"action": "opened"}),
            headers={
                "X-Hub-Signature-256": "sha256=invalid",
                "X-GitHub-Event": "issues",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 401

    @patch("src.api.routes.github.verify_webhook_signature")
    def test_webhook_ignores_non_issue_events(self, mock_verify, client):
        """Test webhook ignores non-issue events."""
        mock_verify.return_value = True

        response = client.post(
            "/api/github/webhook",
            content=json.dumps({"action": "opened"}),
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Event ignored"

    @patch("src.api.routes.github.verify_webhook_signature")
    def test_webhook_ignores_non_opened_actions(self, mock_verify, client):
        """Test webhook ignores issue events that aren't 'opened'."""
        mock_verify.return_value = True

        response = client.post(
            "/api/github/webhook",
            content=json.dumps({"action": "closed"}),
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "issues",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Event ignored"

    @patch("src.api.routes.github.verify_webhook_signature")
    def test_webhook_invalid_json(self, mock_verify, client):
        """Test webhook handles invalid JSON."""
        mock_verify.return_value = True

        response = client.post(
            "/api/github/webhook",
            content="not json",
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "issues",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 400

    @patch("src.memory.organizations.store_github_installation", new_callable=AsyncMock)
    @patch("src.memory.organizations.get_org_by_github", new_callable=AsyncMock)
    @patch("src.api.routes.github.verify_webhook_signature")
    def test_webhook_installation_created(
        self,
        mock_verify,
        mock_get_org,
        mock_store_installation,
        client,
    ):
        """Test webhook handles installation created event."""
        mock_verify.return_value = True
        mock_get_org.return_value = {"id": "org-123"}

        payload = {
            "action": "created",
            "installation": {
                "id": 42,
                "account": {"login": "myorg"},
            },
            "repositories": [
                {"full_name": "myorg/repo1", "id": 1},
                {"full_name": "myorg/repo2", "id": 2},
            ],
        }

        response = client.post(
            "/api/github/webhook",
            content=json.dumps(payload),
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "installation",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Installation created"
        mock_store_installation.assert_awaited_once_with(
            org_id="org-123",
            installation_id=42,
            github_org="myorg",
            repositories=[
                {"full_name": "myorg/repo1", "id": 1},
                {"full_name": "myorg/repo2", "id": 2},
            ],
        )

    @patch("src.memory.organizations.remove_github_installation", new_callable=AsyncMock)
    @patch("src.api.routes.github.verify_webhook_signature")
    def test_webhook_installation_deleted(
        self,
        mock_verify,
        mock_remove_installation,
        client,
    ):
        """Test webhook handles installation deleted event."""
        mock_verify.return_value = True

        payload = {
            "action": "deleted",
            "installation": {
                "id": 42,
                "account": {"login": "myorg"},
            },
        }

        response = client.post(
            "/api/github/webhook",
            content=json.dumps(payload),
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "installation",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Installation deleted"
        mock_remove_installation.assert_awaited_once_with(42)

    @patch("src.api.routes.github.verify_webhook_signature")
    def test_webhook_installation_unhandled_action(self, mock_verify, client):
        """Test webhook handles unhandled installation actions."""
        mock_verify.return_value = True

        payload = {
            "action": "suspend",
            "installation": {
                "id": 42,
                "account": {"login": "myorg"},
            },
        }

        response = client.post(
            "/api/github/webhook",
            content=json.dumps(payload),
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "installation",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Installation suspend (unhandled)"

    @patch("src.api.routes.github.verify_webhook_signature")
    def test_webhook_installation_malformed_payload(self, mock_verify, client):
        """Test webhook handles installation event with missing installation data."""
        mock_verify.return_value = True

        payload = {
            "action": "created",
        }

        response = client.post(
            "/api/github/webhook",
            content=json.dumps(payload),
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "installation",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "Missing installation in payload"

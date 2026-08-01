from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def _make_interaction(
    interaction_type: int = 3,
    custom_id: str = "discord_approve:test_token",
    message_embeds: list | None = None,
):
    """Build a Discord interaction payload."""
    return {
        "type": interaction_type,
        "data": {
            "custom_id": custom_id,
            "values": ["needs_context"] if "feedback" in custom_id else [],
        },
        "message": {
            "embeds": message_embeds or [
                {"description": "**Title:** Test Doc\n**Source:** github"}
            ],
        },
        "member": {"user": {"id": "12345"}},
    }


def _headers():
    return {"X-Signature-Timestamp": "123", "X-Signature-Ed25519": "abc"}


# ── PING ──


@patch("src.api.routes.discord._verify_signature", return_value=True)
def test_ping_returns_pong(mock_verify):
    resp = client.post(
        "/api/discord/interactions",
        json={"type": 1},
        headers=_headers(),
    )
    assert resp.status_code == 200
    assert resp.json() == {"type": 1}


# ── Signature verification ──


def test_missing_signature_returns_401():
    resp = client.post("/api/discord/interactions", json={})
    assert resp.status_code == 401


@patch("src.api.routes.discord._verify_signature", return_value=False)
def test_invalid_signature_returns_401(mock_verify):
    resp = client.post(
        "/api/discord/interactions",
        json={"type": 1},
        headers=_headers(),
    )
    assert resp.status_code == 401


# ── Button clicks ──


@patch("src.api.routes.discord._verify_signature", return_value=True)
@patch("src.api.routes.discord.resolve_interaction_token")
@patch("src.api.routes.discord.verify_review_token")
@patch("src.api.routes.discord.complete_review", new_callable=AsyncMock)
@patch("src.api.routes.discord.resume_review", new_callable=AsyncMock)
def test_approve_button(mock_resume, mock_complete, mock_verify_token, mock_resolve, mock_sig):
    mock_resolve.return_value = "full_token_abc"
    mock_verify_token.return_value = {"reviewer_id": "r1", "review_id": "rev1"}
    payload = _make_interaction(custom_id="discord_approve:shortkey1")
    resp = client.post(
        "/api/discord/interactions",
        json=payload,
        headers=_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == 7
    assert body["data"]["embeds"][0]["color"] == 3066993
    assert "Approved" in body["data"]["embeds"][0]["title"]
    assert body["data"]["components"] == []
    mock_resolve.assert_called_once_with("shortkey1")
    mock_verify_token.assert_called_once_with("full_token_abc")
    mock_complete.assert_called_once_with(
        review_id="rev1", status="approved", feedback=None
    )


@patch("src.api.routes.discord._verify_signature", return_value=True)
@patch("src.api.routes.discord.resolve_interaction_token")
@patch("src.api.routes.discord.verify_review_token")
@patch("src.api.routes.discord.complete_review", new_callable=AsyncMock)
@patch("src.api.routes.discord.resume_review", new_callable=AsyncMock)
def test_reject_button(mock_resume, mock_complete, mock_verify_token, mock_resolve, mock_sig):
    mock_resolve.return_value = "full_token_abc"
    mock_verify_token.return_value = {"reviewer_id": "r1", "review_id": "rev1"}
    payload = _make_interaction(custom_id="discord_reject:shortkey2")
    resp = client.post(
        "/api/discord/interactions",
        json=payload,
        headers=_headers(),
    )
    body = resp.json()
    assert body["type"] == 7
    assert body["data"]["embeds"][0]["color"] == 15158332
    assert "Rejected" in body["data"]["embeds"][0]["title"]
    mock_complete.assert_called_once_with(
        review_id="rev1", status="rejected", feedback=None
    )


@patch("src.api.routes.discord._verify_signature", return_value=True)
@patch("src.api.routes.discord.resolve_interaction_token")
@patch("src.api.routes.discord.verify_review_token")
@patch("src.api.routes.discord.complete_review", new_callable=AsyncMock)
@patch("src.api.routes.discord.resume_review", new_callable=AsyncMock)
def test_revise_button(mock_resume, mock_complete, mock_verify_token, mock_resolve, mock_sig):
    mock_resolve.return_value = "full_token_abc"
    mock_verify_token.return_value = {"reviewer_id": "r1", "review_id": "rev1"}
    payload = _make_interaction(custom_id="discord_revise:shortkey3")
    resp = client.post(
        "/api/discord/interactions",
        json=payload,
        headers=_headers(),
    )
    body = resp.json()
    assert body["type"] == 7
    assert body["data"]["embeds"][0]["color"] == 16776960
    mock_complete.assert_called_once_with(
        review_id="rev1", status="needs_changes", feedback=None
    )


# ── Select menu ──


@patch("src.api.routes.discord._verify_signature", return_value=True)
@patch("src.api.routes.discord.resolve_interaction_token")
@patch("src.api.routes.discord.verify_review_token")
@patch("src.api.routes.discord.complete_review", new_callable=AsyncMock)
@patch("src.api.routes.discord.resume_review", new_callable=AsyncMock)
def test_feedback_select(mock_resume, mock_complete, mock_verify_token, mock_resolve, mock_sig):
    mock_resolve.return_value = "full_token_abc"
    mock_verify_token.return_value = {"reviewer_id": "r1", "review_id": "rev1"}
    payload = _make_interaction(custom_id="discord_feedback:shortkey4")
    payload["data"]["values"] = ["needs_context"]
    resp = client.post(
        "/api/discord/interactions",
        json=payload,
        headers=_headers(),
    )
    assert resp.status_code == 200
    mock_complete.assert_called_once_with(
        review_id="rev1", status="needs_changes", feedback="needs_context"
    )


# ── Expired token ──


@patch("src.api.routes.discord._verify_signature", return_value=True)
@patch("src.api.routes.discord.resolve_interaction_token", return_value=None)
def test_expired_token_returns_error(mock_resolve, mock_sig):
    payload = _make_interaction(custom_id="discord_approve:expired_key")
    resp = client.post(
        "/api/discord/interactions",
        json=payload,
        headers=_headers(),
    )
    body = resp.json()
    assert body["type"] == 4
    assert "expired" in body["data"]["content"].lower()


# ── Unknown short key ──


@patch("src.api.routes.discord._verify_signature", return_value=True)
@patch("src.api.routes.discord.resolve_interaction_token", return_value=None)
def test_unknown_short_key_returns_expired_error(mock_resolve, mock_sig):
    payload = _make_interaction(custom_id="discord_approve:unknownkey")
    resp = client.post(
        "/api/discord/interactions",
        json=payload,
        headers=_headers(),
    )
    body = resp.json()
    assert body["type"] == 4
    assert "expired" in body["data"]["content"].lower()


# ── Unknown interaction type ──


@patch("src.api.routes.discord._verify_signature", return_value=True)
def test_unknown_interaction_type(mock_sig):
    resp = client.post(
        "/api/discord/interactions",
        json={"type": 99},
        headers=_headers(),
    )
    assert resp.status_code == 400


# ── Invalid custom_id ──


@patch("src.api.routes.discord._verify_signature", return_value=True)
@patch("src.api.routes.discord.verify_review_token")
def test_invalid_custom_id(mock_verify_token, mock_sig):
    mock_verify_token.return_value = {"reviewer_id": "r1", "review_id": "rev1"}
    payload = _make_interaction(custom_id="no_colon_here")
    resp = client.post(
        "/api/discord/interactions",
        json=payload,
        headers=_headers(),
    )
    assert resp.status_code == 400

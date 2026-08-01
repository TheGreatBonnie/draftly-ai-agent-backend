from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import cast

from src.config import settings


def generate_review_token(
    reviewer_id: str,
    review_id: str,
    expiry_hours: int = 24,
) -> str:
    """Generate time-limited token for quick actions."""
    payload = {
        "reviewer_id": reviewer_id,
        "review_id": review_id,
        "expires_at": (datetime.now(UTC) + timedelta(hours=expiry_hours)).isoformat(),
    }
    data = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(
        settings.secret_key.encode(), data.encode(), hashlib.sha256
    ).hexdigest()
    return f"{data}.{signature}"


def verify_review_token(token: str) -> dict | None:
    """Verify and decode review token. Returns None if invalid/expired."""
    try:
        data, signature = token.split(".")
        expected = hmac.new(
            settings.secret_key.encode(), data.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(data))
        if datetime.fromisoformat(payload["expires_at"]) < datetime.now(UTC):
            return None
        return cast(dict, payload)
    except Exception:
        return None

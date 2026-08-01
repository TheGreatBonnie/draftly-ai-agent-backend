from src.security.tokens import generate_review_token, verify_review_token


def test_generate_and_verify_token():
    """Test generating and verifying a valid token."""
    token = generate_review_token(
        reviewer_id="reviewer-123",
        review_id="review-456",
        expiry_hours=24,
    )
    payload = verify_review_token(token)
    assert payload is not None
    assert payload["reviewer_id"] == "reviewer-123"
    assert payload["review_id"] == "review-456"


def test_reject_expired_token():
    """Test rejecting an expired token."""
    token = generate_review_token(
        reviewer_id="reviewer-123",
        review_id="review-456",
        expiry_hours=-1,  # Already expired
    )
    payload = verify_review_token(token)
    assert payload is None


def test_reject_tampered_token():
    """Test rejecting a tampered token."""
    token = generate_review_token(
        reviewer_id="reviewer-123",
        review_id="review-456",
    )
    # Tamper with the token
    tampered_token = token[:-5] + "XXXXX"
    payload = verify_review_token(tampered_token)
    assert payload is None


def test_reject_invalid_format():
    """Test rejecting token with invalid format."""
    payload = verify_review_token("invalid-token")
    assert payload is None

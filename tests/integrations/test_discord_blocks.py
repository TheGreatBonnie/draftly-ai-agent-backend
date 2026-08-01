from src.integrations.discord_blocks import (
    _truncate_draft,
    build_discord_result_embed,
    build_discord_review_card,
)


def test_truncate_draft_short():
    assert _truncate_draft("hello", 500) == "hello"


def test_truncate_draft_long():
    long = "word " * 200
    result = _truncate_draft(long, 500)
    assert len(result) <= 510
    assert result.endswith("...")


def test_build_review_card_structure():
    card = build_discord_review_card(
        title="Test Doc",
        source="github",
        confidence=0.85,
        dashboard_url="https://example.com/review/123",
        review_token="tok_abc",
        draft_content="Some draft content",
    )

    assert "embeds" in card
    assert "components" in card
    assert "content" in card
    assert len(card["embeds"]) == 1


def test_build_review_card_embed_fields():
    card = build_discord_review_card(
        title="Test Doc",
        source="slack",
        confidence=0.9,
        dashboard_url="https://example.com/review/123",
        review_token="tok_abc",
        draft_content="Draft text",
    )

    embed = card["embeds"][0]
    assert embed["title"] == "Documentation Review Required"
    assert embed["color"] == 49407
    assert "Test Doc" in embed["description"]
    assert "slack" in embed["description"]
    assert "90%" in embed["description"]
    assert embed["footer"]["text"] == "Review expires in 24 hours"


def test_build_review_card_components():
    card = build_discord_review_card(
        title="Test Doc",
        source="cli",
        confidence=0.7,
        dashboard_url="https://example.com/review/123",
        review_token="tok_xyz",
        draft_content="Content",
    )

    components = card["components"]
    assert len(components) == 3

    link_button = components[0]["components"]
    assert len(link_button) == 1
    assert link_button[0]["label"] == "Read Full Draft"
    assert link_button[0]["style"] == 5
    assert link_button[0]["url"] == "https://example.com/review/123"

    buttons = components[1]["components"]
    assert len(buttons) == 3
    assert buttons[0]["label"] == "Approve"
    assert buttons[0]["style"] == 3
    assert buttons[0]["custom_id"].startswith("discord_approve:")
    assert buttons[1]["label"] == "Reject"
    assert buttons[1]["style"] == 4
    assert buttons[1]["custom_id"].startswith("discord_reject:")
    assert buttons[2]["label"] == "Revise"
    assert buttons[2]["style"] == 2
    assert buttons[2]["custom_id"].startswith("discord_revise:")

    select = components[2]["components"]
    assert len(select) == 1
    assert select[0]["type"] == 3
    assert select[0]["custom_id"].startswith("discord_feedback:")
    assert len(select[0]["options"]) == 5


def test_build_review_card_custom_id_uses_short_key():
    card = build_discord_review_card(
        title="Doc",
        source="github",
        confidence=0.5,
        dashboard_url="https://example.com",
        review_token="my_special_token_123",
        draft_content="content",
    )

    buttons = card["components"][1]["components"]
    for btn in buttons:
        parts = btn["custom_id"].split(":")
        assert len(parts) == 2
        short_key = parts[1]
        assert len(short_key) <= 100
        assert short_key != "my_special_token_123"

    select = card["components"][2]["components"][0]
    parts = select["custom_id"].split(":")
    assert len(parts) == 2
    assert parts[1] != "my_special_token_123"


def test_build_review_card_short_key_stored_in_map():
    from src.integrations.discord_interactions import resolve_interaction_token

    review_token = "test_full_token_abc"
    card = build_discord_review_card(
        title="Doc",
        source="github",
        confidence=0.5,
        dashboard_url="https://example.com",
        review_token=review_token,
        draft_content="content",
    )

    buttons = card["components"][1]["components"]
    short_key = buttons[0]["custom_id"].split(":")[1]
    assert resolve_interaction_token(short_key) == review_token


def test_build_review_card_empty_content():
    card = build_discord_review_card(
        title="Empty Doc",
        source="cli",
        confidence=0.0,
        dashboard_url="https://example.com",
        review_token="tok",
        draft_content="",
    )

    assert len(card["embeds"]) == 1
    assert card["embeds"][0]["fields"][0]["value"] == "No content"


def test_build_result_embed_approved():
    result = build_discord_result_embed("approved", "Test Doc")
    embed = result["embeds"][0]
    assert "Approved" in embed["title"]
    assert embed["color"] == 3066993
    assert result["components"] == []


def test_build_result_embed_rejected():
    result = build_discord_result_embed("rejected", "Test Doc")
    embed = result["embeds"][0]
    assert "Rejected" in embed["title"]
    assert embed["color"] == 15158332


def test_build_result_embed_needs_changes():
    result = build_discord_result_embed("needs_changes", "Test Doc")
    embed = result["embeds"][0]
    assert "Changes Requested" in embed["title"]
    assert embed["color"] == 16776960


def test_build_result_embed_unknown_status():
    result = build_discord_result_embed("unknown", "Test Doc")
    embed = result["embeds"][0]
    assert embed["color"] == 10070709

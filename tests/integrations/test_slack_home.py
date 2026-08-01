"""Tests for App Home view builder."""
import pytest


def test_build_app_home_returns_view():
    from src.integrations.slack_home import build_app_home

    view = build_app_home(team_name="Acme Corp", pipeline_count=5)
    assert view["type"] == "home"
    assert "blocks" in view


def test_build_app_home_includes_team_name():
    from src.integrations.slack_home import build_app_home

    view = build_app_home(team_name="Test Workspace", pipeline_count=0)
    blocks_text = str(view["blocks"])
    assert "Test Workspace" in blocks_text


def test_build_app_home_suggested_prompts():
    from src.integrations.slack_home import build_suggested_prompts

    prompts = build_suggested_prompts()
    assert len(prompts) == 3
    assert all("text" in p for p in prompts)

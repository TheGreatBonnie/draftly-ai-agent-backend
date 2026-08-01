from unittest.mock import AsyncMock, patch

import pytest

from src.analytics.improver import (
    ImprovementProposal,
    generate_improvements,
    create_improvement_proposals,
    _parse_json_response,
)


def test_improvement_proposal_defaults():
    p = ImprovementProposal(id="p1", org_id="o1", improvement_type="prompt", proposed_changes={}, rationale="test")
    assert p.status == "pending"
    assert p.reviewed_by is None


def test_parse_json_response_direct():
    result = _parse_json_response('{"prompts": []}')
    assert result["prompts"] == []


def test_parse_json_response_fallback():
    result = _parse_json_response('text {"prompts": []} text')
    assert result["prompts"] == []


def test_parse_json_response_invalid():
    result = _parse_json_response("garbage")
    assert "error" in result


@pytest.mark.asyncio
async def test_generate_improvements_llm_success():
    mock_response = '{"prompts": [], "tools": [], "rubrics": []}'
    with patch("src.analytics.improver.call_llm", new_callable=AsyncMock, return_value=mock_response):
        result = await generate_improvements({"metrics": {}}, {"prompts": {}})
        assert result["prompts"] == []


@pytest.mark.asyncio
async def test_generate_improvements_llm_failure():
    with patch("src.analytics.improver.call_llm", side_effect=Exception("LLM down")):
        result = await generate_improvements({"metrics": {}}, {"prompts": {}})
        assert "error" in result


@pytest.mark.asyncio
async def test_create_proposals_stores_to_db():
    improvements = {
        "prompts": [{"node": "write_docs", "improved_prompt": "new", "rationale": "better"}],
        "tools": [],
        "rubrics": [],
    }
    with patch("src.analytics.improver._store_proposal", new_callable=AsyncMock) as mock_store:
        proposals = await create_improvement_proposals("org1", improvements)
        assert len(proposals) == 1
        mock_store.assert_awaited_once()

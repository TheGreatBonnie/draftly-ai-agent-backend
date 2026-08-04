from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config import Settings
from src.integrations.llm import (
    call_llm,
    call_llm_structured,
    get_llm,
    stage_llm_kwargs,
    stream_llm,
)


def test_nvidia_model_aliases_read_dotted_env_vars(monkeypatch):
    monkeypatch.setenv("COCKROACHDB_URL", "postgresql://dummy/dummy")
    monkeypatch.setenv("GLM_5.2_MODEL", "z-ai/glm-5.2-custom")
    monkeypatch.setenv("DEEPSEEK_V4_PRO_MODEL", "deepseek-ai/deepseek-v4-pro-custom")
    settings = Settings(_env_file=None)
    assert settings.nvidia_glm_model == "z-ai/glm-5.2-custom"
    assert settings.nvidia_deepseek_v4_pro == "deepseek-ai/deepseek-v4-pro-custom"
    assert settings.research_provider == "requesty"
    assert settings.research_nvidia_model == ""


def test_nvidia_model_defaults(monkeypatch):
    monkeypatch.setenv("COCKROACHDB_URL", "postgresql://dummy/dummy")
    settings = Settings(_env_file=None)
    assert settings.nvidia_glm_model == "z-ai/glm-5.2"
    assert settings.nvidia_deepseek_v4_flash == "deepseek-ai/deepseek-v4-flash"
    assert settings.nvidia_minimax_m3 == "minimax-ai/minimax-m3"
    assert settings.nvidia_kimi_k2_6 == "moonshotai/kimi-k2.6"
    assert settings.review_provider == "requesty"
    assert settings.review_nvidia_model == ""
    assert settings.rubric_grader_nvidia_model == ""
    assert settings.analysis_nvidia_model == ""


def test_rubric_limits_defaults(monkeypatch):
    monkeypatch.setenv("COCKROACHDB_URL", "postgresql://dummy/dummy")
    settings = Settings(_env_file=None)
    assert settings.llm_timeout == 60
    assert settings.llm_max_retries == 2
    assert settings.rubric_max_content_chars == 20000
    assert settings.rubric_max_run_tokens == 20000


def test_get_llm_requesty_returns_chat_openai(monkeypatch):
    monkeypatch.setattr("src.integrations.llm.settings", _fake_settings())
    assert isinstance(get_llm("tensorx/deepseek-v4-flash", provider="requesty"), ChatOpenAI)


def test_get_llm_nvidia_returns_chat_nvidia(monkeypatch):
    monkeypatch.setattr("src.integrations.llm.settings", _fake_settings())
    llm = get_llm("deepseek-ai/deepseek-v4-pro", provider="nvidia")
    assert isinstance(llm, ChatNVIDIA)
    assert llm.model_kwargs["chat_template_kwargs"] == {
        "thinking": True,
        "reasoning_effort": "max",
    }


def test_get_llm_requesty_sets_timeout_and_retries(monkeypatch):
    monkeypatch.setattr("src.integrations.llm.settings", _fake_settings())
    llm = get_llm("tensorx/deepseek-v4-flash", provider="requesty")
    assert llm.request_timeout == 60
    assert llm.max_retries == 2


@pytest.mark.asyncio
async def test_call_llm_returns_content_only(monkeypatch):
    fake_llm = _FakeLLM(
        AIMessage(
            content="the answer",
            additional_kwargs={"reasoning_content": "step 1 thinking"},
        )
    )
    monkeypatch.setattr("src.integrations.llm.get_llm", lambda *a, **kw: fake_llm)
    result = await call_llm("question", provider="nvidia")
    assert result == "the answer"
    assert fake_llm.received_messages[0].content == "question"
    assert isinstance(fake_llm.received_messages[0], HumanMessage)


@pytest.mark.asyncio
async def test_call_llm_passes_system_prompt(monkeypatch):
    fake_llm = _FakeLLM(AIMessage(content="{}"))
    monkeypatch.setattr("src.integrations.llm.get_llm", lambda *a, **kw: fake_llm)
    await call_llm("q", system_prompt="sys", provider="requesty")
    assert isinstance(fake_llm.received_messages[0], SystemMessage)
    assert fake_llm.received_messages[0].content == "sys"


def test_stage_llm_kwargs_requesty(monkeypatch):
    monkeypatch.setattr("src.integrations.llm.settings", _fake_settings())
    assert stage_llm_kwargs("research") == {
        "model": "tensorx/deepseek-v4-flash",
        "provider": "requesty",
    }


def test_stage_llm_kwargs_nvidia(monkeypatch):
    settings = _fake_settings()
    settings.research_provider = "nvidia"
    settings.research_nvidia_model = ""
    monkeypatch.setattr("src.integrations.llm.settings", settings)
    assert stage_llm_kwargs("research") == {
        "model": "deepseek-ai/deepseek-v4-flash",
        "provider": "nvidia",
    }


def test_stage_llm_kwargs_nvidia_override(monkeypatch):
    settings = _fake_settings()
    settings.research_provider = "nvidia"
    settings.research_nvidia_model = "z-ai/glm-5.2"
    monkeypatch.setattr("src.integrations.llm.settings", settings)
    assert stage_llm_kwargs("research") == {
        "model": "z-ai/glm-5.2",
        "provider": "nvidia",
    }


def test_stage_llm_kwargs_unknown_stage(monkeypatch):
    monkeypatch.setattr("src.integrations.llm.settings", _fake_settings())
    with pytest.raises(ValueError):
        stage_llm_kwargs("nope")


@pytest.mark.asyncio
async def test_call_llm_strips_think_tags_for_nvidia(monkeypatch):
    fake_llm = _FakeLLM(
        AIMessage(
            content="<think>step 1 reasoning</think>{\"ok\": true}",
            additional_kwargs={"reasoning_content": "step 1 reasoning"},
        )
    )
    monkeypatch.setattr("src.integrations.llm.get_llm", lambda *a, **kw: fake_llm)
    result = await call_llm("q", provider="nvidia")
    assert result == '{"ok": true}'


@pytest.mark.asyncio
async def test_stream_llm_yields_reasoning_and_content(monkeypatch):
    class _StreamFake:
        async def astream(self, messages):
            yield AIMessage(content="", additional_kwargs={"reasoning_content": "think"})
            yield AIMessage(content="out")

    monkeypatch.setattr("src.integrations.llm.get_llm", lambda *a, **kw: _StreamFake())
    chunks = [pair async for pair in stream_llm("q", provider="nvidia")]
    assert ("think", "") in chunks
    assert (None, "out") in chunks


class _FakeLLM:
    def __init__(self, response):
        self._response = response
        self.received_messages = []

    async def ainvoke(self, messages):
        self.received_messages = messages
        return self._response


def _fake_settings():
    from types import SimpleNamespace

    return SimpleNamespace(
        llm_model="tensorx/deepseek-v4-flash",
        llm_timeout=60,
        llm_max_retries=2,
        requesty_api_key="k",
        requesty_base_url="https://router.requesty.ai/v1",
        nvidia_api_key=type("S", (), {"get_secret_value": lambda self: "nvapi-test"})(),
        nvidia_glm_model="z-ai/glm-5.2",
        nvidia_deepseek_v4_pro="deepseek-ai/deepseek-v4-pro",
        nvidia_deepseek_v4_flash="deepseek-ai/deepseek-v4-flash",
        nvidia_minimax_m3="minimax-ai/minimax-m3",
        nvidia_kimi_k2_6="moonshotai/kimi-k2.6",
        research_model="tensorx/deepseek-v4-flash",
        research_provider="requesty",
        research_nvidia_model="",
        review_nvidia_model="",
        rubric_grader_nvidia_model="",
        analysis_nvidia_model="",
    )


class _FakeVerdict(BaseModel):
    explanation: str
    result: str


class _FakeStructuredLLM:
    def __init__(self, verdict):
        self._verdict = verdict
        self.calls: list[str] = []

    def with_structured_output(self, schema, method=None, include_raw=False):
        self.calls.append(method or "default")
        if self._verdict is None:
            raise ValueError(f"method {method} not supported")
        return _FakeStructuredRunnable(self._verdict)


class _FakeStructuredRunnable:
    def __init__(self, verdict):
        self._verdict = verdict

    async def ainvoke(self, messages):
        return {"raw": None, "parsed": self._verdict, "parsing_error": None}


@pytest.mark.asyncio
async def test_call_llm_structured_returns_parsed_model(monkeypatch):
    verdict = _FakeVerdict(explanation="ok", result="satisfied")
    fake_llm = _FakeStructuredLLM(verdict)
    monkeypatch.setattr("src.integrations.llm.get_llm", lambda *a, **kw: fake_llm)
    result, error = await call_llm_structured(
        prompt="q", schema=_FakeVerdict, system_prompt="sys"
    )
    assert isinstance(result, _FakeVerdict)
    assert result.result == "satisfied"
    assert error == ""
    assert fake_llm.calls == ["json_schema"]


@pytest.mark.asyncio
async def test_call_llm_structured_falls_back_to_function_calling(monkeypatch):
    class _FallbackLLM:
        def with_structured_output(self, schema, method=None, include_raw=False):
            if method == "json_schema":
                raise ValueError("not supported")
            return _FakeStructuredRunnable(_FakeVerdict(explanation="e", result="needs_revision"))

    monkeypatch.setattr("src.integrations.llm.get_llm", lambda *a, **kw: _FallbackLLM())
    result, error = await call_llm_structured(prompt="q", schema=_FakeVerdict)
    assert isinstance(result, _FakeVerdict)
    assert result.result == "needs_revision"
    assert error == ""


@pytest.mark.asyncio
async def test_call_llm_structured_never_raises(monkeypatch):
    class _AlwaysFailLLM:
        def with_structured_output(self, schema, method=None, include_raw=False):
            raise ValueError("nope")

    monkeypatch.setattr("src.integrations.llm.get_llm", lambda *a, **kw: _AlwaysFailLLM())
    result, error = await call_llm_structured(prompt="q", schema=_FakeVerdict)
    assert result is None
    assert error == "structured_output_failed"


@pytest.mark.asyncio
async def test_call_llm_structured_absorbs_get_llm_failure(monkeypatch):
    def raising_get_llm(*a, **kw):
        raise ValueError("bad provider config")

    monkeypatch.setattr("src.integrations.llm.get_llm", raising_get_llm)
    result, error = await call_llm_structured(prompt="q", schema=_FakeVerdict)
    assert result is None
    assert error == "structured_output_failed"


@pytest.mark.asyncio
async def test_call_llm_records_token_usage_in_contextvar():
    from src.integrations import llm as llm_module

    class _Msg:
        content = "hi"
        usage_metadata = {"total_tokens": 42}

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = _Msg()

    llm_module.reset_token_usage()
    with patch.object(llm_module, "get_llm", return_value=mock_llm):
        text = await llm_module.call_llm("prompt")

    assert text == "hi"
    assert llm_module.get_token_usage() == 42


@pytest.mark.asyncio
async def test_reset_token_usage_zeroes_counter():
    from src.integrations import llm as llm_module

    llm_module._token_usage.set(100)
    llm_module.reset_token_usage()
    assert llm_module.get_token_usage() == 0


@pytest.mark.asyncio
async def test_call_llm_structured_records_token_usage_in_contextvar():
    from src.integrations import llm as llm_module

    class _Msg:
        content = "hi"
        usage_metadata = {"total_tokens": 42}

    class _Schema(BaseModel):
        pass

    mock_llm = AsyncMock()
    mock_llm.with_structured_output = Mock(return_value=mock_llm)
    mock_llm.ainvoke.return_value = {
        "raw": _Msg(),
        "parsed": _Schema(),
        "parsing_error": None,
    }

    llm_module.reset_token_usage()
    with patch.object(llm_module, "get_llm", return_value=mock_llm):
        parsed, err = await llm_module.call_llm_structured("prompt", _Schema)

    assert parsed is not None
    assert err == ""
    assert llm_module.get_token_usage() == 42


@pytest.mark.asyncio
async def test_call_llm_structured_nvidia_skips_include_raw(monkeypatch):
    class _NvidiaRunnable:
        def __init__(self, verdict):
            self._verdict = verdict

        async def ainvoke(self, messages):
            return self._verdict

    class _NvidiaLLM:
        def __init__(self):
            self.include_raws: list[bool] = []

        def with_structured_output(self, schema, method=None, include_raw=False):
            self.include_raws.append(include_raw)
            if include_raw:
                raise NotImplementedError("include_raw=True is not implemented")
            return _NvidiaRunnable(_FakeVerdict(explanation="e", result="satisfied"))

    fake = _NvidiaLLM()
    monkeypatch.setattr("src.integrations.llm.get_llm", lambda *a, **kw: fake)
    result, error = await call_llm_structured(prompt="q", schema=_FakeVerdict, provider="nvidia")
    assert isinstance(result, _FakeVerdict)
    assert error == ""
    assert all(r is False for r in fake.include_raws)

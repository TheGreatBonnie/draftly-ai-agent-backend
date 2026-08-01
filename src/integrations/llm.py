from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from typing import Any, TypedDict

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config import settings

logger = structlog.get_logger()

_llm_cache: dict[str, ChatOpenAI] = {}
_nvidia_cache: dict[str, ChatNVIDIA] = {}


def _get_requesty_llm(
    model: str | None = None, temperature: float = 0.3, max_tokens: int = 4096
) -> ChatOpenAI:
    """Get a ChatOpenAI instance routed through Requesty."""
    model = model or settings.llm_model
    cache_key = f"{model}:{temperature}:{max_tokens}"
    if cache_key not in _llm_cache:
        _llm_cache[cache_key] = ChatOpenAI(  # type: ignore[call-arg]
            openai_api_key=settings.requesty_api_key,
            openai_api_base=settings.requesty_base_url,
            model_name=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries,
        )
    return _llm_cache[cache_key]


def get_nvidia_llm(
    model: str | None = None, temperature: float = 0.3, max_tokens: int = 4096
) -> ChatNVIDIA:
    """Get a cached ChatNVIDIA instance. Enables reasoning via chat_template_kwargs."""
    model = model or settings.nvidia_deepseek_v4_flash
    cache_key = f"nvidia:{model}:{temperature}:{max_tokens}"
    if cache_key not in _nvidia_cache:
        _nvidia_cache[cache_key] = ChatNVIDIA(  # type: ignore[call-arg]
            nvidia_api_key=settings.nvidia_api_key.get_secret_value() or None,
            model=model,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            model_kwargs={
                "chat_template_kwargs": {"thinking": True, "reasoning_effort": "max"}
            },
        )
    return _nvidia_cache[cache_key]


def get_llm(
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    provider: str = "requesty",
) -> BaseChatModel:
    """Get a chat model instance for the given provider (requesty | nvidia)."""
    if provider == "nvidia":
        return get_nvidia_llm(model, temperature=temperature, max_tokens=max_tokens)
    return _get_requesty_llm(model, temperature=temperature, max_tokens=max_tokens)


def _extract_reasoning(message: BaseMessage) -> Any:
    if not isinstance(message, AIMessage):
        return None
    return message.additional_kwargs.get("reasoning") or message.additional_kwargs.get(
        "reasoning_content"
    )


_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_tags(text: str) -> str:
    """Remove inline <think> reasoning tags that NVIDIA preserves in content."""
    return _THINK_TAG_RE.sub("", text).strip()


async def call_llm(
    prompt: str,
    system_prompt: str = "",
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    provider: str = "requesty",
) -> str:
    """Call an LLM via the given provider (requesty | nvidia) with the given model."""
    llm = get_llm(model, temperature=temperature, max_tokens=max_tokens, provider=provider)

    messages: list[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    logger.info(
        "llm_call",
        model=model or settings.llm_model,
        provider=provider,
        prompt_length=len(prompt),
    )

    response = await asyncio.wait_for(
        llm.ainvoke(messages), timeout=settings.llm_timeout
    )

    reasoning = _extract_reasoning(response)
    if reasoning:
        logger.info("llm_reasoning", reasoning_length=len(str(reasoning)))

    text = response.content if isinstance(response.content, str) else str(response.content)
    if provider == "nvidia":
        text = _strip_think_tags(text)
    logger.info("llm_response", response_length=len(text))
    return text


async def call_llm_structured(
    prompt: str,
    schema: type[BaseModel],
    system_prompt: str = "",
    model: str | None = None,
    provider: str = "requesty",
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> tuple[BaseModel | None, str]:
    """Call an LLM with structured output. Never raises.

    Returns ``(parsed_model, error)`` where ``error`` is ``""`` on success.
    Attempts the provider ``json_schema`` then ``function_calling`` methods.
    Providers that reject ``json_schema`` at bind time fall back to
    ``function_calling``.
    """
    messages: list[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    for method in ("json_schema", "function_calling"):
        try:
            llm = get_llm(
                model, temperature=temperature, max_tokens=max_tokens, provider=provider
            )
            structured_llm = llm.with_structured_output(schema, method=method)
            response = await asyncio.wait_for(
                structured_llm.ainvoke(messages), timeout=settings.llm_timeout
            )
        except Exception as e:
            logger.warning(
                "structured_output_attempt_failed",
                provider=provider,
                method=method,
                error=str(e),
            )
            continue
        if isinstance(response, schema):
            return response, ""
    return None, "structured_output_failed"


async def stream_llm(
    prompt: str,
    system_prompt: str = "",
    model: str | None = None,
    provider: str = "requesty",
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> AsyncIterator[tuple[str | None, str]]:
    """Stream (reasoning, content) chunks from the given provider's model."""
    llm = get_llm(model, temperature=temperature, max_tokens=max_tokens, provider=provider)

    messages: list[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    async for chunk in llm.astream(messages):
        reasoning = _extract_reasoning(chunk)
        content = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
        if provider == "nvidia":
            content = _strip_think_tags(content)
        yield reasoning, content


class StageLLMKwargs(TypedDict):
    model: str
    provider: str


def stage_llm_kwargs(stage: str) -> StageLLMKwargs:
    """Resolve the model + provider for a graph stage.

    When a stage's ``*_nvidia_model`` is empty, it falls back to the named
    NVIDIA model field (e.g. ``nvidia_deepseek_v4_flash``) so that the
    ``*.env`` model names stay the single source of truth.
    """
    if stage == "research":
        provider = settings.research_provider
        requesty_model = settings.research_model
        nvidia_model = settings.research_nvidia_model or settings.nvidia_deepseek_v4_flash
    elif stage == "review":
        provider = settings.review_provider
        requesty_model = settings.review_model
        nvidia_model = settings.review_nvidia_model or settings.nvidia_deepseek_v4_pro
    elif stage == "rubric_grader":
        provider = settings.rubric_grader_provider
        requesty_model = settings.rubric_grader_model
        nvidia_model = (
            settings.rubric_grader_nvidia_model or settings.nvidia_deepseek_v4_flash
        )
    elif stage == "analysis":
        provider = settings.analysis_provider
        requesty_model = settings.analysis_model
        nvidia_model = settings.analysis_nvidia_model or settings.nvidia_deepseek_v4_pro
    else:
        raise ValueError(f"unknown stage: {stage}")
    if provider == "nvidia":
        return {"model": nvidia_model, "provider": "nvidia"}
    return {"model": requesty_model, "provider": "requesty"}


async def call_bedrock(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Backward-compatible wrapper — calls default model via Requesty."""
    return await call_llm(
        prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )

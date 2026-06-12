"""LLM client — one OpenAI-compatible interface, three interchangeable backends:
local Ollama (dev, free), Qwen Cloud free quota, Qwen Cloud paid. Selected
entirely by env (LLM_ENABLED + QWEN_BASE_URL / QWEN_API_KEY / QWEN_MODEL), so
the move from local dev to Qwen Cloud is a one-variable swap.

Mirrors the connector contract: env-configured, injectable httpx transport for
tests, fail-soft. Business logic depends on the LLMClient ABC and MUST degrade
gracefully — get_llm_client() returns None when disabled, and a live call may
raise LLMUnavailable. Safety gates and scoring never depend on the LLM.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ayin.config import Settings, get_settings
from ayin.llm.schemas import ChatMessage, LLMResponse, LLMUsage

log = logging.getLogger("ayin.llm")

DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TIMEOUT_SECONDS = 30.0

BaseModelT = TypeVar("BaseModelT", bound=BaseModel)


class LLMError(Exception):
    """Base for LLM failures."""


class LLMUnavailable(LLMError):
    """Endpoint unreachable/throttled/5xx — caller should fall back to templates."""


class LLMResponseInvalid(LLMError):
    """Response could not be parsed into the expected structured schema."""


def _extract_json(content: str) -> str:
    """Best-effort isolate a JSON object from model output (tolerate ```json
    fences and surrounding prose)."""
    s = content.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    if not s.startswith("{"):
        i, j = s.find("{"), s.rfind("}")
        if i != -1 and j > i:
            s = s[i : j + 1]
    return s


def parse_into(content: str, schema: type[BaseModelT]) -> BaseModelT:
    """Parse an LLM text response into ``schema``. Raises LLMResponseInvalid."""
    try:
        data = json.loads(_extract_json(content))
    except (json.JSONDecodeError, ValueError) as exc:
        raise LLMResponseInvalid(f"LLM response was not valid JSON: {exc}") from exc
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise LLMResponseInvalid(f"LLM response did not match {schema.__name__}: {exc}") from exc


class LLMClient(ABC):
    """Uniform LLM interface. Subclasses set ``model`` and implement complete()."""

    model: str

    @abstractmethod
    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Send a chat completion. Raise LLMUnavailable on transient failure."""

    def complete_json(
        self,
        messages: Sequence[ChatMessage],
        schema: type[BaseModelT],
        *,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> BaseModelT:
        """Complete and parse the response into ``schema`` (structured output)."""
        resp = self.complete(messages, temperature=temperature, max_tokens=max_tokens)
        return parse_into(resp.content, schema)


class QwenClient(LLMClient):
    """OpenAI-compatible chat-completions client (Qwen Cloud / Ollama / any
    compatible endpoint)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self._timeout = timeout_seconds
        self._transport = transport

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        url = f"{self._base}/chat/completions"
        body: dict = {
            "model": self.model,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
        headers = {"content-type": "application/json"}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"
        try:
            with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
                res = client.post(url, json=body, headers=headers)
        except httpx.TransportError as exc:
            raise LLMUnavailable(f"LLM endpoint unreachable: {exc}") from exc
        if res.status_code == 429 or res.status_code >= 500:
            raise LLMUnavailable(f"LLM endpoint unavailable ({res.status_code})")
        if res.status_code != 200:
            raise LLMError(f"LLM endpoint error {res.status_code}: {res.text[:200]}")
        data = res.json()
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseInvalid(f"unexpected completion shape: {exc}") from exc
        usage_raw = data.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
            completion_tokens=int(usage_raw.get("completion_tokens", 0)),
            total_tokens=int(usage_raw.get("total_tokens", 0)),
        )
        return LLMResponse(
            content=message.get("content") or "",
            model=str(data.get("model", self.model)),
            usage=usage,
            tool_calls=list(message.get("tool_calls") or []),
            raw={"id": data.get("id")},
        )


class MockLLMClient(LLMClient):
    """Deterministic, network-free client for tests and offline dev. Serves
    queued ``responses`` in order, then ``default``. Records calls for asserts."""

    def __init__(
        self,
        *,
        model: str = "mock-qwen",
        responses: Sequence[str] | None = None,
        default: str = "{}",
    ) -> None:
        self.model = model
        self._responses = list(responses or [])
        self._default = default
        self.calls: list[list[ChatMessage]] = []

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        self.calls.append(list(messages))
        content = self._responses.pop(0) if self._responses else self._default
        return LLMResponse(
            content=content,
            model=self.model,
            usage=LLMUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )


def get_llm_client(settings: Settings | None = None) -> LLMClient | None:
    """Return a configured client, or None when the LLM is disabled (callers
    then use deterministic templates). Never raises on missing config."""
    s = settings or get_settings()
    if not s.llm_enabled:
        return None
    return QwenClient(
        base_url=s.qwen_base_url,
        api_key=s.qwen_api_key,
        model=s.qwen_model,
        timeout_seconds=s.qwen_timeout_seconds,
    )

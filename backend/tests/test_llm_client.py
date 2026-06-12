"""LLM client tests: env-gated factory, OpenAI-compatible request shape via an
injected httpx mock transport, structured-output parsing, and graceful
degradation (transient vs hard errors). Clearly-fake keys only."""

import json

import httpx
import pytest

from ayin.config import Settings
from ayin.llm.client import (
    LLMError,
    LLMResponseInvalid,
    LLMUnavailable,
    MockLLMClient,
    QwenClient,
    get_llm_client,
    parse_into,
)
from ayin.llm.schemas import ChatMessage, NarrativeDraft, Role

ONE_MSG = [ChatMessage(role=Role.USER, content="x")]


def _client(handler):
    return QwenClient(
        base_url="http://llm.test/v1", api_key="fake-key", model="qwen3:4b",
        transport=httpx.MockTransport(handler),
    )


def _completion(content):
    return {
        "id": "cmpl-1", "model": "qwen3:4b",
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
    }


def test_factory_disabled_returns_none():
    assert get_llm_client(Settings(llm_enabled=False)) is None


def test_factory_enabled_builds_qwen_client():
    c = get_llm_client(Settings(llm_enabled=True, qwen_model="qwen-max"))
    assert isinstance(c, QwenClient)
    assert c.model == "qwen-max"


def test_openai_compatible_request_shape():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion('{"verdict":"ok","claims":[]}'))

    msgs = [ChatMessage(role=Role.SYSTEM, content="sys"), ChatMessage(role=Role.USER, content="hi")]
    resp = _client(handler).complete(msgs)
    assert seen["url"].endswith("/chat/completions")
    assert seen["auth"] == "Bearer fake-key"
    assert seen["body"]["model"] == "qwen3:4b"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert resp.usage.total_tokens == 12


def test_complete_json_parses_structured_output():
    def handler(request):
        return httpx.Response(200, json=_completion('{"verdict":"v","claims":[]}'))

    draft = _client(handler).complete_json(ONE_MSG, NarrativeDraft)
    assert isinstance(draft, NarrativeDraft) and draft.verdict == "v"


def test_fenced_json_is_tolerated():
    fenced = '```json\n{"verdict":"v","claims":[]}\n```'

    def handler(request):
        return httpx.Response(200, json=_completion(fenced))

    assert _client(handler).complete_json(ONE_MSG, NarrativeDraft).verdict == "v"


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_statuses_are_unavailable(status):
    def handler(request):
        return httpx.Response(status)

    with pytest.raises(LLMUnavailable):
        _client(handler).complete(ONE_MSG)


def test_4xx_is_hard_error():
    def handler(request):
        return httpx.Response(400, text="bad request")

    with pytest.raises(LLMError):
        _client(handler).complete(ONE_MSG)


def test_transport_error_is_unavailable():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(LLMUnavailable):
        _client(handler).complete(ONE_MSG)


def test_malformed_completion_shape_is_invalid():
    def handler(request):
        return httpx.Response(200, json={"no_choices": True})

    with pytest.raises(LLMResponseInvalid):
        _client(handler).complete(ONE_MSG)


def test_parse_into_rejects_non_json():
    with pytest.raises(LLMResponseInvalid):
        parse_into("definitely not json", NarrativeDraft)


def test_mock_client_serves_queued_then_default():
    m = MockLLMClient(responses=['{"a": 1}'], default='{"b": 2}')
    assert m.complete(ONE_MSG).content == '{"a": 1}'
    assert m.complete(ONE_MSG).content == '{"b": 2}'
    assert len(m.calls) == 2

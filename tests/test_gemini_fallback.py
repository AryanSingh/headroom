from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
from fastapi.responses import StreamingResponse

from cutctx.backends.base import BackendResponse
from cutctx.proxy.server import CutctxProxy


class _GeminiRequest:
    headers = {"x-goog-api-key": "test-key"}
    query_params = {}
    url = SimpleNamespace(path="/v1beta/models/gemini-2.0-flash:generateContent")

    async def body(self) -> bytes:
        return json.dumps(
            {
                "contents": [{"role": "user", "parts": [{"text": "hello"}]}],
            }
        ).encode("utf-8")


class _GeminiStreamRequest(_GeminiRequest):
    query_params = {"alt": "sse"}
    url = SimpleNamespace(path="/v1beta/models/gemini-2.0-flash:streamGenerateContent")


class _GeminiFallbackBackend:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.name = f"litellm-{provider}"

    async def send_openai_message(self, body: dict, headers: dict[str, str]) -> BackendResponse:
        return BackendResponse(
            body={
                "id": "chatcmpl-gem-fallback-1",
                "object": "chat.completion",
                "model": body.get("model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "fallback gemini ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                    "prompt_tokens_details": {"cached_tokens": 2},
                },
            },
            status_code=200,
            headers={"content-type": "application/json"},
        )

    async def stream_openai_message(self, body: dict, headers: dict[str, str]):
        yield (
            'data: {"choices":[{"delta":{"content":"fallback gemini stream ok"}}],'
            '"usage":{"completion_tokens":4}}\n\n'
        )
        yield (
            'data: {"usage":{"prompt_tokens":10,"completion_tokens":4,'
            '"total_tokens":14,"prompt_tokens_details":{"cached_tokens":2}}}\n\n'
        )
        yield "data: [DONE]\n\n"


class _HttpClientConnectError:
    def build_request(self, method, url, headers=None, content=None):  # noqa: ANN001, ANN201
        return httpx.Request(method, url, headers=headers, content=content)

    async def send(self, request, stream=False):  # noqa: ANN001, ANN201
        raise httpx.ConnectError("primary gemini offline", request=request)


def test_gemini_generate_content_falls_back_to_configured_backend() -> None:
    handler = object.__new__(CutctxProxy)
    handler.memory_handler = None
    handler.rate_limiter = None
    async def record_failed(**kwargs):  # noqa: ANN202
        return None

    handler.metrics = SimpleNamespace(
        record_failed=record_failed,
        record_compression_declined=lambda reason: None,
    )
    handler.config = SimpleNamespace(
        optimize=False,
        image_optimize=False,
        anthropic_pre_upstream_memory_context_timeout_seconds=1.0,
        fallback_enabled=True,
        fallback_provider="openai",
    )
    handler.usage_reporter = None
    handler.openai_provider = SimpleNamespace(get_context_limit=lambda model: 128_000)
    handler.openai_pipeline = SimpleNamespace(apply=lambda **kwargs: None)
    handler.cost_tracker = None
    handler.fallback_backend = _GeminiFallbackBackend("openai")
    handler.openai_fallback_backend = None
    outcomes = []

    async def next_request_id():  # noqa: ANN202
        return "req_gem_fallback"

    async def record(outcome):  # noqa: ANN001, ANN202
        outcomes.append(outcome)

    async def retry_request(method, url, headers, body, **_kwargs):  # noqa: ANN001, ANN202
        request = httpx.Request(method, url, headers=headers)
        raise httpx.ConnectError("primary gemini offline", request=request)

    handler._next_request_id = next_request_id
    handler._record_request_outcome = record
    handler._retry_request = retry_request

    response = asyncio.run(
        handler.handle_gemini_generate_content(
            _GeminiRequest(),
            "gemini-2.0-flash",
        )
    )

    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["candidates"][0]["content"]["parts"][0]["text"] == "fallback gemini ok"
    assert payload["usageMetadata"]["promptTokenCount"] == 10
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.provider == "openai"
    assert outcome.tags["fallback_provider"] == "openai"
    assert outcome.tags["fallback_attempted"] == "true"
    assert outcome.tags["fallback_reason"] == "connect_error"


def test_gemini_stream_generate_content_falls_back_to_configured_backend() -> None:
    handler = object.__new__(CutctxProxy)
    handler.memory_handler = None
    handler.rate_limiter = None
    async def record_failed(**kwargs):  # noqa: ANN202
        return None

    handler.metrics = SimpleNamespace(
        record_failed=record_failed,
        record_compression_declined=lambda reason: None,
    )
    handler.config = SimpleNamespace(
        optimize=False,
        image_optimize=False,
        anthropic_pre_upstream_memory_context_timeout_seconds=1.0,
        fallback_enabled=True,
        fallback_provider="openai",
        log_full_messages=False,
        ccr_inject_tool=False,
        retry_max_attempts=1,
        retry_base_delay_ms=1,
        retry_max_delay_ms=1,
    )
    handler.usage_reporter = None
    handler.openai_provider = SimpleNamespace(get_context_limit=lambda model: 128_000)
    handler.openai_pipeline = SimpleNamespace(apply=lambda **kwargs: None)
    handler.cost_tracker = None
    handler.fallback_backend = _GeminiFallbackBackend("openai")
    handler.openai_fallback_backend = None
    handler.http_client = _HttpClientConnectError()
    outcomes = []

    async def next_request_id():  # noqa: ANN202
        return "req_gem_stream_fallback"

    async def record(outcome):  # noqa: ANN001, ANN202
        outcomes.append(outcome)

    handler._next_request_id = next_request_id
    handler._record_request_outcome = record

    response = asyncio.run(
        handler.handle_gemini_generate_content(
            _GeminiStreamRequest(),
            "gemini-2.0-flash",
        )
    )

    assert isinstance(response, StreamingResponse)

    async def collect():  # noqa: ANN202
        return [chunk async for chunk in response.body_iterator]

    chunks = asyncio.run(collect())
    assert any(b"fallback gemini stream ok" in chunk for chunk in chunks)
    assert any(b'"usageMetadata"' in chunk for chunk in chunks)
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.provider == "openai"
    assert outcome.tags["fallback_provider"] == "openai"
    assert outcome.tags["fallback_attempted"] == "true"
    assert outcome.tags["fallback_reason"] == "connect_error"

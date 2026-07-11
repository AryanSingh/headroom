from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import anyio
import httpx
from fastapi import Request

from cutctx.backends.base import BackendResponse
from cutctx.proxy.handlers.openai import OpenAIHandlerMixin
from cutctx.proxy.handlers.streaming import StreamingMixin
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.outcome import RequestOutcome


class _DummyTokenizer:
    def count_messages(self, messages) -> int:
        return max(1, len(messages or []))


class _DummyMetrics:
    async def record_request(self, **kwargs):
        return None

    async def record_stage_timings(self, path: str, timings: dict[str, float]) -> None:
        return None

    async def record_failed(self, **kwargs):
        return None

    async def record_rate_limited(self, **kwargs):
        return None

    def record_compression_declined(self, reason: str) -> None:
        return None


class _FallbackOpenAIBackend:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.name = f"litellm-{provider}"

    async def send_openai_message(self, body: dict, headers: dict[str, str]) -> BackendResponse:
        return BackendResponse(
            body={
                "id": "chatcmpl-fallback-1",
                "object": "chat.completion",
                "model": body.get("model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "fallback openai ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 4,
                    "total_tokens": 15,
                    "prompt_tokens_details": {"cached_tokens": 3},
                },
            },
            status_code=200,
            headers={"content-type": "application/json"},
        )

    async def stream_openai_message(self, body: dict, headers: dict[str, str]):
        yield (
            'data: {"choices":[{"delta":{"content":"fallback stream ok"}}],'
            '"usage":{"completion_tokens":4}}\n\n'
        )
        yield (
            'data: {"usage":{"prompt_tokens":11,"completion_tokens":4,'
            '"total_tokens":15,"prompt_tokens_details":{"cached_tokens":3}}}\n\n'
        )
        yield "data: [DONE]\n\n"


class _PrefixTracker:
    def get_frozen_message_count(self) -> int:
        return 0

    def update_from_response(self, **kwargs) -> None:
        return None


class _FallbackOpenAIHandler(OpenAIHandlerMixin):
    OPENAI_API_URL = "https://api.openai.com"

    def __init__(self, *, fallback_provider: str) -> None:
        self.rate_limiter = None
        self.metrics = _DummyMetrics()
        self.config = ProxyConfig(
            optimize=False,
            image_optimize=False,
            retry_max_attempts=1,
            retry_base_delay_ms=1,
            retry_max_delay_ms=1,
            connect_timeout_seconds=10,
            mode="token",
            cache_enabled=False,
            rate_limit_enabled=False,
            fallback_enabled=True,
            fallback_provider=fallback_provider,
            prefix_freeze_enabled=False,
            memory_enabled=False,
            log_full_messages=False,
        )
        self.usage_reporter = None
        self.openai_provider = SimpleNamespace(get_context_limit=lambda model: 128_000)
        self.openai_pipeline = SimpleNamespace(apply=MagicMock())
        self.anthropic_backend = None
        self.fallback_backend = _FallbackOpenAIBackend(fallback_provider)
        self.openai_fallback_backend = None
        self.cost_tracker = None
        self.memory_handler = None
        self.cache = None
        self.security = None
        self.ccr_context_tracker = None
        self.ccr_injector = None
        self.ccr_response_handler = None
        self.ccr_feedback = None
        self.ccr_batch_processor = None
        self.ccr_mcp_server = None
        self.traffic_learner = None
        self.tool_injector = None
        self.read_lifecycle_manager = None
        self.logger = SimpleNamespace(log=lambda *a, **k: None)
        self.request_logger = self.logger
        self.usage_observer = None
        self.image_compressor = None
        self.pipeline_extensions = SimpleNamespace(
            emit=lambda *a, **k: SimpleNamespace(
                messages=None,
                tools=None,
                headers=None,
                body=None,
                metadata=None,
                response=None,
            )
        )
        self.session_tracker_store = SimpleNamespace(
            compute_session_id=lambda *a, **k: "sess-openai-fallback-1",
            get_or_create=lambda *a, **k: _PrefixTracker(),
        )
        self.recorded_outcomes: list[RequestOutcome] = []

    async def _next_request_id(self) -> str:
        return "req-openai-fallback"

    async def _retry_request(self, method: str, url: str, headers: dict, body: dict, **_kwargs):
        request = httpx.Request(method, url)
        raise httpx.ConnectError("primary openai offline", request=request)

    async def _record_request_outcome(self, outcome: RequestOutcome) -> None:
        self.recorded_outcomes.append(outcome)

    async def _run_compression_in_executor(self, fn, *, timeout: float):
        return fn()

    def _get_compression_cache(self, session_id):
        return SimpleNamespace(
            apply_cached=lambda m: m,
            compute_frozen_count=lambda m: 0,
            mark_stable_from_messages=lambda *a, **k: None,
            should_defer_compression=lambda h: False,
            mark_stable=lambda h: None,
            content_hash=lambda c: "h",
            update_from_result=lambda *a, **k: None,
            _cache={},
            _stable_hashes=set(),
        )


class _HttpClientConnectError:
    def build_request(self, method: str, url: str, content: bytes, headers: dict[str, str]):
        return httpx.Request(method, url, content=content, headers=headers)

    async def send(self, request, stream: bool = False):
        raise httpx.ConnectError("primary openai offline", request=request)


class _StreamingFallbackOpenAIHandler(StreamingMixin, _FallbackOpenAIHandler):
    def __init__(self, *, fallback_provider: str) -> None:
        super().__init__(fallback_provider=fallback_provider)
        self.http_client = _HttpClientConnectError()


async def _collect_streaming_response_body(response) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    return b"".join(chunks)


def _build_request(body: dict, headers: dict[str, str]) -> Request:
    payload = json.dumps(body).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/v1/chat/completions",
        "raw_path": b"/v1/chat/completions",
        "query_string": b"",
        "headers": [
            (key.lower().encode("utf-8"), value.encode("utf-8"))
            for key, value in headers.items()
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    }
    return Request(scope, receive)


def test_openai_chat_request_falls_back_to_configured_gemini_backend() -> None:
    request = _build_request(
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
        {"authorization": "Bearer sk-test"},
    )
    handler = _FallbackOpenAIHandler(fallback_provider="gemini")

    import cutctx.tokenizers as _tk

    orig_get = _tk.get_tokenizer
    _tk.get_tokenizer = lambda _model: _DummyTokenizer()
    try:
        response = anyio.run(handler.handle_openai_chat, request)
    finally:
        _tk.get_tokenizer = orig_get

    assert response.status_code == 200
    assert b"fallback openai ok" in response.body
    assert len(handler.recorded_outcomes) == 1
    outcome = handler.recorded_outcomes[0]
    assert outcome.provider == "gemini"
    assert outcome.tags["fallback_provider"] == "gemini"
    assert outcome.tags["fallback_attempted"] == "true"
    assert outcome.tags["fallback_reason"] == "connect_error"


def test_openai_chat_streaming_request_falls_back_to_configured_gemini_backend() -> None:
    request = _build_request(
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
        {"authorization": "Bearer sk-test"},
    )
    handler = _StreamingFallbackOpenAIHandler(fallback_provider="gemini")

    import cutctx.tokenizers as _tk

    orig_get = _tk.get_tokenizer
    _tk.get_tokenizer = lambda _model: _DummyTokenizer()
    try:
        response = anyio.run(handler.handle_openai_chat, request)
        body = anyio.run(_collect_streaming_response_body, response)
    finally:
        _tk.get_tokenizer = orig_get

    assert response.status_code == 200
    assert b"fallback stream ok" in body
    assert len(handler.recorded_outcomes) == 1
    outcome = handler.recorded_outcomes[0]
    assert outcome.provider == "gemini"
    assert outcome.tags["fallback_provider"] == "gemini"
    assert outcome.tags["fallback_attempted"] == "true"
    assert outcome.tags["fallback_reason"] == "connect_error"

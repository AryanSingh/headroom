from __future__ import annotations

import json
from types import SimpleNamespace

import anyio
import httpx
from fastapi import Request

from cutctx.backends.base import BackendResponse
from cutctx.proxy.handlers.openai import OpenAIHandlerMixin
from cutctx.proxy.outcome import RequestOutcome


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


class _FallbackResponsesBackend:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.name = f"litellm-{provider}"

    async def send_openai_message(self, body: dict, headers: dict[str, str]) -> BackendResponse:
        return BackendResponse(
            body={
                "id": "chatcmpl-fallback-resp-1",
                "object": "chat.completion",
                "model": body.get("model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "fallback responses ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 9,
                    "completion_tokens": 4,
                    "total_tokens": 13,
                    "prompt_tokens_details": {"cached_tokens": 2},
                },
            },
            status_code=200,
            headers={"content-type": "application/json"},
        )


class _FallbackResponsesHandler(OpenAIHandlerMixin):
    OPENAI_API_URL = "https://api.openai.com"

    def __init__(self, *, fallback_provider: str) -> None:
        self.rate_limiter = None
        self.metrics = _DummyMetrics()
        self.config = SimpleNamespace(
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
            ccr_inject_tool=False,
        )
        self.usage_reporter = None
        self.openai_provider = SimpleNamespace(get_context_limit=lambda model: 128_000)
        self.openai_pipeline = SimpleNamespace(apply=lambda **kwargs: None)
        self.anthropic_backend = None
        self.fallback_backend = _FallbackResponsesBackend(fallback_provider)
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
        self.session_tracker_store = SimpleNamespace(
            compute_session_id=lambda *a, **k: "sess-openai-resp-fallback-1",
            get_or_create=lambda *a, **k: SimpleNamespace(get_frozen_message_count=lambda: 0),
        )
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
        self.recorded_outcomes: list[RequestOutcome] = []

    async def _next_request_id(self) -> str:
        return "req-openai-responses-fallback"

    async def _retry_request(self, method: str, url: str, headers: dict, body: dict, **_kwargs):
        request = httpx.Request(method, url)
        raise httpx.ConnectError("primary openai responses offline", request=request)

    async def _record_request_outcome(self, outcome: RequestOutcome) -> None:
        self.recorded_outcomes.append(outcome)

    async def _compress_openai_responses_payload_in_executor(self, body, *, model: str, request_id: str):
        body_bytes = len(json.dumps(body).encode("utf-8"))
        return body, False, 0, [], "no_compression", body_bytes, body_bytes, 0, {}


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
        "path": "/v1/responses",
        "raw_path": b"/v1/responses",
        "query_string": b"",
        "headers": [
            (key.lower().encode("utf-8"), value.encode("utf-8"))
            for key, value in headers.items()
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    }
    return Request(scope, receive)


def test_openai_responses_request_falls_back_to_configured_gemini_backend() -> None:
    request = _build_request(
        {
            "model": "gpt-5.4-mini",
            "input": "hello",
            "stream": False,
        },
        {"authorization": "Bearer sk-test"},
    )
    handler = _FallbackResponsesHandler(fallback_provider="gemini")

    response = anyio.run(handler.handle_openai_responses, request)

    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["object"] == "response"
    assert payload["output"][0]["content"][0]["text"] == "fallback responses ok"
    assert len(handler.recorded_outcomes) == 1
    outcome = handler.recorded_outcomes[0]
    assert outcome.provider == "gemini"
    assert outcome.tags["fallback_provider"] == "gemini"
    assert outcome.tags["fallback_attempted"] == "true"
    assert outcome.tags["fallback_reason"] == "connect_error"

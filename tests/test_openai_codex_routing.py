import base64
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anyio
import pytest
from fastapi import HTTPException, Request

from cutctx.proxy.handlers.openai import (
    OpenAIHandlerMixin,
    _resolve_codex_routing_headers,
)
from cutctx.proxy.handlers.openai.utils import (
    _has_codex_responses_lite_hint,
    _strip_openai_internal_headers,
)
from cutctx.proxy.model_router import ModelRouter, ModelRouterConfig


def _jwt(payload: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}

    def encode(part: dict) -> str:
        raw = json.dumps(part, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{encode(header)}.{encode(payload)}."


def test_resolve_codex_routing_prefers_explicit_header():
    headers, is_chatgpt = _resolve_codex_routing_headers(
        {
            "Authorization": "Bearer sk-test",
            "ChatGPT-Account-ID": "acct-explicit",
        }
    )

    assert is_chatgpt is True
    assert headers["ChatGPT-Account-ID"] == "acct-explicit"


def test_resolve_codex_routing_derives_account_id_from_oauth_jwt():
    token = _jwt(
        {
            "https://api.openai.com/auth": {
                "chatgpt_account_id": "acct-from-jwt",
            }
        }
    )

    headers, is_chatgpt = _resolve_codex_routing_headers(
        {
            "authorization": f"Bearer {token}",
        }
    )

    assert is_chatgpt is True
    assert headers["ChatGPT-Account-ID"] == "acct-from-jwt"


def test_resolve_codex_routing_leaves_regular_openai_bearer_tokens_unchanged():
    token = _jwt({"aud": ["https://api.openai.com/v1"]})

    headers, is_chatgpt = _resolve_codex_routing_headers(
        {
            "authorization": f"Bearer {token}",
        }
    )

    assert is_chatgpt is False
    assert "ChatGPT-Account-ID" not in headers


def test_resolve_codex_routing_returns_none_without_bearer_auth():
    headers, is_chatgpt = _resolve_codex_routing_headers({})

    assert is_chatgpt is False
    assert headers == {}


def test_resolve_codex_routing_ignores_non_jwt_bearer_tokens():
    headers, is_chatgpt = _resolve_codex_routing_headers(
        {
            "authorization": "Bearer not-a-jwt",
        }
    )

    assert is_chatgpt is False
    assert headers["authorization"] == "Bearer not-a-jwt"


def test_resolve_codex_routing_ignores_invalid_jwt_payloads():
    invalid_payload = base64.urlsafe_b64encode(b"not-json").decode("ascii").rstrip("=")
    token = f"test-header.{invalid_payload}.signature"

    headers, is_chatgpt = _resolve_codex_routing_headers(
        {
            "authorization": f"Bearer {token}",
        }
    )

    assert is_chatgpt is False
    assert headers["authorization"] == f"Bearer {token}"


def test_strip_openai_internal_headers_removes_codex_lite_hints():
    headers = {
        "Authorization": "Bearer sk-test",
        "X-OpenAI-Internal-Codex-Responses-Lite": "1",
        "x-openai-internal-another-flag": "enabled",
        "x-cutctx-bypass": "true",
    }

    stripped = _strip_openai_internal_headers(headers)

    assert "X-OpenAI-Internal-Codex-Responses-Lite" not in stripped
    assert "x-openai-internal-another-flag" not in stripped
    assert stripped["Authorization"] == "Bearer sk-test"
    assert stripped["x-cutctx-bypass"] == "true"


def test_has_codex_responses_lite_hint_detects_enabled_header():
    assert _has_codex_responses_lite_hint(
        {"X-OpenAI-Internal-Codex-Responses-Lite": "1"}
    )
    assert _has_codex_responses_lite_hint(
        {"x-openai-internal-codex-responses-lite": "true"}
    )
    assert not _has_codex_responses_lite_hint(
        {"X-OpenAI-Internal-Codex-Responses-Lite": "0"}
    )


class _DummyMetrics:
    async def record_request(self, **kwargs):  # noqa: ANN003
        return None

    async def record_failed(self, **kwargs):  # noqa: ANN003
        return None


class _DummyTokenizer:
    def count_messages(self, messages):
        return len(messages)

    def count_text(self, text):
        return len(text)


class _ResponseStub:
    status_code = 200
    headers = {"content-type": "application/json", "content-length": "42"}
    content = b'{"id":"resp_123","output":[{"type":"message"}]}'

    def json(self):
        return {"usage": {"input_tokens": 2, "output_tokens": 1}}


class _DummyOpenAIHandler(OpenAIHandlerMixin):
    OPENAI_API_URL = "https://api.openai.com"

    def __init__(self) -> None:
        self.rate_limiter = None
        self.cache = None
        self.metrics = _DummyMetrics()
        self.config = SimpleNamespace(
            optimize=False,
            audio_optimize=False,
            hooks=None,
            mode="off",
            retry_max_attempts=3,
            retry_base_delay_ms=10,
            retry_max_delay_ms=50,
            connect_timeout_seconds=10,
        )
        self.usage_reporter = None
        self.openai_provider = SimpleNamespace(get_context_limit=lambda model: 128_000)
        self.openai_pipeline = SimpleNamespace(apply=MagicMock())
        self.anthropic_backend = None
        self.cost_tracker = None
        self.memory_handler = None
        self._model_router = None
        # PR-A6 wires session-sticky `OpenAI-Beta` merging into the
        # responses HTTP handler — it reads `compute_session_id` to key
        # the SessionBetaTracker. The routing tests don't exercise the
        # tracker semantics themselves, so a fixed-id stub is enough.
        self.session_tracker_store = SimpleNamespace(
            compute_session_id=lambda *a, **k: "sess-openai-1",
            get_or_create=lambda *a, **k: SimpleNamespace(
                get_frozen_message_count=lambda: 0,
                update_from_response=lambda *args, **kwargs: None,
            ),
        )
        self.captured_request: tuple[str, str, dict, dict] | None = None
        self.captured_stream_request: tuple[str, dict, dict] | None = None

    async def _next_request_id(self) -> str:
        return "req-1"

    def _extract_tags(self, headers: dict[str, str]) -> dict[str, str]:
        return {}

    async def _retry_request(self, method: str, url: str, headers: dict, body: dict):
        self.captured_request = (method, url, headers, body)
        return _ResponseStub()

    async def _run_compression_in_executor(self, fn, *, timeout: float):
        # Test stub for CutctxProxy._run_compression_in_executor.
        # The real implementation runs `fn` on a bounded thread pool with
        # a wall-clock timeout; tests just need the callable invoked
        # synchronously so MagicMock call_count assertions fire.
        return fn()

    async def _record_request_outcome(self, outcome) -> None:
        # Test stub: delegates to the production funnel so wire shape
        # matches CutctxProxy._record_request_outcome.
        from cutctx.proxy.outcome import emit_request_outcome

        await emit_request_outcome(self, outcome)

    async def _stream_response(
        self,
        url: str,
        headers: dict,
        body: dict,
        provider: str,
        model: str,
        request_id: str,
        original_tokens: int,
        optimized_tokens: int,
        tokens_saved: int,
        transforms_applied: list[str],
        tags: dict[str, str],
        optimization_latency: float,
        memory_user_id: str | None = None,
        **kwargs,
    ):
        self.captured_stream_request = (url, headers, body)
        return SimpleNamespace(
            status_code=200,
            url=url,
            headers=headers,
            body=body,
            memory_user_id=memory_user_id,
        )


def _build_request(
    body: dict,
    headers: dict[str, str],
    *,
    path: str = "/v1/responses",
) -> Request:
    payload = json.dumps(body).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [
            (key.lower().encode("utf-8"), value.encode("utf-8")) for key, value in headers.items()
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    }
    return Request(scope, receive)


def test_handle_openai_responses_routes_chatgpt_auth_to_backend_api(monkeypatch):
    token = _jwt(
        {
            "https://api.openai.com/auth": {
                "chatgpt_account_id": "acct-from-jwt",
            }
        }
    )
    request = _build_request(
        {"model": "gpt-5.4", "input": "hello"},
        {"Authorization": f"Bearer {token}"},
    )
    handler = _DummyOpenAIHandler()

    monkeypatch.setattr("cutctx.tokenizers.get_tokenizer", lambda model: _DummyTokenizer())

    response = anyio.run(handler.handle_openai_responses, request)

    assert handler.captured_request is not None
    method, url, headers, body = handler.captured_request
    assert method == "POST"
    assert url == "https://chatgpt.com/backend-api/codex/responses"
    assert headers["ChatGPT-Account-ID"] == "acct-from-jwt"
    assert body["input"] == "hello"
    assert response.status_code == 200


def test_handle_openai_responses_routes_api_key_auth_direct_to_openai(monkeypatch):
    request = _build_request(
        {"model": "gpt-4o-mini", "input": "hello"},
        {
            "Authorization": "Bearer sk-test",
            "X-OpenAI-Internal-Codex-Responses-Lite": "1",
        },
    )
    handler = _DummyOpenAIHandler()

    monkeypatch.setattr("cutctx.tokenizers.get_tokenizer", lambda model: _DummyTokenizer())

    response = anyio.run(handler.handle_openai_responses, request)

    assert handler.captured_request is not None
    method, url, headers, body = handler.captured_request
    assert method == "POST"
    assert url == "https://api.openai.com/v1/responses"
    assert headers.get("ChatGPT-Account-ID") is None
    assert "X-OpenAI-Internal-Codex-Responses-Lite" not in headers
    assert body["input"] == "hello"
    assert response.status_code == 200


def test_handle_openai_responses_lite_uses_verified_preset_target(monkeypatch):
    request = _build_request(
        {"model": "gpt-5.6-terra", "input": "what is the restart command?"},
        {
            "Authorization": "Bearer sk-test",
            "X-OpenAI-Internal-Codex-Responses-Lite": "1",
            "User-Agent": "Codex Desktop/1.0",
        },
    )
    handler = _DummyOpenAIHandler()
    handler._model_router = ModelRouter(ModelRouterConfig.codex_gpt54mini_high_preset())

    monkeypatch.setattr("cutctx.tokenizers.get_tokenizer", lambda model: _DummyTokenizer())

    response = anyio.run(handler.handle_openai_responses, request)

    assert handler.captured_request is not None
    _, _, headers, body = handler.captured_request
    assert body["model"] == "gpt-5.4-mini"
    assert body["reasoning"] == {"effort": "high"}
    assert "X-OpenAI-Internal-Codex-Responses-Lite" not in headers
    assert response.status_code == 200


def test_handle_openai_responses_chatgpt_oversize_is_truncated_before_upstream(monkeypatch):
    request = _build_request(
        {"model": "gpt-5.6-terra", "input": "keep this conversation alive"},
        {
            "Authorization": "Bearer sk-test",
            "ChatGPT-Account-ID": "acct-from-jwt",
        },
    )
    handler = _DummyOpenAIHandler()

    def _guard(payload, *, model):  # noqa: ARG001
        if payload.get("input") == "shortened":
            return False, 10, 100, 128_000
        return True, 200_000, 100, 128_000

    def _truncate(body, max_bytes, request_id):  # noqa: ARG001
        return {"model": body["model"], "input": "shortened"}

    handler._openai_responses_context_guard = _guard  # type: ignore[method-assign]
    monkeypatch.setattr(
        "cutctx.proxy.handlers.openai.responses._truncate_body_for_chatgpt",
        _truncate,
    )
    monkeypatch.setattr("cutctx.tokenizers.get_tokenizer", lambda model: _DummyTokenizer())

    response = anyio.run(handler.handle_openai_responses, request)

    assert response.status_code == 200
    assert handler.captured_request is not None
    _, url, _, body = handler.captured_request
    assert url == "https://chatgpt.com/backend-api/codex/responses"
    assert body["input"] == "shortened"


def test_handle_openai_responses_non_chatgpt_oversize_returns_413(monkeypatch):
    request = _build_request(
        {"model": "gpt-5.6-terra", "input": "keep this conversation alive"},
        {"Authorization": "Bearer sk-test"},
    )
    handler = _DummyOpenAIHandler()

    def _guard(payload, *, model):  # noqa: ARG001
        return True, 200_000, 100, 128_000

    handler._openai_responses_context_guard = _guard  # type: ignore[method-assign]
    monkeypatch.setattr("cutctx.tokenizers.get_tokenizer", lambda model: _DummyTokenizer())

    with pytest.raises(HTTPException) as exc_info:
        anyio.run(handler.handle_openai_responses, request)

    assert exc_info.value.status_code == 413
    assert handler.captured_request is None
    assert exc_info.value.detail["error"]["type"] == "context_too_large"


def test_handle_openai_responses_stream_skips_python_compression(monkeypatch):
    """PR-C5: Python no longer compresses /v1/responses (Rust handles it
    natively). The streaming forward path must still fire — only the
    Python compression dispatch is retired."""
    request = _build_request(
        {
            "model": "gpt-5.4",
            "stream": True,
            "instructions": "Keep it short",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello"}],
                }
            ],
        },
        {"Authorization": "Bearer sk-test"},
    )
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True

    monkeypatch.setattr("cutctx.tokenizers.get_tokenizer", lambda model: _DummyTokenizer())

    response = anyio.run(handler.handle_openai_responses, request)

    assert response.status_code == 200
    assert handler.captured_stream_request is not None
    assert handler.openai_pipeline.apply.call_count == 0
    assert handler.captured_stream_request[2]["stream"] is True


def test_handle_openai_responses_memory_timeout_fails_open(monkeypatch):
    class _SlowMemoryHandler:
        def __init__(self):
            self.config = SimpleNamespace(inject_context=True, inject_tools=False)

        async def search_and_format_context(self, memory_user_id, messages, **_kwargs):
            return "should not be used"

        def has_memory_tool_calls(self, response, provider):
            return False

    async def _timeout_wait_for(awaitable, timeout):
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise TimeoutError

    request = _build_request(
        {"model": "gpt-5.4", "input": "hello"},
        {"Authorization": "Bearer sk-test", "x-cutctx-user-id": "user-1"},
    )
    handler = _DummyOpenAIHandler()
    handler.memory_handler = _SlowMemoryHandler()

    monkeypatch.setattr("cutctx.tokenizers.get_tokenizer", lambda model: _DummyTokenizer())
    monkeypatch.setattr("cutctx.proxy.handlers.openai.asyncio.wait_for", _timeout_wait_for)

    response = anyio.run(handler.handle_openai_responses, request)

    assert response.status_code == 200
    assert handler.captured_request is not None
    _, _, _, body = handler.captured_request
    assert body.get("instructions") is None


def test_codex_responses_timeout_fails_open_in_standalone_proxy(monkeypatch):
    """Codex users running only the proxy still get fail-open on timeout."""
    request = _build_request(
        {
            "model": "gpt-5.4",
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": "large tool output",
                }
            ],
        },
        {"Authorization": "Bearer sk-test", "x-client": "codex"},
    )
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True

    monkeypatch.setattr("cutctx.tokenizers.get_tokenizer", lambda model: _DummyTokenizer())
    monkeypatch.setattr(
        handler,
        "_compress_openai_responses_payload",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()),
    )

    response = anyio.run(handler.handle_openai_responses, request)

    assert response.status_code == 200
    assert handler.captured_request is not None
    _, url, _, body = handler.captured_request
    assert url == "https://api.openai.com/v1/responses"
    assert body["input"][0]["output"] == "large tool output"


class _DummyWebSocket:
    def __init__(self, headers: dict[str, str]):
        self.headers = headers
        self.accepted_subprotocol = None

    async def accept(self, subprotocol=None):
        self.accepted_subprotocol = subprotocol


def test_handle_openai_responses_ws_resolves_codex_routing_headers():
    class SentinelError(RuntimeError):
        pass

    handler = _DummyOpenAIHandler()
    websocket = _DummyWebSocket({"authorization": "Bearer token"})

    with patch.dict(sys.modules, {"websockets": MagicMock()}):
        with patch(
            "cutctx.proxy.handlers.openai.responses._resolve_codex_routing_headers",
            side_effect=SentinelError("resolved"),
        ):
            with pytest.raises(SentinelError, match="resolved"):
                anyio.run(handler.handle_openai_responses_ws, websocket)

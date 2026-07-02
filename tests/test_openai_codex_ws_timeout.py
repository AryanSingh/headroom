"""Regression coverage for Codex websocket upstream timeout handling."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anyio

from cutctx.proxy.handlers.openai import OpenAIHandlerMixin


class _DummyMetrics:
    async def record_request(self, **kwargs):  # pragma: no cover - test helper
        return None

    async def record_stage_timings(self, path: str, timings: dict[str, float]) -> None:
        return None

    def inc_active_ws_sessions(self) -> None:
        return None

    def dec_active_ws_sessions(self) -> None:
        return None

    def inc_active_relay_tasks(self, n: int = 1) -> None:
        return None

    def dec_active_relay_tasks(self, n: int = 1) -> None:
        return None

    def observe_ws_session_duration(self, duration: float) -> None:
        return None

    def record_ws_termination(self, cause: str) -> None:
        return None


class _DummyOpenAIHandler(OpenAIHandlerMixin):
    OPENAI_API_URL = "https://api.openai.com"

    def __init__(self, *, connect_timeout_seconds: int) -> None:
        self.rate_limiter = None
        self.metrics = _DummyMetrics()
        self.config = SimpleNamespace(
            optimize=False,
            retry_max_attempts=1,
            retry_base_delay_ms=1,
            retry_max_delay_ms=1,
            connect_timeout_seconds=connect_timeout_seconds,
        )
        self.http_client = MagicMock()
        self.usage_reporter = None
        self.openai_provider = SimpleNamespace(get_context_limit=lambda model: 128_000)
        self.openai_pipeline = SimpleNamespace(apply=MagicMock())
        self.anthropic_backend = None
        self.cost_tracker = None
        self.memory_handler = None

    async def _next_request_id(self) -> str:
        return "req-ws-timeout"


class _FakeWebSocket:
    def __init__(self, headers: dict[str, str], frames: list[str]) -> None:
        self.headers = headers
        self._frames = list(frames)
        self.client = SimpleNamespace(host="127.0.0.1", port=12345)
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []
        self.closed = False
        self.close_code: int | None = None

    async def accept(self, subprotocol=None, headers=None) -> None:
        return None

    async def receive_text(self) -> str:
        if not self._frames:
            raise RuntimeError("WebSocketDisconnect: no more frames")
        return self._frames.pop(0)

    async def send_text(self, text: str) -> None:
        self.sent_text.append(text)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def close(self, code: int | None = None, reason: str | None = None) -> None:
        self.closed = True
        self.close_code = code


class _FakeUpstream:
    def __init__(self, events: list[str]) -> None:
        self._events = list(events)
        self.sent: list[str] = []
        self.closed = False
        self.response = SimpleNamespace(headers={})

    async def send(self, payload: str) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for event in self._events:
            yield event


def _make_fake_websockets_module(upstream: _FakeUpstream, capture: dict[str, object]):
    module = MagicMock()

    async def _connect(url: str, **kwargs):
        capture["url"] = url
        capture["kwargs"] = dict(kwargs)
        return upstream

    module.connect = _connect
    module.Subprotocol = str
    return module


def test_chatgpt_auth_ws_uses_extended_open_timeout() -> None:
    upstream = _FakeUpstream(
        [
            json.dumps({"type": "response.created", "response": {"id": "resp_1"}}),
            json.dumps({"type": "response.completed", "response": {"id": "resp_1"}}),
        ]
    )
    capture: dict[str, object] = {}
    client_ws = _FakeWebSocket(
        headers={
            "authorization": "Bearer fake-token",
            "chatgpt-account-id": "acct-test",
        },
        frames=[
            json.dumps(
                {
                    "type": "response.create",
                    "response": {"model": "gpt-5.4", "input": "hello"},
                }
            )
        ],
    )
    handler = _DummyOpenAIHandler(connect_timeout_seconds=2)

    with patch.dict(sys.modules, {"websockets": _make_fake_websockets_module(upstream, capture)}):
        anyio.run(handler.handle_openai_responses_ws, client_ws)

    assert capture["url"] == "wss://chatgpt.com/backend-api/codex/responses"
    assert capture["kwargs"]["open_timeout"] == 30

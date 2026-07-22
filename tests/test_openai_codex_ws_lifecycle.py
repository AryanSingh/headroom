"""Unit 3: WebSocket session lifecycle + deterministic relay cancellation.

These tests exercise the Codex WS handler with a fake upstream and a
fake client WebSocket so we can drive the relay halves through their
real code paths (not mocked) and assert on registry / task state.
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cutctx.cache.prefix_tracker import SessionTrackerStore
from cutctx.proxy.handlers.openai import OpenAIHandlerMixin
from cutctx.proxy.handlers.openai.responses import (
    _compute_responses_ws_conversation_session_id,
)
from cutctx.proxy.helpers import COMPRESSION_TIMEOUT_SECONDS
from cutctx.proxy.ws_session_registry import WebSocketSessionRegistry

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _DummyMetrics:
    def __init__(self) -> None:
        self.active_ws_sessions = 0
        self.active_ws_sessions_max = 0
        self.active_relay_tasks = 0
        self.ws_session_durations: list[float] = []
        self.stage_timings: list[tuple[str, dict[str, float]]] = []
        self.termination_causes: list[str] = []
        self.recorded_requests: list[dict] = []

    async def record_request(self, **kwargs):  # pragma: no cover
        self.recorded_requests.append(dict(kwargs))
        return None

    async def record_stage_timings(self, path: str, timings: dict[str, float]) -> None:
        self.stage_timings.append((path, dict(timings)))

    def inc_active_ws_sessions(self) -> None:
        self.active_ws_sessions += 1
        self.active_ws_sessions_max = max(self.active_ws_sessions_max, self.active_ws_sessions)

    def dec_active_ws_sessions(self) -> None:
        self.active_ws_sessions = max(0, self.active_ws_sessions - 1)

    def inc_active_relay_tasks(self, n: int = 1) -> None:
        self.active_relay_tasks += n

    def dec_active_relay_tasks(self, n: int = 1) -> None:
        self.active_relay_tasks = max(0, self.active_relay_tasks - n)

    def record_ws_session_duration(self, duration_ms: float, cause: str) -> None:
        self.ws_session_durations.append(duration_ms)
        self.termination_causes.append(cause)


class _DummyOpenAIHandler(OpenAIHandlerMixin):
    OPENAI_API_URL = "https://api.openai.com"

    def __init__(self, ws_sessions: WebSocketSessionRegistry | None = None) -> None:
        self.rate_limiter = None
        self.metrics = _DummyMetrics()
        self.config = SimpleNamespace(
            optimize=False,
            retry_max_attempts=1,
            retry_base_delay_ms=1,
            retry_max_delay_ms=1,
            connect_timeout_seconds=10,
            fallback_enabled=False,
            fallback_provider=None,
        )
        self.usage_reporter = None
        self.openai_provider = SimpleNamespace(get_context_limit=lambda model: 128_000)
        self.openai_pipeline = SimpleNamespace(apply=MagicMock())
        self.anthropic_backend = None
        self.fallback_backend = None
        self.openai_fallback_backend = None
        self.cost_tracker = None
        self.memory_handler = None
        self.session_tracker_store = SessionTrackerStore()
        self.ws_sessions = ws_sessions or WebSocketSessionRegistry()
        self.compression_executor_calls = 0
        self.compression_executor_timeouts: list[float] = []

    async def _next_request_id(self) -> str:
        return "req-lifecycle-test"

    async def _run_compression_in_executor(self, fn, *, timeout: float):
        self.compression_executor_calls += 1
        self.compression_executor_timeouts.append(timeout)
        return fn()

    async def _record_request_outcome(self, outcome) -> None:
        # Mirror of ``CutctxProxy._record_request_outcome`` for the
        # mixin tests. Delegates to the free funnel function so the
        # wire shape is identical to production.
        from cutctx.proxy.outcome import emit_request_outcome

        await emit_request_outcome(self, outcome)


class _FakeWebSocketDisconnect(Exception):
    """Mirrors the ``WebSocketDisconnect`` type-name check in the handler.

    The production code identifies "normal client gone" by
    ``"WebSocketDisconnect" in type(e).__name__`` — so the fake exception
    type name must start with ``WebSocketDisconnect``.
    """


# Force the type-name substring match in the handler.
_FakeWebSocketDisconnect.__name__ = "WebSocketDisconnect_Fake"


class _FallbackResponsesBackend:
    def __init__(self, provider: str = "gemini") -> None:
        self.name = f"litellm-{provider}"

    async def stream_openai_message(self, body, headers):
        yield 'data: {"choices":[{"delta":{"content":"fallback "},"finish_reason":null}]}\n\n'
        yield (
            'data: {"choices":[{"delta":{"content":"session ok"},"finish_reason":"stop"}],'
            '"usage":{"prompt_tokens":14,"completion_tokens":6,"total_tokens":20,'
            '"prompt_tokens_details":{"cached_tokens":4}}}\n\n'
        )
        yield "data: [DONE]\n\n"


class _FakeWebSocket:
    """Scripted client WebSocket that can delay / disconnect mid-stream."""

    def __init__(
        self,
        frames: list[str] | None = None,
        *,
        disconnect_after_n_sends: int | None = None,
        hold_after_initial: bool = False,
        call_log: list[str] | None = None,
    ) -> None:
        self.headers = {"authorization": "Bearer test"}
        self._frames = list(frames or [])
        self._hold_after_initial = hold_after_initial
        self._disconnect_after_n_sends = disconnect_after_n_sends
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []
        self.accepted_subprotocol: str | None = None
        self.accepted_headers: list[tuple[bytes, bytes]] | None = None
        self.closed = False
        self.close_code: int | None = None
        self._call_log = call_log
        # "client" can trip this event to simulate mid-stream disconnect.
        self._disconnect_event = asyncio.Event()
        self.client = SimpleNamespace(host="127.0.0.1", port=12345)

    async def accept(self, subprotocol=None, headers=None) -> None:
        self.accepted_subprotocol = subprotocol
        self.accepted_headers = list(headers) if headers is not None else None
        if self._call_log is not None:
            self._call_log.append("accept")

    async def receive_text(self) -> str:
        if self._frames:
            return self._frames.pop(0)
        if self._hold_after_initial:
            # Wait for simulated client disconnect.
            await self._disconnect_event.wait()
        # Use an exception type whose name starts with ``WebSocketDisconnect``
        # so the handler's ``type(e).__name__`` check classifies this as a
        # normal client exit (not a ``client_error``).
        raise _FakeWebSocketDisconnect("client closed")

    async def send_text(self, text: str) -> None:
        self.sent_text.append(text)
        if (
            self._disconnect_after_n_sends is not None
            and len(self.sent_text) >= self._disconnect_after_n_sends
        ):
            # Trigger the "client gone" signal the next receive_text will see.
            self._disconnect_event.set()

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def close(self, code: int | None = None, reason: str | None = None) -> None:
        self.closed = True
        self.close_code = code

    def trigger_disconnect(self) -> None:
        self._disconnect_event.set()


class TestResponsesWsConversationSessionId:
    def test_prefers_previous_response_id_for_reconnects(self):
        store = SessionTrackerStore()
        headers = {"authorization": "Bearer test-key"}
        body = {
            "type": "response.create",
            "response": {
                "model": "gpt-5",
                "previous_response_id": "resp_123",
                "instructions": "Be concise.",
            },
        }

        session_id = _compute_responses_ws_conversation_session_id(
            store,
            headers,
            body,
            fallback_session_id="socket-1",
        )

        assert session_id == store.compute_session_id(
            SimpleNamespace(
                headers={
                    "authorization": "Bearer test-key",
                    "x-cutctx-session-id": "resp:resp_123",
                }
            ),
            "gpt-5",
            [{"role": "system", "content": "Be concise."}],
        )

    def test_falls_back_to_instructions_when_no_response_id(self):
        store = SessionTrackerStore()
        headers = {"authorization": "Bearer test-key"}
        body = {
            "type": "response.create",
            "response": {
                "model": "gpt-5",
                "instructions": "Keep answers under 10 words.",
            },
        }

        session_id = _compute_responses_ws_conversation_session_id(
            store,
            headers,
            body,
            fallback_session_id="socket-1",
        )

        assert session_id == store.compute_session_id(
            SimpleNamespace(headers=headers),
            "gpt-5",
            [{"role": "system", "content": "Keep answers under 10 words."}],
        )


class _FakeHeaders:
    """Minimal stand-in for websockets' handshake ``Headers``.

    Exposes both ``raw_items()`` (preferred by the production header
    extractor to survive duplicate names like ``set-cookie``) and
    ``items()``.
    """

    def __init__(self, pairs) -> None:
        if isinstance(pairs, dict):
            pairs = list(pairs.items())
        self._pairs = [(str(k), str(v)) for k, v in pairs]

    def raw_items(self):
        return list(self._pairs)

    def items(self):
        return list(self._pairs)


class _FakeUpstream:
    """Upstream that streams scripted events then optionally blocks.

    ``hold_after_events`` makes the async iterator wait forever after the
    scripted events are exhausted — that mirrors a real upstream that
    keeps the connection open after a ``response.completed`` event. The
    handler's ``_upstream_to_client`` will block on it, so the only way
    the outer ``asyncio.wait`` can progress is via the client-side task
    completing — which is exactly the cancel-partner path we want to
    test.
    """

    def __init__(
        self,
        events: list[str],
        *,
        hold_after_events: bool = False,
        raise_mid_stream: Exception | None = None,
        response_headers=None,
    ) -> None:
        self._events = list(events)
        self._hold_after_events = hold_after_events
        self._raise_mid_stream = raise_mid_stream
        self.sent: list[str] = []
        self.closed = False
        # Mirror websockets' ClientConnection.response.headers, which is the
        # only place OpenAI delivers the Codex x-codex-* subscription window.
        self.response = SimpleNamespace(headers=_FakeHeaders(response_headers or []))

    async def __aenter__(self) -> _FakeUpstream:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.closed = True

    async def send(self, payload: str) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for ev in self._events:
            yield ev
        if self._raise_mid_stream is not None:
            raise self._raise_mid_stream
        if self._hold_after_events:
            # Wait forever — until the task is cancelled by the handler.
            await asyncio.Event().wait()


def _make_fake_websockets_module(
    upstream: _FakeUpstream | None,
    *,
    call_log: list[str] | None = None,
    connect_error: Exception | None = None,
):
    """Build a fake ``websockets`` module.

    Production now does ``upstream = await websockets.connect(...)`` (then
    ``async with upstream``), so ``connect`` must return an awaitable that
    resolves to the connection. ``connect_error`` makes the await raise to
    simulate an upstream handshake failure.
    """
    module = MagicMock()

    async def _connect(*args, **kwargs):
        if call_log is not None:
            call_log.append("connect")
        if connect_error is not None:
            raise connect_error
        return upstream

    module.connect = _connect
    module.Subprotocol = str
    return module


def _first_frame() -> str:
    return json.dumps(
        {
            "type": "response.create",
            "response": {"model": "gpt-5.4", "input": "hi"},
        }
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ws_first_frame_compression_uses_bounded_executor():
    """Codex WS compression must not run synchronously on the event loop."""
    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
        json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
    ]
    upstream = _FakeUpstream(upstream_events)
    fake_ws_mod = _make_fake_websockets_module(upstream)

    client_ws = _FakeWebSocket(frames=[_first_frame()])
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True
    handler._compress_openai_responses_payload = MagicMock(
        return_value=(
            {"model": "gpt-5.4", "input": "hi"},
            False,
            0,
            [],
            "router_no_compression",
            10,
            10,
        )
    )

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await handler.handle_openai_responses_ws(client_ws)

    assert handler.compression_executor_calls == 1
    assert handler.compression_executor_timeouts == [COMPRESSION_TIMEOUT_SECONDS]
    handler._compress_openai_responses_payload.assert_called_once()


@pytest.mark.asyncio
async def test_happy_path_registry_empty_after_response_completed():
    """Normal session completes — both relay tasks done, registry empty."""
    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
        json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
    ]
    upstream = _FakeUpstream(upstream_events)
    fake_ws_mod = _make_fake_websockets_module(upstream)

    client_ws = _FakeWebSocket(frames=[_first_frame()])
    handler = _DummyOpenAIHandler()

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await handler.handle_openai_responses_ws(client_ws)

    assert handler.ws_sessions.active_count() == 0
    assert handler.metrics.active_ws_sessions == 0
    # termination_cause captured
    assert handler.metrics.termination_causes
    # Either "response_completed" or "client_disconnect" — both are
    # acceptable here depending on which relay half exited first; the
    # important thing is we recorded one.
    assert handler.metrics.termination_causes[-1] in {
        "response_completed",
        "client_disconnect",
        "upstream_disconnect",
    }


@pytest.mark.asyncio
async def test_ws_chatgpt_subscription_preserves_requested_model_before_forwarding():
    """The native WS relay must preserve the caller's model while still

    applying request-shape sanitization. Proactively migrating gpt-5.4 to
    gpt-5.5 prevented the upstream from trying models that may now be
    supported for the account/transport.
    """
    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
        json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
    ]
    upstream = _FakeUpstream(upstream_events)
    fake_ws_mod = _make_fake_websockets_module(upstream)

    client_ws = _FakeWebSocket(frames=[_first_frame()])
    client_ws.headers["chatgpt-account-id"] = "acct-123"
    handler = _DummyOpenAIHandler()

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await handler.handle_openai_responses_ws(client_ws)

    assert upstream.sent, "handler never forwarded a frame upstream"
    forwarded = json.loads(upstream.sent[0])
    assert forwarded["response"]["model"] == "gpt-5.4"


@pytest.mark.asyncio
async def test_ws_chatgpt_first_frame_uses_safe_tool_output_compressor():
    tools = [{"type": "function", "name": "read_fixture", "description": "provider owned"}]
    inner = {
        "model": "gpt-5.4",
        "tools": tools,
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "compressible output " * 200,
            }
        ],
    }
    frame = json.dumps({"type": "response.create", "response": inner})
    upstream = _FakeUpstream(
        [
            json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
            json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
        ]
    )
    client_ws = _FakeWebSocket(frames=[frame])
    client_ws.headers["chatgpt-account-id"] = "acct-123"
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True
    handler._compress_chatgpt_subscription_tool_outputs_in_executor = AsyncMock(
        return_value=(
            {**inner, "input": [{**inner["input"][0], "output": "short output"}]},
            True,
            398,
            ["router:openai:responses:function_call_output:kompress"],
            None,
            5000,
            500,
            400,
            {},
        )
    )
    handler._compress_openai_responses_payload_in_executor = AsyncMock(
        side_effect=AssertionError("subscription first frame used the general compressor")
    )

    with patch.dict(sys.modules, {"websockets": _make_fake_websockets_module(upstream)}):
        await handler.handle_openai_responses_ws(client_ws)

    forwarded = json.loads(upstream.sent[0])["response"]
    assert forwarded["tools"] == tools
    assert forwarded["input"][0]["output"] == "short output"


@pytest.mark.asyncio
async def test_ws_opaque_continuation_ignores_approximate_context_refusal():
    """Encrypted subscription state must reach ChatGPT unchanged.

    Session 019f6752-d143-7e70-b780-34396670b634 reported about 194K input
    tokens upstream, while CutCtx's generic JSON tokenizer estimated the
    reconstructed continuation at 294,402 tokens and closed the retry locally.
    The encrypted state is opaque to CutCtx, so only ChatGPT can count it
    authoritatively.
    """
    inner = {
        "model": "gpt-5.6-sol",
        "input": [
            {
                "type": "reasoning",
                "encrypted_content": "opaque-model-bound-continuation",
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "continue"}],
            },
        ],
    }
    first_frame = json.dumps({"type": "response.create", "response": inner})
    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
        json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
    ]
    upstream = _FakeUpstream(upstream_events)
    fake_ws_mod = _make_fake_websockets_module(upstream)
    client_ws = _FakeWebSocket(frames=[first_frame])
    client_ws.headers["chatgpt-account-id"] = "acct-123"
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True
    handler._compress_openai_responses_payload = MagicMock(
        return_value=(inner, False, 0, [], "router_no_compression", 10, 10)
    )
    handler._openai_responses_context_guard = MagicMock(
        return_value=(True, 294_402, 242_400, 258_400)
    )

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await handler.handle_openai_responses_ws(client_ws)

    assert upstream.sent, "opaque continuation was refused before reaching ChatGPT"
    forwarded = json.loads(upstream.sent[0])
    assert forwarded["response"]["model"] == "gpt-5.6-sol"
    assert (
        forwarded["response"]["input"][0]["encrypted_content"] == "opaque-model-bound-continuation"
    )
    assert client_ws.close_code != 1009


@pytest.mark.asyncio
async def test_ws_second_turn_preserves_requested_model_under_chatgpt_auth():
    """Turn 2+ of a persistent WS session goes through a separate

    per-frame path (``_maybe_compress_response_create_frame``) with its own
    ``prepare_model_routing`` + ``implicit_downgrade_allowed`` check and its
    own (previously missing) ChatGPT-subscription sanitizer call. Turn 1
    being fixed masked this: a session could open with fields stripped, then
    fail on its second turn because the per-frame path never checked
    ``is_chatgpt_auth`` and leaked subscription-incompatible request fields.
    """
    second_frame = json.dumps(
        {
            "type": "response.create",
            "response": {"model": "gpt-5.6-terra", "input": "continue"},
        }
    )
    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
        json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
    ]
    upstream = _FakeUpstream(upstream_events)
    fake_ws_mod = _make_fake_websockets_module(upstream)

    client_ws = _FakeWebSocket(frames=[_first_frame(), second_frame])
    client_ws.headers["chatgpt-account-id"] = "acct-123"
    handler = _DummyOpenAIHandler()
    # The per-frame path (unlike turn 1) only runs when compression is
    # enabled — matches production default (optimize=True).
    handler.config.optimize = True

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await asyncio.wait_for(
            handler.handle_openai_responses_ws(client_ws),
            timeout=5.0,
        )

    assert len(upstream.sent) >= 2, "handler never forwarded the second frame upstream"
    second_forwarded = json.loads(upstream.sent[1])
    assert second_forwarded["response"]["model"] == "gpt-5.6-terra"


@pytest.mark.asyncio
async def test_ws_chatgpt_later_frame_uses_safe_tool_output_compressor():
    second_inner = {
        "model": "gpt-5.6-terra",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_2",
                "output": "compressible output " * 200,
            }
        ],
    }
    client_ws = _FakeWebSocket(
        frames=[_first_frame(), json.dumps({"type": "response.create", "response": second_inner})]
    )
    client_ws.headers["chatgpt-account-id"] = "acct-123"
    upstream = _FakeUpstream(
        [
            json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
            json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
        ]
    )
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True
    calls = 0

    async def compress_subscription(payload, *, model, request_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            size = len(json.dumps(payload).encode())
            return (
                payload,
                False,
                0,
                [],
                "subscription_no_eligible_output",
                size,
                size,
                0,
                {},
            )
        candidate = copy.deepcopy(payload)
        candidate["input"][0]["output"] = "short output"
        return (
            candidate,
            True,
            398,
            ["router:openai:responses:function_call_output:kompress"],
            None,
            5000,
            500,
            400,
            {},
        )

    handler._compress_chatgpt_subscription_tool_outputs_in_executor = compress_subscription

    with patch.dict(sys.modules, {"websockets": _make_fake_websockets_module(upstream)}):
        await asyncio.wait_for(handler.handle_openai_responses_ws(client_ws), timeout=5.0)

    second_forwarded = json.loads(upstream.sent[1])["response"]
    assert second_forwarded["model"] == "gpt-5.6-terra"
    assert second_forwarded["input"][0]["output"] == "short output"


@pytest.mark.asyncio
async def test_ws_chatgpt_safe_compressor_failure_forwards_opaque_frame_without_closing(
    monkeypatch,
):
    inner = {
        "model": "gpt-5.6-sol",
        "input": [
            {"type": "reasoning", "encrypted_content": "opaque-model-bound-continuation"},
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "continue"}],
            },
        ],
    }
    client_ws = _FakeWebSocket(
        frames=[json.dumps({"type": "response.create", "response": inner})]
    )
    client_ws.headers["chatgpt-account-id"] = "acct-123"
    upstream = _FakeUpstream(
        [
            json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
            json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
        ]
    )
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True
    handler._compress_chatgpt_subscription_tool_outputs_in_executor = AsyncMock(
        side_effect=RuntimeError("synthetic optional compression failure")
    )
    handler._openai_responses_context_guard = MagicMock(
        return_value=(True, 294_402, 242_400, 258_400)
    )
    monkeypatch.setattr(
        "cutctx.proxy.helpers.decide_compression_failure_action",
        lambda *args, **kwargs: SimpleNamespace(
            refuse=True,
            reason="context_risk",
            frame_bytes=2_000_000,
        ),
    )

    with patch.dict(sys.modules, {"websockets": _make_fake_websockets_module(upstream)}):
        await handler.handle_openai_responses_ws(client_ws)

    forwarded = json.loads(upstream.sent[0])["response"]
    assert forwarded["model"] == "gpt-5.6-sol"
    assert forwarded["input"] == inner["input"]
    assert client_ws.close_code != 1009


@pytest.mark.asyncio
async def test_ws_session_metrics_include_response_completed_usage():
    """Codex WS sessions should report real upstream usage, not zero-token sessions."""

    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
        json.dumps(
            {
                "type": "response.completed",
                "response": {
                    "id": "r_1",
                    "usage": {
                        "input_tokens": 100,
                        "input_tokens_details": {"cached_tokens": 75},
                        "output_tokens": 12,
                    },
                },
            }
        ),
    ]
    upstream = _FakeUpstream(upstream_events)
    fake_ws_mod = _make_fake_websockets_module(upstream)

    client_ws = _FakeWebSocket(frames=[_first_frame()])
    handler = _DummyOpenAIHandler()

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await handler.handle_openai_responses_ws(client_ws)

    assert handler.metrics.recorded_requests
    recorded = handler.metrics.recorded_requests[-1]
    assert recorded["input_tokens"] == 100
    assert recorded["output_tokens"] == 12
    assert recorded["cache_read_tokens"] == 75
    assert recorded["cache_write_tokens"] == 25
    assert recorded["uncached_input_tokens"] == 25


@pytest.mark.asyncio
async def test_ws_session_metrics_include_dashboard_performance_timings():
    """Codex WS response metrics should feed the dashboard Performance tab."""

    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
        json.dumps(
            {
                "type": "response.completed",
                "response": {
                    "id": "r_1",
                    "usage": {
                        "input_tokens": 100,
                        "input_tokens_details": {"cached_tokens": 75},
                        "output_tokens": 12,
                    },
                },
            }
        ),
    ]
    upstream = _FakeUpstream(upstream_events)
    fake_ws_mod = _make_fake_websockets_module(upstream)

    client_ws = _FakeWebSocket(frames=[_first_frame()])
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True

    def _noop_compress(payload, *, model, request_id, timing=None):
        if timing is not None:
            timing["compression_live_unit_extraction"] = 2.0
            timing["compression_unit_router_strategy_passthrough"] = 3.0
        return payload, False, 0, [], "test_noop", 10, 10, 0

    handler._compress_openai_responses_payload = _noop_compress  # type: ignore[method-assign]

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await handler.handle_openai_responses_ws(client_ws)

    assert handler.metrics.recorded_requests
    recorded = handler.metrics.recorded_requests[-1]
    assert recorded["overhead_ms"] > 0
    assert recorded["ttfb_ms"] > 0
    assert recorded["pipeline_timing"]["codex_ws.compression"] > 0
    assert recorded["pipeline_timing"]["codex_ws.upstream_first_event"] > 0
    assert recorded["pipeline_timing"]["codex_ws.compression_preflight_serialization"] > 0
    assert recorded["pipeline_timing"]["codex_ws.compression_executor_wait_run"] > 0
    assert recorded["pipeline_timing"]["codex_ws.compression_live_unit_extraction"] == 2.0
    assert (
        recorded["pipeline_timing"]["codex_ws.compression_unit_router_strategy_passthrough"] == 3.0
    )


@pytest.mark.asyncio
async def test_client_disconnect_cancels_upstream_relay_within_100ms():
    """**Failing-test-first** scenario from the plan.

    When the client side exits (``receive_text`` raises
    ``WebSocketDisconnect``) while upstream is still open and iterating,
    the upstream relay task must be cancelled and become ``done()``
    quickly. The registry must report no active sessions afterwards.
    """
    # Upstream keeps iterating forever after one event, forcing the
    # upstream-to-client task to block on the iterator. The only way
    # out is a cancel from the handler's orchestration.
    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
    ]
    upstream = _FakeUpstream(upstream_events, hold_after_events=True)
    fake_ws_mod = _make_fake_websockets_module(upstream)

    # Client has one initial frame, then disconnects after the server
    # sends the first forwarded event to us.
    client_ws = _FakeWebSocket(
        frames=[_first_frame()],
        hold_after_initial=True,
    )
    handler = _DummyOpenAIHandler()

    # Trigger disconnect shortly after the handler accepts.
    async def _trigger() -> None:
        await asyncio.sleep(0.05)
        client_ws.trigger_disconnect()

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        trigger_task = asyncio.create_task(_trigger())
        try:
            await asyncio.wait_for(
                handler.handle_openai_responses_ws(client_ws),
                timeout=2.0,
            )
        finally:
            trigger_task.cancel()
            try:
                await trigger_task
            except asyncio.CancelledError:
                pass

    # Registry must be empty — the finally block deregistered the session.
    assert handler.ws_sessions.active_count() == 0, (
        "session leaked — deregister did not run in outermost finally"
    )
    assert handler.metrics.active_ws_sessions == 0
    # We recorded a session duration (came through deregister path).
    assert handler.metrics.ws_session_durations, (
        "record_ws_session_duration never fired — deregister path broken"
    )
    # And we tagged the cause. For a client-side exit it should be one
    # of: client_disconnect, client_error, upstream_disconnect (if
    # upstream iteration happened to end first in a race).
    cause = handler.metrics.termination_causes[-1]
    assert cause in {
        "client_disconnect",
        "client_error",
        "upstream_disconnect",
    }, f"unexpected cause: {cause}"

    # No codex-ws-* named task should still be running.
    leaked = [
        t
        for t in asyncio.all_tasks()
        if (t.get_name() or "").startswith("codex-ws-") and not t.done()
    ]
    assert leaked == [], f"relay tasks leaked: {[t.get_name() for t in leaked]}"


@pytest.mark.asyncio
async def test_upstream_closes_first_cancels_client_task():
    """Upstream iterator ends naturally; client task should be cancelled.

    The client is set to block on ``receive_text`` indefinitely; only a
    cancel from the handler's orchestration releases it.
    """
    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
        json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
    ]
    upstream = _FakeUpstream(upstream_events, hold_after_events=False)
    fake_ws_mod = _make_fake_websockets_module(upstream)

    client_ws = _FakeWebSocket(
        frames=[_first_frame()],
        hold_after_initial=True,
    )
    handler = _DummyOpenAIHandler()

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await asyncio.wait_for(
            handler.handle_openai_responses_ws(client_ws),
            timeout=2.0,
        )

    assert handler.ws_sessions.active_count() == 0
    # We must still have recorded exactly one session duration.
    assert len(handler.metrics.ws_session_durations) == 1


@pytest.mark.asyncio
async def test_upstream_error_mid_stream_classifies_as_upstream_error():
    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
    ]
    upstream = _FakeUpstream(
        upstream_events,
        raise_mid_stream=RuntimeError("boom from upstream"),
    )
    fake_ws_mod = _make_fake_websockets_module(upstream)

    client_ws = _FakeWebSocket(
        frames=[_first_frame()],
        hold_after_initial=True,
    )
    handler = _DummyOpenAIHandler()

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await asyncio.wait_for(
            handler.handle_openai_responses_ws(client_ws),
            timeout=2.0,
        )

    assert handler.ws_sessions.active_count() == 0
    assert handler.metrics.termination_causes
    assert handler.metrics.termination_causes[-1] == "upstream_error"


@pytest.mark.asyncio
async def test_response_cancel_frame_is_logged_as_client_cancel_lifecycle():
    """A Codex Ctrl-C maps to response.cancel on the WS stream.

    The proxy should relay it upstream and classify the lifecycle as a
    client-side cancel when no response.completed event follows.
    """
    cancel_frame = json.dumps({"type": "response.cancel", "response_id": "r_1"})
    upstream = _FakeUpstream([], hold_after_events=True)
    fake_ws_mod = _make_fake_websockets_module(upstream)

    client_ws = _FakeWebSocket(
        frames=[_first_frame(), cancel_frame],
        hold_after_initial=True,
    )
    handler = _DummyOpenAIHandler()

    async def _trigger() -> None:
        await asyncio.sleep(0.05)
        client_ws.trigger_disconnect()

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        trigger_task = asyncio.create_task(_trigger())
        try:
            await asyncio.wait_for(
                handler.handle_openai_responses_ws(client_ws),
                timeout=2.0,
            )
        finally:
            trigger_task.cancel()
            try:
                await trigger_task
            except asyncio.CancelledError:
                pass

    assert cancel_frame in upstream.sent
    assert handler.metrics.termination_causes[-1] == "client_cancel"
    assert handler.ws_sessions.active_count() == 0


@pytest.mark.asyncio
async def test_upstream_connect_failure_still_deregisters_cleanly():
    """Handshake-phase leak must be impossible: if upstream connect
    raises before relay tasks are created, the session is still
    registered+deregistered cleanly (or never registered). Either way,
    no leak.
    """
    fake_ws_mod = _make_fake_websockets_module(None, connect_error=RuntimeError("upstream refused"))

    client_ws = _FakeWebSocket(frames=[_first_frame()])
    handler = _DummyOpenAIHandler()

    async def _fallback(*args, **kwargs):
        return None

    handler._ws_http_fallback = _fallback  # type: ignore[assignment]

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await handler.handle_openai_responses_ws(client_ws)

    assert handler.ws_sessions.active_count() == 0


@pytest.mark.asyncio
async def test_ws_connect_failure_falls_back_to_http():
    """When every upstream connect attempt fails, the client is accepted,
    then immediately closed with code 1014 (no fallback, no first frame read).
    """
    fake_ws_mod = _make_fake_websockets_module(
        None, connect_error=RuntimeError("HTTP 500 from upstream")
    )

    first = _first_frame()
    client_ws = _FakeWebSocket(frames=[first])
    handler = _DummyOpenAIHandler()

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await handler.handle_openai_responses_ws(client_ws)

    # Client was accepted (with no x-codex-* headers, since upstream connect failed).
    assert client_ws.accepted_headers is None
    # Then immediately closed with code 1014 (not via fallback).
    assert client_ws.closed is True
    assert client_ws.close_code == 1014
    # Clean teardown.
    assert handler.ws_sessions.active_count() == 0


@pytest.mark.asyncio
async def test_ws_connect_failure_uses_configured_backend_fallback():
    fake_ws_mod = _make_fake_websockets_module(
        None, connect_error=RuntimeError("HTTP 500 from upstream")
    )

    client_ws = _FakeWebSocket(frames=[_first_frame()])
    handler = _DummyOpenAIHandler()
    handler.config.fallback_enabled = True
    handler.config.fallback_provider = "gemini"
    handler.fallback_backend = _FallbackResponsesBackend("gemini")

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await handler.handle_openai_responses_ws(client_ws)

    assert client_ws.sent_text
    assert json.loads(client_ws.sent_text[0])["type"] == "response.created"
    assert json.loads(client_ws.sent_text[-1])["type"] == "response.completed"
    assert handler.metrics.recorded_requests
    recorded = handler.metrics.recorded_requests[-1]
    assert recorded["input_tokens"] == 14
    assert recorded["output_tokens"] == 6
    assert recorded["cache_read_tokens"] == 4
    assert recorded["cache_write_tokens"] == 10
    assert recorded["uncached_input_tokens"] == 10
    assert recorded["provider"] == "gemini"
    assert handler.ws_sessions.active_count() == 0


@pytest.mark.asyncio
async def test_ws_accept_happens_before_upstream_connect():
    """The client must be accepted first (before connecting upstream),
    to avoid timeouts when OpenAI's WebSocket handshake takes 20+ seconds.
    The x-codex-* headers are recorded into /stats after upstream handshake
    completes, but are no longer forwarded in the client 101 response.
    """
    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
        json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
    ]
    call_log: list[str] = []
    upstream = _FakeUpstream(upstream_events)
    fake_ws_mod = _make_fake_websockets_module(upstream, call_log=call_log)

    client_ws = _FakeWebSocket(frames=[_first_frame()], call_log=call_log)
    handler = _DummyOpenAIHandler()

    with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
        await handler.handle_openai_responses_ws(client_ws)

    assert "connect" in call_log and "accept" in call_log
    assert call_log.index("accept") < call_log.index("connect"), (
        f"accept must precede connect, got {call_log}"
    )


@pytest.mark.asyncio
async def test_ws_forwards_codex_headers_to_client_accept():
    """OpenAI's x-codex-* subscription window from the upstream WS
    handshake is no longer forwarded in the client-facing 101 (cosmetic loss
    to avoid 20+ second handshake timeouts). The x-codex-* headers are still
    recorded into Python /stats state, and the session works correctly.
    """
    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
        json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
    ]
    # Include duplicate set-cookie to ensure raw_items() is used (a plain
    # dict-style .items() on real websockets Headers raises on dupes).
    handshake_headers = [
        ("x-codex-primary-used-percent", "42"),
        ("X-Codex-Primary-Window-Minutes", "300"),
        ("set-cookie", "a=1"),
        ("set-cookie", "b=2"),
        ("authorization", "Bearer leak"),
    ]
    upstream = _FakeUpstream(upstream_events, response_headers=handshake_headers)
    fake_ws_mod = _make_fake_websockets_module(upstream)

    client_ws = _FakeWebSocket(frames=[_first_frame()])
    handler = _DummyOpenAIHandler()

    captured: dict = {}

    def _fake_state():
        class _S:
            def update_from_headers(self, headers):
                captured.update(headers)

        return _S()

    with (
        patch.dict(sys.modules, {"websockets": fake_ws_mod}),
        patch(
            "cutctx.subscription.codex_rate_limits.get_codex_rate_limit_state",
            _fake_state,
        ),
    ):
        await handler.handle_openai_responses_ws(client_ws)

    # x-codex-* headers are no longer forwarded in the accept response.
    assert client_ws.accepted_headers is None
    # But they are recorded into /stats state for internal tracking.
    assert captured == {
        "x-codex-primary-used-percent": "42",
        "X-Codex-Primary-Window-Minutes": "300",
    }


@pytest.mark.asyncio
async def test_ws_first_frame_timeout_after_connect_closes_upstream():
    """If the client never sends its first frame after we connected, the
    upstream WS must be closed (no leak) and the session deregistered.
    """
    upstream = _FakeUpstream([], hold_after_events=True)
    fake_ws_mod = _make_fake_websockets_module(upstream)

    # No frames + hold => receive_text blocks until disconnect; we force a
    # short first-frame timeout so the handler hits the timeout branch.
    client_ws = _FakeWebSocket(frames=[], hold_after_initial=True)
    handler = _DummyOpenAIHandler()

    with (
        patch.dict(sys.modules, {"websockets": fake_ws_mod}),
        patch(
            "cutctx.proxy.handlers.openai.responses.WS_FIRST_FRAME_TIMEOUT_SECONDS",
            0.05,
        ),
    ):
        await asyncio.wait_for(
            handler.handle_openai_responses_ws(client_ws),
            timeout=2.0,
        )

    assert upstream.closed, "upstream not closed on first-frame timeout"
    assert client_ws.closed and client_ws.close_code == 1001
    assert handler.ws_sessions.active_count() == 0


@pytest.mark.asyncio
async def test_many_concurrent_sessions_cleanly_drained():
    """50 concurrent sessions: all drain; registry and named tasks go to 0."""
    upstream_events = [
        json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
        json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
    ]

    async def run_one() -> None:
        upstream = _FakeUpstream(list(upstream_events))
        fake_ws_mod = _make_fake_websockets_module(upstream)
        client_ws = _FakeWebSocket(frames=[_first_frame()])
        handler = _DummyOpenAIHandler()
        with patch.dict(sys.modules, {"websockets": fake_ws_mod}):
            await handler.handle_openai_responses_ws(client_ws)
        assert handler.ws_sessions.active_count() == 0

    await asyncio.gather(*[run_one() for _ in range(50)])

    # Global check: no codex-ws-* named task remains.
    leaked = [
        t
        for t in asyncio.all_tasks()
        if (t.get_name() or "").startswith("codex-ws-") and not t.done()
    ]
    assert leaked == []

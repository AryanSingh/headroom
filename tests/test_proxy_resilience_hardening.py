"""Regression tests for the H14/H15/H16 resilience audit findings.

H14 — malformed unauthenticated input used to reach a handler and raise an
      unhandled exception (500 + traceback in the log) instead of a 4xx.
H15 — no total wall-clock deadline: a silent or byte-trickling upstream could
      hang a client for retries x inter-byte-timeout, or forever.
H16 — quadratic BPE tokenization on unbroken character runs, and no aggregate
      bound on in-flight request memory.

Plus: malformed upstream JSON relayed as 200, and env parsing that failed
open on unrecognised values.
"""

from __future__ import annotations

import asyncio
import json
import time

import anyio
import httpx
import pytest
from fastapi import HTTPException, Request

from cutctx.proxy.helpers import (
    MAX_JSON_NESTING_DEPTH,
    InFlightBodyBudget,
    check_json_nesting_depth,
    get_max_inflight_body_bytes,
    is_stateless,
    validate_request_body_shape,
)
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import _get_env_bool, _get_env_float, _get_env_int
from cutctx.tokenizers.bpe_guard import MAX_BPE_RUN_CHARS, iter_bpe_safe_chunks
from cutctx.tokenizers.estimator import EstimatingTokenCounter
from cutctx.tokenizers.registry import TokenizerRegistry
from tests.test_anthropic_pre_upstream_backpressure import (
    _DummyAnthropicHandler,
    _build_request,
    _tokenizer_patch,
)


def _raw_request(payload: bytes, path: str = "/v1/messages") -> Request:
    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"authorization", b"Bearer sk-ant-api-test")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    }
    return Request(scope, receive)


def _run_handler(request: Request):
    handler = _DummyAnthropicHandler()
    with _tokenizer_patch():
        return anyio.run(handler.handle_anthropic_messages, request)


def _error_message(response) -> str:
    return json.loads(bytes(response.body))["error"]["message"]


# --------------------------------------------------------------------------- #
# H14 — request-shape validation at the boundary                              #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("body", "expected_fragment"),
    [
        ({"model": 123, "messages": [{"role": "user", "content": "hi"}]}, "'model'"),
        ({"model": "claude-3-5-sonnet-latest", "messages": None}, "'messages'"),
        (
            {"model": "claude-3-5-sonnet-latest", "messages": {"role": "user"}},
            "'messages'",
        ),
        (
            {"model": "claude-3-5-sonnet-latest", "messages": ["not-an-object"]},
            "messages[0]",
        ),
    ],
)
def test_h14_malformed_body_returns_400_naming_the_field(body, expected_fragment):
    """Each of these used to raise an unhandled exception -> 500."""
    response = _run_handler(_build_request(body, {"authorization": "Bearer sk-ant-api-test"}))
    assert response.status_code == 400, response.status_code
    message = _error_message(response)
    assert expected_fragment in message, message
    assert "Traceback" not in message


def test_h14_deeply_nested_json_returns_400_not_recursionerror():
    """``RecursionError`` is not a ``ValueError`` — it escaped the parse guard."""
    payload = (
        '{"model":"claude-3-5-sonnet-latest","messages":'
        + "[" * 10_000
        + "]" * 10_000
        + "}"
    ).encode()
    response = _run_handler(_raw_request(payload))
    assert response.status_code == 400, response.status_code
    assert "nested too deeply" in _error_message(response)


def test_h14_nesting_depth_guard_boundary():
    ok = "[" * MAX_JSON_NESTING_DEPTH + "]" * MAX_JSON_NESTING_DEPTH
    check_json_nesting_depth(ok)  # must not raise
    too_deep = "[" * (MAX_JSON_NESTING_DEPTH + 1) + "]" * (MAX_JSON_NESTING_DEPTH + 1)
    with pytest.raises(ValueError, match="nested too deeply"):
        check_json_nesting_depth(too_deep)


def test_h14_nesting_depth_guard_ignores_brackets_inside_strings():
    """Brackets in string literals must not count toward depth."""
    payload = json.dumps({"messages": [{"role": "user", "content": "[" * 5_000}]})
    check_json_nesting_depth(payload)  # must not raise


def test_h14_shape_validator_accepts_realistic_bodies():
    """The guard must not reject anything a real client sends."""
    validate_request_body_shape(
        {
            "model": "claude-3-5-sonnet-latest",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
            "tools": [{"name": "t", "input_schema": {"type": "object"}}],
            "stream": True,
            "max_tokens": 1024,
            "system": "be brief",
            "metadata": {"user_id": "u1"},
        }
    )
    validate_request_body_shape({"contents": [{"role": "user", "parts": [{"text": "hi"}]}]})
    validate_request_body_shape({})


def test_h14_tokenizer_registry_rejects_non_string_model():
    with pytest.raises(TypeError, match="must be a string"):
        TokenizerRegistry.get(123)  # type: ignore[arg-type]


def test_h14_count_messages_rejects_non_list_and_non_dict_items():
    tokenizer = EstimatingTokenCounter()
    with pytest.raises(TypeError, match="messages must be a list"):
        tokenizer.count_messages(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"messages\[0\] must be a dict"):
        tokenizer.count_messages(["hi"])  # type: ignore[list-item]


# --------------------------------------------------------------------------- #
# H15 — total wall-clock deadline across retries                              #
# --------------------------------------------------------------------------- #


class _FakeHttpClient:
    """Upstream that accepts the connection and then behaves badly.

    ``per_attempt_delay`` models the time each attempt burns before httpx
    gives up on its own (inter-byte) timeout. With ``read_timeout_exc=True``
    the attempt ends in a retryable ``httpx.ReadTimeout``, which is exactly
    the slow-loris shape: every individual attempt is "fine", the aggregate
    is not.
    """

    def __init__(self, *, per_attempt_delay: float, read_timeout_exc: bool = False) -> None:
        self.per_attempt_delay = per_attempt_delay
        self.read_timeout_exc = read_timeout_exc
        self.attempts = 0

    async def post(self, url, **kwargs):
        self.attempts += 1
        await asyncio.sleep(self.per_attempt_delay)
        if self.read_timeout_exc:
            raise httpx.ReadTimeout("upstream trickled bytes then stalled")
        raise AssertionError("upstream should never have completed in this test")


def _proxy_with_fake_upstream(
    *, total_timeout: int, per_attempt_delay: float, read_timeout_exc: bool = False
):
    from cutctx.proxy.server import CutctxProxy

    config = ProxyConfig(
        cache_enabled=False,
        rate_limit_enabled=False,
        memory_enabled=False,
        optimize=False,
        request_total_timeout_seconds=total_timeout,
        retry_max_attempts=3,
        retry_base_delay_ms=1,
        retry_max_delay_ms=2,
    )
    proxy = CutctxProxy(config)
    proxy.http_client = _FakeHttpClient(
        per_attempt_delay=per_attempt_delay, read_timeout_exc=read_timeout_exc
    )
    return proxy


def test_h15_silent_upstream_hits_total_deadline_as_504():
    """Upstream accepts and never replies -> bounded 504, not a long hang."""
    proxy = _proxy_with_fake_upstream(total_timeout=1, per_attempt_delay=60.0)

    async def _run():
        started = time.monotonic()
        with pytest.raises(HTTPException) as excinfo:
            await proxy._retry_request(
                "POST",
                "https://api.anthropic.com/v1/messages",
                {},
                {"model": "claude-3-5-sonnet-latest", "messages": []},
            )
        return excinfo.value, time.monotonic() - started

    exc, elapsed = anyio.run(_run)
    assert exc.status_code == 504, exc.status_code
    assert "total request deadline" in str(exc.detail)
    # Without the deadline this would have waited retries x 60s.
    assert elapsed < 10.0, elapsed


def test_h15_slow_upstream_deadline_is_enforced_across_retries():
    """Per-attempt failures that individually fit the budget must still be
    bounded in aggregate — the deadline spans retries and backoff."""
    proxy = _proxy_with_fake_upstream(
        total_timeout=1, per_attempt_delay=0.4, read_timeout_exc=True
    )

    async def _run():
        started = time.monotonic()
        with pytest.raises(HTTPException) as excinfo:
            await proxy._retry_request(
                "POST",
                "https://api.anthropic.com/v1/messages",
                {},
                {"model": "claude-3-5-sonnet-latest", "messages": []},
            )
        return excinfo.value, time.monotonic() - started, proxy.http_client.attempts

    exc, elapsed, attempts = anyio.run(_run)
    assert exc.status_code == 504, exc.status_code
    assert attempts >= 1
    assert elapsed < 5.0, elapsed


def test_h15_deadline_disabled_when_configured_zero():
    config = ProxyConfig(request_total_timeout_seconds=0)
    assert config.request_total_timeout_seconds == 0


def test_h15_read_and_total_timeouts_are_separate_knobs():
    config = ProxyConfig()
    assert config.request_timeout_seconds > 0
    assert config.request_total_timeout_seconds > 0
    custom = ProxyConfig(request_timeout_seconds=17, request_total_timeout_seconds=23)
    assert (custom.request_timeout_seconds, custom.request_total_timeout_seconds) == (17, 23)


# --------------------------------------------------------------------------- #
# H16 — CPU amplification (quadratic BPE) and memory amplification            #
# --------------------------------------------------------------------------- #


def test_h16_bpe_guard_splits_only_pathological_runs():
    prose = "the quick brown fox jumps over the lazy dog " * 500
    assert list(iter_bpe_safe_chunks(prose)) == [prose]

    pathological = "A" * (MAX_BPE_RUN_CHARS * 4 + 7)
    chunks = list(iter_bpe_safe_chunks(pathological))
    assert len(chunks) == 5
    assert max(len(c) for c in chunks) <= MAX_BPE_RUN_CHARS
    assert "".join(chunks) == pathological


def test_h16_bpe_guard_preserves_text_around_long_runs():
    text = "before " + "B" * (MAX_BPE_RUN_CHARS * 2) + " after"
    chunks = list(iter_bpe_safe_chunks(text))
    assert "".join(chunks) == text
    assert max(len(c) for c in chunks) <= MAX_BPE_RUN_CHARS + len("before ")


def test_h16_single_run_token_count_is_not_quadratic():
    """100 KB of one repeated character used to cost seconds of CPU per count."""
    tiktoken = pytest.importorskip("tiktoken")
    del tiktoken
    from cutctx.tokenizers.tiktoken_counter import TiktokenCounter

    counter = TiktokenCounter("gpt-4")  # cl100k_base
    counter.count_text("warmup")  # pay the encoding load once

    def _elapsed(n: int) -> float:
        text = "A" * n
        start = time.perf_counter()
        counter.count_text(text)
        return time.perf_counter() - start

    small = _elapsed(25 * 1024)
    large = _elapsed(100 * 1024)
    # Quadratic would be ~16x for a 4x input. Allow generous slack for CI
    # noise but reject the quadratic regime.
    assert large < max(0.5, small * 8), (small, large)


def test_h16_inflight_body_budget_rejects_over_budget_and_releases():
    budget = InFlightBodyBudget(limit_bytes=1000)
    assert budget.try_reserve(600) is True
    assert budget.try_reserve(300) is True
    assert budget.try_reserve(200) is False  # would exceed 1000
    assert budget.rejections == 1
    budget.release(300)
    assert budget.try_reserve(200) is True
    assert budget.reserved_bytes == 800
    assert budget.peak_reserved == 900


def test_h16_inflight_body_budget_zero_disables():
    budget = InFlightBodyBudget(limit_bytes=0)
    assert budget.try_reserve(10**12) is True


def test_h16_inflight_budget_env_is_validated(monkeypatch):
    monkeypatch.delenv("CUTCTX_MAX_INFLIGHT_BODY_BYTES", raising=False)
    assert get_max_inflight_body_bytes() > 0
    monkeypatch.setenv("CUTCTX_MAX_INFLIGHT_BODY_BYTES", "1234")
    assert get_max_inflight_body_bytes() == 1234
    monkeypatch.setenv("CUTCTX_MAX_INFLIGHT_BODY_BYTES", "lots")
    with pytest.raises(ValueError, match="CUTCTX_MAX_INFLIGHT_BODY_BYTES"):
        get_max_inflight_body_bytes()


# --------------------------------------------------------------------------- #
# Malformed upstream JSON must be 502, not a relayed 200                      #
# --------------------------------------------------------------------------- #


class _MalformedJsonResponse:
    status_code = 200
    headers = {"content-type": "application/json"}
    text = "<html>upstream had a bad day</html>"
    content = b"<html>upstream had a bad day</html>"

    def json(self):
        raise json.JSONDecodeError("Expecting value", self.text, 0)


class _MalformedUpstreamHandler(_DummyAnthropicHandler):
    async def _retry_request(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return _MalformedJsonResponse()


def test_malformed_upstream_json_becomes_502_not_200():
    handler = _MalformedUpstreamHandler()
    request = _build_request(
        {"model": "claude-3-5-sonnet-latest", "messages": [{"role": "user", "content": "hi"}]},
        {"authorization": "Bearer sk-ant-api-test"},
    )
    with _tokenizer_patch():
        response = anyio.run(handler.handle_anthropic_messages, request)
    assert response.status_code == 502, response.status_code
    assert "malformed" in _error_message(response).lower()


# --------------------------------------------------------------------------- #
# Env parsing must fail fast, not fail open                                   #
# --------------------------------------------------------------------------- #


def test_get_env_bool_fails_fast_on_unrecognised_value(monkeypatch):
    """``CUTCTX_STATELESS='True '`` used to coerce to False — fail open."""
    monkeypatch.setenv("CUTCTX_STATELESS", "True ")
    assert _get_env_bool("CUTCTX_STATELESS", False) is True  # trailing space tolerated

    monkeypatch.setenv("CUTCTX_STATELESS", "yep")
    with pytest.raises(ValueError) as excinfo:
        _get_env_bool("CUTCTX_STATELESS", False)
    assert "CUTCTX_STATELESS" in str(excinfo.value)
    assert "'yep'" in str(excinfo.value)


def test_is_stateless_fails_fast_instead_of_open(monkeypatch):
    """The real ``CUTCTX_STATELESS`` reader is ``helpers.is_stateless``."""
    monkeypatch.delenv("CUTCTX_STATELESS", raising=False)
    assert is_stateless() is False

    monkeypatch.setenv("CUTCTX_STATELESS", "True ")
    assert is_stateless() is True  # used to silently be False -> fail open

    monkeypatch.setenv("CUTCTX_STATELESS", "off")
    assert is_stateless() is False

    monkeypatch.setenv("CUTCTX_STATELESS", "enabled?")
    with pytest.raises(ValueError, match="CUTCTX_STATELESS"):
        is_stateless()


@pytest.mark.parametrize("value", ["true", "TRUE", " on ", "1", "yes"])
def test_get_env_bool_accepts_known_truthy(monkeypatch, value):
    monkeypatch.setenv("CUTCTX_TEST_BOOL", value)
    assert _get_env_bool("CUTCTX_TEST_BOOL", False) is True


@pytest.mark.parametrize("value", ["false", "FALSE", " off ", "0", "no"])
def test_get_env_bool_accepts_known_falsy(monkeypatch, value):
    monkeypatch.setenv("CUTCTX_TEST_BOOL", value)
    assert _get_env_bool("CUTCTX_TEST_BOOL", True) is False


def test_get_env_int_and_float_fail_fast(monkeypatch):
    monkeypatch.setenv("CUTCTX_TEST_INT", "12x")
    with pytest.raises(ValueError) as excinfo:
        _get_env_int("CUTCTX_TEST_INT", 5)
    assert "CUTCTX_TEST_INT" in str(excinfo.value)
    assert "'12x'" in str(excinfo.value)

    monkeypatch.setenv("CUTCTX_TEST_FLOAT", "1.2.3")
    with pytest.raises(ValueError, match="CUTCTX_TEST_FLOAT"):
        _get_env_float("CUTCTX_TEST_FLOAT", 1.0)

    monkeypatch.setenv("CUTCTX_TEST_INT", " 42 ")
    assert _get_env_int("CUTCTX_TEST_INT", 5) == 42


def test_proxy_config_env_int_fails_fast(monkeypatch):
    monkeypatch.setenv("CUTCTX_REQUEST_TOTAL_TIMEOUT_SECONDS", "soon")
    with pytest.raises(ValueError, match="CUTCTX_REQUEST_TOTAL_TIMEOUT_SECONDS"):
        ProxyConfig()


def test_httpx_is_importable_for_type_annotations():
    """Guard against the test module drifting from the httpx-based fakes."""
    assert hasattr(httpx, "TimeoutException")

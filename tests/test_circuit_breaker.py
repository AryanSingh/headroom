"""Tests for the per-provider circuit breaker (commercial-readiness runbook Task 4).

Covers the state machine in isolation (``CircuitBreaker``) plus a minimal
integration test proving the shared ``_retry_request`` call site in
``server.py`` fast-fails with a 503 when a provider's breaker is OPEN,
without attempting the upstream call.
"""

from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock

import httpx
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from cutctx.proxy.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    get_circuit_breaker,
    infer_provider_from_url,
    reset_all_circuit_breakers,
)
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


@pytest.fixture(autouse=True)
def _clean_registry():
    """Isolate the process-wide breaker registry between tests."""
    reset_all_circuit_breakers()
    yield
    reset_all_circuit_breakers()


# --------------------------------------------------------------------------- #
# State machine unit tests                                                    #
# --------------------------------------------------------------------------- #


def test_starts_closed() -> None:
    breaker = CircuitBreaker("anthropic", failure_threshold=3, cooldown_s=30)
    assert breaker.state is CircuitState.CLOSED
    assert breaker.allow_request() is True


def test_opens_after_n_consecutive_failures() -> None:
    breaker = CircuitBreaker("anthropic", failure_threshold=3, cooldown_s=30)
    breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED
    breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN


def test_rejects_fast_while_open() -> None:
    breaker = CircuitBreaker("anthropic", failure_threshold=1, cooldown_s=30)
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    assert breaker.allow_request() is False
    # Still rejecting on repeated checks, no state corruption.
    assert breaker.allow_request() is False


def test_success_resets_consecutive_failure_count_while_closed() -> None:
    breaker = CircuitBreaker("anthropic", failure_threshold=3, cooldown_s=30)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    # Counter reset — two more failures should not open it.
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED


def test_transitions_to_half_open_after_cooldown() -> None:
    breaker = CircuitBreaker("anthropic", failure_threshold=1, cooldown_s=0.05)
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    time.sleep(0.08)
    assert breaker.state is CircuitState.HALF_OPEN
    assert breaker.allow_request() is True


def test_single_success_in_half_open_closes_breaker() -> None:
    breaker = CircuitBreaker("anthropic", failure_threshold=1, cooldown_s=0.05)
    breaker.record_failure()
    time.sleep(0.08)
    assert breaker.state is CircuitState.HALF_OPEN
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.allow_request() is True


def test_failure_in_half_open_reopens_breaker() -> None:
    breaker = CircuitBreaker("anthropic", failure_threshold=1, cooldown_s=0.05)
    breaker.record_failure()
    time.sleep(0.08)
    assert breaker.state is CircuitState.HALF_OPEN
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    assert breaker.allow_request() is False


def test_breaker_is_per_provider() -> None:
    """Opening one provider's breaker must not affect another's."""
    anthropic_breaker = get_circuit_breaker("anthropic")
    openai_breaker = get_circuit_breaker("openai")

    for _ in range(anthropic_breaker.failure_threshold):
        anthropic_breaker.record_failure()

    assert anthropic_breaker.state is CircuitState.OPEN
    assert openai_breaker.state is CircuitState.CLOSED
    assert openai_breaker.allow_request() is True


def test_get_circuit_breaker_returns_shared_instance() -> None:
    first = get_circuit_breaker("gemini")
    second = get_circuit_breaker("gemini")
    assert first is second


def test_failure_threshold_and_cooldown_read_from_env(monkeypatch) -> None:
    monkeypatch.setenv("CUTCTX_CIRCUIT_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("CUTCTX_CIRCUIT_COOLDOWN_S", "12")
    breaker = CircuitBreaker("anthropic")
    assert breaker.failure_threshold == 2
    assert breaker.cooldown_s == 12.0


def test_infer_provider_from_url() -> None:
    assert infer_provider_from_url("https://api.anthropic.com/v1/messages") == "anthropic"
    assert infer_provider_from_url("https://api.openai.com/v1/chat/completions") == "openai"
    assert infer_provider_from_url("https://chatgpt.com/backend-api/codex") == "openai"
    assert (
        infer_provider_from_url("https://generativelanguage.googleapis.com/v1/models")
        == "gemini"
    )
    assert infer_provider_from_url("https://cloudcode-pa.googleapis.com/v1internal") == "gemini"
    assert infer_provider_from_url("https://example.internal/proxy") == "unknown"


# --------------------------------------------------------------------------- #
# Integration: the real /v1/messages request path fast-fails on an OPEN      #
# breaker, without attempting the upstream call.                             #
# --------------------------------------------------------------------------- #


class _ExplodingTransport(httpx.AsyncBaseTransport):
    """Transport that fails the test if the upstream is ever actually called."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            "upstream should not have been called while the circuit breaker is OPEN"
        )


def _make_app():
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        log_requests=False,
        ccr_inject_tool=False,
        ccr_handle_responses=False,
        ccr_context_tracking=False,
        image_optimize=False,
    )
    app = create_app(config)
    proxy = app.state.proxy
    proxy.http_client = httpx.AsyncClient(transport=_ExplodingTransport())
    return TestClient(app), proxy


def test_open_breaker_fast_fails_request_without_hitting_upstream() -> None:
    client, _proxy = _make_app()

    # Force the anthropic breaker open directly (simpler + more deterministic
    # than driving N real upstream failures through the full stack).
    breaker = get_circuit_breaker("anthropic")
    breaker.record_failure()
    breaker.failure_threshold = 1
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN

    response = client.post(
        "/v1/messages",
        headers={
            "x-api-key": "test-key",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 503, response.text


def test_closed_breaker_allows_request_through_to_upstream() -> None:
    """Sanity check: a healthy (CLOSED) breaker doesn't interfere at all."""
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        log_requests=False,
        ccr_inject_tool=False,
        ccr_handle_responses=False,
        ccr_context_tracking=False,
        image_optimize=False,
    )
    app = create_app(config)
    proxy = app.state.proxy

    class _OkTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 3,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                },
            )

    proxy.http_client = httpx.AsyncClient(transport=_OkTransport())
    client = TestClient(app)

    response = client.post(
        "/v1/messages",
        headers={
            "x-api-key": "test-key",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )

    assert response.status_code == 200, response.text
    assert get_circuit_breaker("anthropic").state is CircuitState.CLOSED

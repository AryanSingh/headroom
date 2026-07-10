"""Tests for the /transformations/feed endpoint in the proxy server."""

import os

import pytest

# Skip if fastapi not available
pytest.importorskip("fastapi")

from httpx import ASGITransport, AsyncClient

from cutctx.proxy.models import RequestLog
from cutctx.proxy.server import create_app

_ADMIN_HEADERS = {"x-cutctx-admin-key": os.environ.get("CUTCTX_ADMIN_API_KEY", "")}


@pytest.fixture
def app():
    app = create_app()
    app.state.proxy.logger.log_file = None
    app.state.proxy.logger._logs.clear()
    return app


def _log_entry(**overrides) -> RequestLog:
    base = {
        "request_id": "trace-1",
        "timestamp": "2026-07-09T12:00:00Z",
        "provider": "openai",
        "model": "gpt-5.4-mini",
        "input_tokens_original": 1200,
        "input_tokens_optimized": 800,
        "output_tokens": 200,
        "tokens_saved": 400,
        "savings_percent": 33.3,
        "optimization_latency_ms": 12.5,
        "total_latency_ms": 88.1,
        "tags": {"decline_reason": "compression_disabled"},
        "cache_hit": False,
        "transforms_applied": ["smart_crusher"],
        "request_messages": [{"role": "user", "content": "before"}],
        "compressed_messages": [{"role": "user", "content": "after"}],
        "turn_id": "turn-1",
        "pipeline_timing": {"route_ms": 2.0, "compress_ms": 10.5},
        "decline_reason": "compression_disabled",
        "routing_metadata": {
            "requested_model": "gpt-5.4",
            "actual_model": "gpt-5.4-mini",
            "routed": True,
            "source_model": "gpt-5.4",
            "target_model": "gpt-5.4-mini",
            "reason": "low_complexity",
            "saved_tokens": 400,
            "saved_usd": 0.12,
        },
        "fallback": {
            "provider": "openai",
            "reason": "circuit_breaker_open",
            "attempted": False,
            "circuit_breaker_state": "open",
            "active_provider": "openai-primary",
        },
        "savings_by_source_tokens": {"cutctx_compression": 400, "model_routing": 400},
        "savings_by_source_usd": {"cutctx_compression": 0.04, "model_routing": 0.12},
        "request_cost_usd": 0.03,
    }
    base.update(overrides)
    return RequestLog(**base)


@pytest.mark.asyncio
async def test_transformations_feed_endpoint_returns_list(app):
    """The endpoint should return a list of recent transformations."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/transformations/feed", headers=_ADMIN_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "transformations" in data
    assert isinstance(data["transformations"], list)


@pytest.mark.asyncio
async def test_transformations_feed_returns_messages(app):
    """Each transformation exposes both the original request and the
    post-compression form that was actually sent upstream, plus the response.

    The pre/post pair is what makes compression legible: consumers can diff
    the two to see what the pipeline stripped, replaced, or kept.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/transformations/feed", headers=_ADMIN_HEADERS)

    data = response.json()
    transformations = data["transformations"]
    for t in transformations:
        assert "request_messages" in t
        assert t["request_messages"] is None or isinstance(t["request_messages"], list)
        assert "compressed_messages" in t
        assert t["compressed_messages"] is None or isinstance(t["compressed_messages"], list)
        assert "response_content" in t
        assert t["response_content"] is None or isinstance(t["response_content"], str)


@pytest.mark.asyncio
async def test_transformations_feed_includes_trace_metadata(app):
    app.state.proxy.logger.log(_log_entry())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/transformations/feed", headers=_ADMIN_HEADERS)

    assert response.status_code == 200
    transformation = next(
        row for row in response.json()["transformations"] if row["request_id"] == "trace-1"
    )
    assert transformation["decline_reason"] == "compression_disabled"
    assert transformation["optimization_latency_ms"] == 12.5
    assert transformation["total_latency_ms"] == 88.1
    assert transformation["pipeline_timing"] == {"route_ms": 2.0, "compress_ms": 10.5}
    assert transformation["routing"]["target_model"] == "gpt-5.4-mini"
    assert transformation["savings_by_source_tokens"]["model_routing"] == 400
    assert transformation["request_cost_usd"] == 0.03
    assert transformation["fallback"]["circuit_breaker_state"] == "open"


@pytest.mark.asyncio
async def test_transformations_feed_respects_limit(app):
    """The endpoint should respect a ?limit= query parameter."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/transformations/feed?limit=5", headers=_ADMIN_HEADERS)

    data = response.json()
    assert len(data["transformations"]) <= 5

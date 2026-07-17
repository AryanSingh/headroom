"""Tests for structured request trace inspector endpoints."""

import os

import pytest

pytest.importorskip("fastapi")

from httpx import ASGITransport, AsyncClient

from cutctx.proxy.models import ProxyConfig, RequestLog
from cutctx.proxy.server import create_app

_ADMIN_HEADERS = {"x-cutctx-admin-key": os.environ.get("CUTCTX_ADMIN_API_KEY", "")}


@pytest.fixture
def app():
    app = create_app()
    app.state.proxy.logger.log_file = None
    app.state.proxy.logger._logs.clear()
    return app


def _trace_entry(**overrides) -> RequestLog:
    base = {
        "request_id": "trace-1",
        "timestamp": "2026-07-09T12:00:00Z",
        "provider": "openai",
        "model": "gpt-5.4-mini",
        "input_tokens_original": 1500,
        "input_tokens_optimized": 900,
        "output_tokens": 250,
        "tokens_saved": 600,
        "savings_percent": 40.0,
        "optimization_latency_ms": 18.2,
        "total_latency_ms": 120.5,
        "tags": {"client": "codex", "project": "headroom"},
        "cache_hit": True,
        "transforms_applied": ["smart_crusher", "router:log"],
        "cache_saved_tokens": 200,
        "semantic_cache_saved_tokens": 50,
        "self_hosted_prefix_cache_saved_tokens": 25,
        "model_routing_saved_tokens": 300,
        "total_saved_tokens": 1175,
        "total_savings_percent": 78.3,
        "request_cost_usd": 0.08,
        "pipeline_timing": {"route_ms": 5.0, "compress_ms": 13.2},
        "decline_reason": None,
        "routing_metadata": {
            "requested_model": "gpt-5.4",
            "actual_model": "gpt-5.4-mini",
            "routed": True,
            "source_model": "gpt-5.4",
            "target_model": "gpt-5.4-mini",
            "reason": "low_complexity",
            "request_overrides": {"reasoning": {"effort": "high"}},
            "saved_tokens": 300,
            "saved_usd": 0.09,
        },
        "savings_by_source_tokens": {
            "cutctx_compression": 600,
            "provider_prompt_cache": 200,
            "semantic_cache": 50,
            "prefix_cache_self_hosted": 25,
            "model_routing": 300,
        },
        "savings_by_source_usd": {
            "cutctx_compression": 0.05,
            "model_routing": 0.09,
        },
        "request_messages": [{"role": "user", "content": "before"}],
        "compressed_messages": [{"role": "user", "content": "after"}],
        "response_content": "done",
        "turn_id": "turn-xyz",
        "fallback": {
            "provider": "openai",
            "reason": "circuit_breaker_open",
            "attempted": False,
            "circuit_breaker_state": "open",
            "circuit_breaker_retry_after_s": 12.5,
            "active_provider": "openai-primary",
            "active_base_url": "https://api.openai.com",
        },
    }
    base.update(overrides)
    return RequestLog(**base)


@pytest.mark.asyncio
async def test_request_trace_detail_endpoint_returns_structured_trace(app):
    app.state.proxy.logger.log(_trace_entry())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/transformations/traces/trace-1", headers=_ADMIN_HEADERS)

    assert response.status_code == 200
    trace = response.json()["trace"]
    assert trace["request_id"] == "trace-1"
    assert trace["provider"]["requested_model"] == "gpt-5.4"
    assert trace["provider"]["actual_model"] == "gpt-5.4-mini"
    assert trace["routing"]["routed"] is True
    assert trace["routing"]["request_overrides"] == {"reasoning": {"effort": "high"}}
    assert trace["compression"]["savings_by_source_tokens"]["cutctx_compression"] == 600
    assert trace["latency"]["pipeline_timing"] == {"route_ms": 5.0, "compress_ms": 13.2}
    assert trace["cache"]["provider_prompt_cache_saved_tokens"] == 200
    assert trace["fallback"]["circuit_breaker_state"] == "open"
    assert trace["fallback"]["active_provider"] == "openai-primary"
    assert trace["messages"]["compressed_messages"] == [{"role": "user", "content": "after"}]
    assert trace["decision_receipt"]["observation"]["completeness"] == "legacy"
    assert trace["decision_receipt"]["cache"]["provider_prompt_cache"]["status"] == "hit"


@pytest.mark.asyncio
async def test_trace_returns_persisted_receipt_verbatim(app):
    receipt = {
        "schema_version": 99,
        "observation": {"completeness": "complete", "payload_capture": "disabled"},
        "future_field": {"preserved": True},
    }
    app.state.proxy.logger.log(_trace_entry(decision_receipt=receipt))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/transformations/traces/trace-1", headers=_ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["trace"]["decision_receipt"] == receipt


@pytest.mark.asyncio
async def test_request_trace_list_endpoint_returns_recent_traces(app):
    app.state.proxy.logger.log(_trace_entry(request_id="trace-a"))
    app.state.proxy.logger.log(_trace_entry(request_id="trace-b"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/transformations/traces?limit=1", headers=_ADMIN_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["log_full_messages"] is False
    assert len(payload["traces"]) == 1
    assert payload["traces"][0]["request_id"] == "trace-b"


@pytest.mark.asyncio
async def test_request_trace_detail_endpoint_404s_for_unknown_request(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/transformations/traces/missing", headers=_ADMIN_HEADERS)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_real_compress_request_writes_trace_record(app):
    messages = [
        {"role": "user", "content": "Summarize this payload."},
        {
            "role": "tool",
            "tool_call_id": "call_trace",
            "content": "\n".join(
                f"row={i} status={'ok' if i % 5 else 'error'}" for i in range(120)
            ),
        },
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        compress_response = await client.post(
            "/v1/compress",
            json={"messages": messages, "model": "gpt-4o"},
            headers=_ADMIN_HEADERS,
        )
        traces_response = await client.get(
            "/transformations/traces?limit=5", headers=_ADMIN_HEADERS
        )

    assert compress_response.status_code == 200
    assert traces_response.status_code == 200

    traces = traces_response.json()["traces"]
    matching = [
        row
        for row in traces
        if row["provider"]["actual_model"] == "gpt-4o"
        and row["compression"]["tokens_saved"] == compress_response.json()["tokens_saved"]
    ]
    assert matching, traces
    trace_id = matching[0]["request_id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        detail_response = await client.get(
            f"/transformations/traces/{trace_id}",
            headers=_ADMIN_HEADERS,
        )

    assert detail_response.status_code == 200
    trace = detail_response.json()["trace"]
    assert trace["request_id"] == trace_id
    assert trace["provider"]["name"]
    assert (
        trace["compression"]["input_tokens_original"]
        >= trace["compression"]["input_tokens_optimized"]
    )


@pytest.mark.asyncio
async def test_request_trace_endpoints_fall_back_to_memory_when_shared_log_unavailable(
    app, monkeypatch
):
    app.state.proxy.logger.log_file = os.path.join(os.getcwd(), "unavailable-requests.jsonl")
    app.state.proxy.logger.log(_trace_entry(request_id="trace-fallback"))

    monkeypatch.setattr(
        "cutctx.proxy.request_logger._tail_lines",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk unavailable")),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        list_response = await client.get("/transformations/traces?limit=5", headers=_ADMIN_HEADERS)
        detail_response = await client.get(
            "/transformations/traces/trace-fallback",
            headers=_ADMIN_HEADERS,
        )

    assert list_response.status_code == 200
    assert any(row["request_id"] == "trace-fallback" for row in list_response.json()["traces"])
    assert detail_response.status_code == 200
    assert detail_response.json()["trace"]["request_id"] == "trace-fallback"


@pytest.mark.asyncio
async def test_rate_limit_denial_is_available_in_the_trace_inspector(tmp_path):
    app = create_app(
        ProxyConfig(
            cache_enabled=False,
            rate_limit_enabled=True,
            rate_limit_requests_per_minute=1,
            prefix_freeze_db_path=str(tmp_path / "prefix-tracker.db"),
        )
    )
    app.state.proxy.logger.log_file = None
    app.state.proxy.logger._logs.clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first_response = await client.post(
            "/v1/chat/completions",
            headers=_ADMIN_HEADERS,
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]},
        )
        # The first request can fail upstream in this isolated test app, but
        # it must still consume the same client's rate-limit bucket.
        assert first_response.status_code != 429
        response = await client.post(
            "/v1/chat/completions",
            headers=_ADMIN_HEADERS,
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]},
        )
        traces_response = await client.get(
            "/transformations/traces?limit=5", headers=_ADMIN_HEADERS
        )

    assert response.status_code == 429
    request_id = response.headers["x-request-id"]
    matching = [
        trace for trace in traces_response.json()["traces"] if trace["request_id"] == request_id
    ]
    assert matching
    assert matching[0]["compression"]["decline_reason"] == "rate_limit_exceeded"
    assert matching[0]["tags"]["rate_limit_denied"] == "true"
    assert matching[0]["decision_receipt"]["observation"]["completeness"] == "partial"
    assert matching[0]["decision_receipt"]["observation"]["missing"] == [
        "rate_limit_exceeded"
    ]

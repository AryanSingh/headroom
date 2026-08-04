"""End-to-end reconciliation for the Prometheus scrape surface."""

from __future__ import annotations

import re

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from cutctx.proxy.outcome import RequestOutcome
from cutctx.proxy.server import CutctxProxy, ProxyConfig, create_app


def _metric(payload: str, name: str) -> float:
    match = re.search(rf"^{re.escape(name)}\s+([-+0-9.eE]+)$", payload, re.MULTILINE)
    assert match is not None, f"missing metric {name}"
    return float(match.group(1))


def test_metrics_reconcile_with_observed_http_and_outcome_counts(monkeypatch) -> None:
    sequence = iter(
        [
            RequestOutcome(
                request_id="metrics-1",
                provider="openai",
                model="gpt-4o",
                original_tokens=120,
                optimized_tokens=100,
                output_tokens=20,
                tokens_saved=20,
                attempted_input_tokens=120,
            ),
            RequestOutcome(
                request_id="metrics-2",
                provider="openai",
                model="gpt-4o",
                original_tokens=240,
                optimized_tokens=200,
                output_tokens=30,
                tokens_saved=40,
                attempted_input_tokens=240,
            ),
        ]
    )

    async def fake_openai(self, request):  # type: ignore[no-untyped-def]
        await self._record_request_outcome(next(sequence))
        return JSONResponse({"ok": True})

    monkeypatch.setattr(CutctxProxy, "handle_openai_chat", fake_openai)
    app = create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            admin_api_key="metrics-admin",
        )
    )

    with TestClient(app) as client:
        assert client.post("/v1/chat/completions", json={}).status_code == 200
        assert client.post("/v1/chat/completions", json={}).status_code == 200
        scrape = client.get("/metrics", headers={"x-cutctx-admin-key": "metrics-admin"})

    assert scrape.status_code == 200, scrape.text
    payload = scrape.text
    assert _metric(payload, "cutctx_requests_total") == 2
    assert _metric(payload, "cutctx_tokens_input_total") == 300
    assert _metric(payload, "cutctx_tokens_output_total") == 50
    assert _metric(payload, "cutctx_tokens_saved_total") == 60

    # The scrape itself is active while its snapshot is rendered: three HTTP
    # requests accepted, the two provider requests completed, one active scrape.
    assert _metric(payload, "cutctx_inbound_requests_total") == 3
    assert _metric(payload, "cutctx_inbound_requests_completed_total") == 2
    assert _metric(payload, "cutctx_inbound_requests_active") == 1

"""Cross-provider enforcement tests for the proxy spend budget."""

from __future__ import annotations

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from cutctx.proxy.server import CutctxProxy, ProxyConfig, create_app


def _budget_app():
    return create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=True,
            budget_limit_usd=1.0,
            anthropic_api_url="https://api.anthropic.test",
            openai_api_url="https://api.openai.test",
            gemini_api_url="https://api.gemini.test",
        )
    )


def test_exhausted_budget_blocks_openai_and_gemini_before_upstream(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_openai(self, request):  # type: ignore[no-untyped-def]
        calls.append(request.url.path)
        return JSONResponse({"unexpected": "openai upstream reached"})

    async def fake_gemini(
        self, request, model, upstream_base_url=None, provider_name="gemini"
    ):  # type: ignore[no-untyped-def]
        calls.append(request.url.path)
        return JSONResponse({"unexpected": "gemini upstream reached"})

    monkeypatch.setattr(CutctxProxy, "handle_openai_chat", fake_openai)
    monkeypatch.setattr(CutctxProxy, "handle_gemini_generate_content", fake_gemini)

    app = _budget_app()
    tracker = app.state.proxy.cost_tracker
    assert tracker is not None
    tracker.record_cost(1.0)

    with TestClient(app) as client:
        openai = client.post("/v1/chat/completions", json={"model": "gpt-4o", "messages": []})
        gemini = client.post(
            "/v1beta/models/gemini-2.5-flash:generateContent",
            json={"contents": [{"role": "user", "parts": [{"text": "hello"}]}]},
        )

    assert openai.status_code == 429
    assert gemini.status_code == 429
    assert openai.json()["error"]["type"] == "budget_exceeded"
    assert gemini.json()["error"]["type"] == "budget_exceeded"
    assert calls == []

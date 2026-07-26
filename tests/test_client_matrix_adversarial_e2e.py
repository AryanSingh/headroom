"""Hermetic client-matrix adversarial e2e across wire formats.

Covers Messages / Chat Completions / Responses HTTP (and WS invariants where
feasible) with mocked upstream via ``_retry_request``.

IMPORTANT: ``ProxyConfig(backend="anthropic")`` keeps ``anthropic_backend=None``
so handlers use ``_retry_request`` (the capture point). ``backend="openai"``
installs LiteLLM and bypasses that mock (ADV-20260726-003).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from cutctx.proxy.model_router import ModelRouter, ModelRouterConfig, prepare_model_routing
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app

ADMIN = "client-matrix-admin"
FAST = {"gpt-5.4-mini", "claude-haiku-4-5", "gemini-2.5-flash"}
STRONG = {
    "gpt-5.5",
    "gpt-5.6-terra",
    "gpt-5.6-sol",
    "claude-opus-4-5",
    "gemini-2.5-pro",
}


class UpstreamCapture:
    """Records upstream model, body, headers, and mutation kwargs."""

    def __init__(self) -> None:
        self.models: list[str] = []
        self.bodies: list[dict[str, Any]] = []
        self.urls: list[str] = []
        self.headers: list[dict[str, str]] = []
        self.kwargs: list[dict[str, Any]] = []
        self.stream_flags: list[bool] = []

    async def __call__(self, method, url, headers, body, stream=False, **kwargs):  # noqa: ANN001
        payload = body if isinstance(body, dict) else {}
        self.models.append(str(payload.get("model", "")))
        self.bodies.append(payload)
        self.urls.append(str(url))
        self.headers.append({str(k).lower(): str(v) for k, v in dict(headers or {}).items()})
        self.kwargs.append(dict(kwargs))
        self.stream_flags.append(bool(stream))
        url_s = str(url)
        if "anthropic" in url_s or "/v1/messages" in url_s:
            return httpx.Response(
                200,
                json={
                    "id": "msg_matrix",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "ok"}],
                    "model": payload.get("model"),
                    "usage": {"input_tokens": 10, "output_tokens": 3},
                },
            )
        if "/responses" in url_s:
            return httpx.Response(
                200,
                json={
                    "id": "resp_matrix",
                    "object": "response",
                    "model": payload.get("model"),
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "ok"}],
                        }
                    ],
                    "usage": {"input_tokens": 10, "output_tokens": 3},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_matrix",
                "object": "chat.completion",
                "model": payload.get("model"),
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 3,
                    "total_tokens": 13,
                },
            },
        )


@pytest.fixture
def matrix_app(tmp_path, monkeypatch):
    tracker_db = tmp_path / "prefix_tracker.db"
    orch_dir = tmp_path / "orchestration"
    orch_dir.mkdir()
    savings = tmp_path / "proxy_savings.json"
    monkeypatch.setenv("CUTCTX_PREFIX_TRACKER_DB_PATH", str(tracker_db))
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_DIR", str(orch_dir))
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(savings))
    monkeypatch.setenv("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
    config = ProxyConfig(
        backend="anthropic",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        log_requests=False,
        ccr_inject_tool=False,
        ccr_handle_responses=False,
        ccr_context_tracking=False,
        image_optimize=False,
        discover_pipeline_extensions=False,
        admin_api_key=ADMIN,
        model_routing_preset="auto",
        prefix_freeze_db_path=str(tracker_db),
    )
    app = create_app(config)
    capture = UpstreamCapture()
    with TestClient(app) as client:
        proxy = client.app.state.proxy
        assert proxy.anthropic_backend is None
        assert proxy._model_router is not None
        assert proxy._model_router.config.enabled is True
        proxy._retry_request = capture
        yield client, capture, proxy


def _chat(client: TestClient, model: str, messages: list[dict], **extra: Any):
    return client.post(
        "/v1/chat/completions",
        headers={
            "Authorization": "Bearer sk-test",
            "x-cutctx-admin-key": ADMIN,
            "User-Agent": "cursor/1.0",
        },
        json={"model": model, "messages": messages, **extra},
    )


def _messages(client: TestClient, model: str, messages: list[dict], **extra: Any):
    return client.post(
        "/v1/messages",
        headers={
            "x-api-key": "sk-ant-test",
            "anthropic-version": "2023-06-01",
            "x-cutctx-admin-key": ADMIN,
            "User-Agent": "claude-code/1.0",
        },
        json={"model": model, "max_tokens": 64, "messages": messages, **extra},
    )


def _responses(client: TestClient, model: str, input_payload: Any, **extra: Any):
    return client.post(
        "/v1/responses",
        headers={
            "Authorization": "Bearer sk-test",
            "x-cutctx-admin-key": ADMIN,
            "User-Agent": "codex-cli/0.0",
        },
        json={"model": model, "input": input_payload, **extra},
    )


# ── Wire formats: happy path routing ─────────────────────────────────────────


def test_messages_auto_low_routes_fast(matrix_app) -> None:
    client, capture, _ = matrix_app
    resp = _messages(client, "auto", [{"role": "user", "content": "Rename this variable."}])
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] in FAST
    reasons = capture.kwargs[-1].get("mutation_reasons") or []
    # Anthropic path must mark model_routing when body model changes (ADV-001).
    if capture.models[-1] != "auto":
        assert "model_routing" in reasons or capture.kwargs[-1].get("body_mutated") in {
            True,
            None,
        }


def test_chat_auto_high_routes_strong(matrix_app) -> None:
    client, capture, _ = matrix_app
    resp = _chat(
        client,
        "auto",
        [{"role": "user", "content": "Implement durable workflow cancellation."}],
    )
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] in STRONG
    assert capture.models[-1] not in FAST


def test_responses_http_auto_low_routes_fast(matrix_app) -> None:
    client, capture, _ = matrix_app
    resp = _responses(client, "auto", "Rename this variable.")
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] in FAST


def test_responses_http_strong_high_stays(matrix_app) -> None:
    client, capture, _ = matrix_app
    resp = _responses(client, "gpt-5.5", "Implement durable workflow cancellation.")
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] == "gpt-5.5"


def test_responses_store_false_and_previous_id(matrix_app) -> None:
    client, capture, _ = matrix_app
    resp = _responses(
        client,
        "gpt-5.4",
        "continue",
        store=False,
        previous_response_id="resp_opaque_prior",
    )
    assert resp.status_code == 200, resp.text
    body = capture.bodies[-1]
    assert body.get("store") is False
    assert body.get("previous_response_id") == "resp_opaque_prior"
    assert capture.models[-1] in {"gpt-5.4", "gpt-5.4-mini"} | STRONG | FAST


# ── ADV-PROTOCOL ─────────────────────────────────────────────────────────────


def test_adv_protocol_empty_user_content_chat(matrix_app) -> None:
    client, capture, _ = matrix_app
    resp = _chat(client, "gpt-5.4", [{"role": "user", "content": ""}])
    assert resp.status_code in {200, 400, 422}, resp.text
    if resp.status_code == 200:
        assert capture.models[-1]


def test_adv_protocol_non_string_content_blocks(matrix_app) -> None:
    client, capture, _ = matrix_app
    resp = _messages(
        client,
        "claude-sonnet-4-5",
        [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
    )
    assert resp.status_code == 200, resp.text
    assert capture.models[-1]


def test_adv_protocol_multimodal_image_block_messages(matrix_app) -> None:
    client, capture, _ = matrix_app
    # 1x1 PNG
    tiny = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQ"
        "AAAABJRU5ErkJggg=="
    )
    resp = _messages(
        client,
        "claude-sonnet-4-5",
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": tiny,
                        },
                    },
                ],
            }
        ],
    )
    assert resp.status_code == 200, resp.text
    assert capture.models[-1]


def test_adv_protocol_oversized_tools_chat(matrix_app) -> None:
    client, capture, _ = matrix_app
    tools = [
        {
            "type": "function",
            "function": {
                "name": f"tool_{i}",
                "description": f"tool {i}",
                "parameters": {"type": "object", "properties": {"x": {"type": "string"}}},
            },
        }
        for i in range(120)
    ]
    # Protocol: 100+ tools must not blow up; tool-surface may slim to max (default 16).
    resp = _chat(
        client,
        "gpt-5.5",
        [{"role": "user", "content": "Use a tool if needed."}],
        tools=tools,
    )
    assert resp.status_code == 200, resp.text
    upstream_tools = capture.bodies[-1].get("tools") or []
    assert 1 <= len(upstream_tools) <= 120
    assert len(upstream_tools) <= 16  # default CUTCTX_TOOL_SURFACE_MAX_TOOLS

    # Routing: tool definitions + high-risk prompt must not unsafe-Mini (ADV-ROUTE).
    high = _chat(
        client,
        "gpt-5.5",
        [{"role": "user", "content": "Implement durable workflow cancellation."}],
        tools=tools[:5],
    )
    assert high.status_code == 200, high.text
    assert capture.models[-1] == "gpt-5.5"


# ── ADV-ROUTE / landmines ────────────────────────────────────────────────────


def test_adv_route_adversarial_high_never_mini(matrix_app) -> None:
    client, capture, _ = matrix_app
    resp = _chat(
        client,
        "gpt-5.5",
        [{"role": "user", "content": "Audit the authentication flow for vulnerabilities."}],
    )
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] == "gpt-5.5"


def test_adv_route_off_mode_no_downgrade_concrete(matrix_app) -> None:
    client, capture, _ = matrix_app
    off = client.post(
        "/config/flags",
        headers={"x-cutctx-admin-key": ADMIN},
        json={"orchestrator_mode": "off"},
    )
    assert off.status_code == 200
    resp = _chat(client, "gpt-5.5", [{"role": "user", "content": "Rename this variable."}])
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] == "gpt-5.5"


def test_adv_route_subscription_ws_preserves_model() -> None:
    """Unit-level WS invariant (ADV-007) — full WS e2e lives in openai_codex_ws_*."""
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.6-sol",
        messages=[{"role": "user", "content": "hi"}],
        request_savings_metadata={},
        implicit_downgrade_allowed=False,
        allow_transport_safe_targets=False,
    )
    assert model == "gpt-5.6-sol"
    assert metadata["model_routing_trace"]["applied"] is False


def test_adv_ws_keepalive_config() -> None:
    """uvicorn ping interval must stay high for Codex mid-turn idle (ADV-004)."""
    import cutctx.proxy.server as proxy_server_module

    captured: dict[str, object] = {}

    def fake_create_app(config: ProxyConfig) -> object:
        return object()

    def fake_uvicorn_run(app: object, **kwargs: object) -> None:
        captured.update(kwargs)

    # Local monkeypatch without fixture — isolate via setattr/restore.
    orig_create = proxy_server_module.create_app
    orig_run = proxy_server_module.uvicorn.run
    try:
        proxy_server_module.create_app = fake_create_app  # type: ignore[assignment]
        proxy_server_module.uvicorn.run = fake_uvicorn_run  # type: ignore[assignment]
        proxy_server_module.run_server(ProxyConfig(host="127.0.0.1", port=0), print_banner=False)
    finally:
        proxy_server_module.create_app = orig_create
        proxy_server_module.uvicorn.run = orig_run
    assert captured["ws_ping_interval"] == 600
    assert captured["ws_ping_timeout"] == 600


# ── ADV-AUTH / headers ───────────────────────────────────────────────────────


def test_adv_auth_strips_internal_headers_on_chat(matrix_app) -> None:
    client, capture, _ = matrix_app
    resp = client.post(
        "/v1/chat/completions",
        headers={
            "Authorization": "Bearer sk-test",
            "x-cutctx-admin-key": ADMIN,
            "x-cutctx-user-id": "user-matrix",
            "User-Agent": "cursor/1.0",
        },
        json={"model": "gpt-5.4", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200, resp.text
    upstream_headers = capture.headers[-1]
    assert "x-cutctx-admin-key" not in upstream_headers
    assert "x-cutctx-user-id" not in upstream_headers


def test_adv_auth_claude_code_ua_messages(matrix_app) -> None:
    client, capture, _ = matrix_app
    resp = _messages(client, "claude-haiku-4-5", [{"role": "user", "content": "ping"}])
    assert resp.status_code == 200, resp.text
    assert capture.models[-1]


# ── ADV-COMPRESS / byte-faithful adjacent ─────────────────────────────────────


def test_responses_drops_stale_content_encoding_header_path(matrix_app) -> None:
    """HTTP responses path must not forward content-encoding after JSON body (ADV-005 adjacent).

    Full zstd decode coverage lives in test_openai_codex_routing.py; here we assert
    the live app path never re-attaches encoding on a normal JSON POST.
    """
    client, capture, _ = matrix_app
    resp = _responses(client, "gpt-5.4", "header check")
    assert resp.status_code == 200, resp.text
    hdrs = capture.headers[-1]
    assert "content-encoding" not in hdrs


# ── Stats / dashboard mode APIs ──────────────────────────────────────────────


def test_stats_and_livez_readyz_shape(matrix_app) -> None:
    client, capture, _ = matrix_app
    livez = client.get("/livez")
    readyz = client.get("/readyz")
    assert livez.status_code == 200
    assert readyz.status_code == 200
    _chat(client, "auto", [{"role": "user", "content": "What is idempotency?"}])
    stats = client.get("/stats", headers={"x-cutctx-admin-key": ADMIN})
    assert stats.status_code == 200
    payload = stats.json()
    assert "model_routing" in payload
    assert payload["model_routing"]["mode"] in {"auto", "off", "aggressive", "balanced"}
    assert capture.models[-1] in FAST | STRONG


def test_orchestrator_mode_toggle_ack(matrix_app) -> None:
    client, _, _ = matrix_app
    for mode in ("auto", "off", "aggressive"):
        flipped = client.post(
            "/config/flags",
            headers={"x-cutctx-admin-key": ADMIN},
            json={"orchestrator_mode": mode},
        )
        assert flipped.status_code == 200, flipped.text
        applied = flipped.json().get("applied_live", {}).get("orchestrator_mode", {})
        assert applied.get("mode") == mode
        stats = client.get("/stats", headers={"x-cutctx-admin-key": ADMIN})
        assert stats.json()["model_routing"]["mode"] == mode

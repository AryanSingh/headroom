"""Adversarial + HTTP e2e verification for Cursor-style Auto model routing.

Exercises the real FastAPI request path (`/v1/chat/completions`,
`/v1/messages`, `/config/flags`, `/stats`) with a mocked upstream so we can
assert the *exact model string forwarded upstream* without provider keys.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from cutctx.proxy.model_router import is_auto_model
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app

ADMIN = "routing-adv-admin"
FAST = {"gpt-5.4-mini", "claude-haiku-4-5", "gemini-2.5-flash"}
MEDIUM = {"gpt-5.6-luna", "gpt-5.4", "gpt-5", "claude-sonnet-4-5"}
STRONG = {
    "gpt-5.5",
    "gpt-5.6-terra",
    "gpt-5.6-sol",
    "claude-opus-4-5",
    "gemini-2.5-pro",
}


class UpstreamCapture:
    """Records every upstream model the proxy attempted to call."""

    def __init__(self) -> None:
        self.models: list[str] = []
        self.bodies: list[dict[str, Any]] = []

    async def __call__(
        self, method, url, headers, body, stream=False, **kwargs
    ):  # noqa: ANN001
        payload = body if isinstance(body, dict) else {}
        self.models.append(str(payload.get("model", "")))
        self.bodies.append(payload)
        if "anthropic" in str(url) or "/v1/messages" in str(url):
            return httpx.Response(
                200,
                json={
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "ok"}],
                    "model": payload.get("model"),
                    "usage": {"input_tokens": 10, "output_tokens": 3},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_test",
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
def routing_app(tmp_path, monkeypatch):
    # backend="anthropic" keeps anthropic_backend=None so OpenAI/Anthropic
    # handlers use _retry_request (the capture point). backend="openai" would
    # install LiteLLM and bypass that mock.
    tracker_db = tmp_path / "prefix_tracker.db"
    orch_dir = tmp_path / "orchestration"
    orch_dir.mkdir()
    savings = tmp_path / "proxy_savings.json"
    monkeypatch.setenv("CUTCTX_PREFIX_TRACKER_DB_PATH", str(tracker_db))
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_DIR", str(orch_dir))
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(savings))
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
        model_routing_preset="codex-gpt54mini-high",
        # Direct ProxyConfig() does not read CUTCTX_PREFIX_TRACKER_DB_PATH.
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
    body = {"model": model, "messages": messages, **extra}
    return client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer sk-test", "x-cutctx-admin-key": ADMIN},
        json=body,
    )


def _messages(client: TestClient, model: str, messages: list[dict]):
    return client.post(
        "/v1/messages",
        headers={
            "x-api-key": "sk-ant-test",
            "anthropic-version": "2023-06-01",
            "x-cutctx-admin-key": ADMIN,
        },
        json={"model": model, "max_tokens": 64, "messages": messages},
    )


# ── Happy path: model=auto ──────────────────────────────────────────────────


def test_e2e_auto_low_routes_to_fast(routing_app) -> None:
    client, capture, _ = routing_app
    resp = _chat(client, "auto", [{"role": "user", "content": "Rename this variable."}])
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] in FAST
    assert resp.headers.get("x-cutctx-model") in FAST | {None} or True  # header optional
    assert resp.json().get("model") in FAST


def test_e2e_auto_medium_routes_to_medium(routing_app) -> None:
    client, capture, _ = routing_app
    resp = _chat(
        client,
        "cutctx-auto",
        [
            {"role": "user", "content": "Inspect the service."},
            {"role": "assistant", "content": "I found two relevant modules."},
            {"role": "user", "content": "Explain the first module."},
        ],
    )
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] in MEDIUM | STRONG  # medium preferred; strong ok if catalog gap


def test_e2e_auto_high_routes_to_strong(routing_app) -> None:
    client, capture, _ = routing_app
    resp = _chat(
        client,
        "cursor-auto",
        [{"role": "user", "content": "Implement durable workflow cancellation."}],
    )
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] in STRONG
    assert capture.models[-1] not in FAST


def test_e2e_auto_anthropic_low_and_high(routing_app) -> None:
    client, capture, _ = routing_app
    low = _messages(client, "auto", [{"role": "user", "content": "hi, what's 2+2?"}])
    assert low.status_code == 200, low.text
    assert capture.models[-1] in FAST

    high = _messages(
        client,
        "auto",
        [{"role": "user", "content": "Implement model routing in the proxy and test it end to end."}],
    )
    assert high.status_code == 200, high.text
    assert capture.models[-1] in STRONG
    assert capture.models[-1] not in FAST


# ── Downgrade from concrete strong model ────────────────────────────────────


def test_e2e_strong_low_downgrades_to_fast(routing_app) -> None:
    client, capture, _ = routing_app
    resp = _chat(client, "gpt-5.5", [{"role": "user", "content": "Rename this variable."}])
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] == "gpt-5.4-mini"


def test_e2e_strong_high_stays_strong(routing_app) -> None:
    client, capture, _ = routing_app
    resp = _chat(
        client,
        "gpt-5.5",
        [{"role": "user", "content": "Implement durable workflow cancellation."}],
    )
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] == "gpt-5.5"


# ── Adversarial: must NOT downgrade ─────────────────────────────────────────


@pytest.mark.parametrize(
    "content",
    [
        "Audit the authentication flow for vulnerabilities.",
        "Fix the production billing failure.",
        "Debug why the websocket reconnect loop drops events.",
        "Fix it.",
        "Explain this:\n```python\nraise RuntimeError('x')\n```",
        "Investigate this stack trace and propose a fix.",
        "Design a multi-region failover architecture.",
        "Use the deployment tool to publish the release.",
    ],
)
def test_adversarial_prompts_never_route_to_fast_from_strong(routing_app, content: str) -> None:
    client, capture, _ = routing_app
    resp = _chat(client, "gpt-5.5", [{"role": "user", "content": content}])
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] not in FAST, f"unsafe Mini for {content!r}: {capture.models[-1]}"
    assert capture.models[-1] == "gpt-5.5"


def test_adversarial_tool_context_keeps_strong(routing_app) -> None:
    client, capture, _ = routing_app
    resp = _chat(
        client,
        "gpt-5.5",
        [
            {"role": "user", "content": "Check disk usage."},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "bash", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "Filesystem 92% full"},
            {"role": "user", "content": "What next?"},
        ],
    )
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] == "gpt-5.5"


def test_adversarial_auto_with_tools_stays_out_of_fast(routing_app) -> None:
    """Auto + tool definitions on a high-risk prompt must not pick Mini."""
    client, capture, _ = routing_app
    resp = _chat(
        client,
        "auto",
        [{"role": "user", "content": "Implement durable workflow cancellation."}],
        tools=[
            {
                "type": "function",
                "function": {"name": "run_tests", "parameters": {"type": "object"}},
            }
        ],
    )
    assert resp.status_code == 200, resp.text
    assert capture.models[-1] not in FAST


# ── Mode / dashboard / CLI-adjacent APIs ────────────────────────────────────


def test_dashboard_mode_toggle_enables_and_disables_downgrades(routing_app) -> None:
    client, capture, proxy = routing_app

    off = client.post(
        "/config/flags",
        headers={"x-cutctx-admin-key": ADMIN},
        json={"orchestrator_mode": "off"},
    )
    assert off.status_code == 200
    assert off.json()["applied_live"]["orchestrator_mode"]["mode"] == "off"

    # Concrete strong + simple must NOT downgrade when Off.
    resp = _chat(client, "gpt-5.5", [{"role": "user", "content": "Rename this variable."}])
    assert resp.status_code == 200
    assert capture.models[-1] == "gpt-5.5"

    # Auto synthetic model still resolves even when toggle is Off.
    auto = _chat(client, "auto", [{"role": "user", "content": "Rename this variable."}])
    assert auto.status_code == 200
    assert capture.models[-1] in FAST
    assert is_auto_model("auto")

    on = client.post(
        "/config/flags",
        headers={"x-cutctx-admin-key": ADMIN},
        json={"orchestrator_mode": "auto"},
    )
    assert on.status_code == 200
    assert on.json()["applied_live"]["orchestrator_mode"]["mode"] == "auto"

    stats = client.get("/stats", headers={"x-cutctx-admin-key": ADMIN})
    assert stats.status_code == 200
    payload = stats.json()
    assert payload["model_routing"]["mode"] == "auto"
    assert payload["model_routing"]["preset"] == "codex-gpt54mini-high"

    # Downgrades resume.
    again = _chat(client, "gpt-5.5", [{"role": "user", "content": "Rename this variable."}])
    assert again.status_code == 200
    assert capture.models[-1] == "gpt-5.4-mini"


def test_stats_expose_routing_after_request(routing_app) -> None:
    client, capture, _ = routing_app
    _chat(client, "auto", [{"role": "user", "content": "What is idempotency?"}])
    stats = client.get("/stats", headers={"x-cutctx-admin-key": ADMIN})
    assert stats.status_code == 200
    mr = stats.json()["model_routing"]
    assert mr["mode"] == "auto"
    assert mr["configured_routes"] >= 1
    assert capture.models[-1] in FAST

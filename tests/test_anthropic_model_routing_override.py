"""The Anthropic handler must actually send the routed model upstream.

Regression coverage for a bug that made model routing a no-op on the entire
Anthropic path — which is the path Claude Code uses. The handler computed the
routing decision correctly and recorded its savings metadata, then applied the
override with ``dataclasses.replace(body, model=...)``. ``body`` is a plain
dict, so that call raised ``TypeError`` on every request, and a bare
``except Exception: pass`` swallowed it. Upstream kept receiving the original
model.

Nothing caught it because the existing tests exercise ``prepare_model_routing``
directly and assert on its return value. These tests assert the contract that
actually matters: the model in the request that leaves the proxy.
"""

from __future__ import annotations

import httpx
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from cutctx.proxy.model_router import ModelRoute, ModelRouter, ModelRouterConfig
from cutctx.proxy.server import ProxyConfig, create_app

_UPSTREAM_RESPONSE = {
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
}

#: Claude Code's real User-Agent. Its requests classify as SUBSCRIPTION auth
#: mode, so routing them is exactly the case that was silently broken.
_CLAUDE_CODE_UA = "claude-cli/2.1.214 (external, cli)"


def _make_client() -> TestClient:
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        log_requests=False,
        ccr_inject_tool=False,
        ccr_handle_responses=False,
        ccr_context_tracking=False,
    )
    return TestClient(create_app(config))


def _downgrade_router() -> ModelRouter:
    """Router that unconditionally downgrades Opus to Haiku."""
    return ModelRouter(
        ModelRouterConfig(
            enabled=True,
            downgrade_when="always",
            routes=[
                ModelRoute(
                    source="claude-opus-4-5",
                    target="claude-haiku-4-5",
                    source_cost_per_mtok=15.0,
                    target_cost_per_mtok=0.8,
                )
            ],
        )
    )


def _capture_upstream(proxy) -> dict:  # noqa: ANN001
    captured: dict = {}

    async def _fake_retry(method, url, headers, body, stream=False, **kwargs):  # noqa: ANN001
        captured["body"] = body
        return httpx.Response(200, json=_UPSTREAM_RESPONSE)

    proxy._retry_request = _fake_retry
    return captured


def _post(client: TestClient, model: str):  # noqa: ANN202
    return client.post(
        "/v1/messages",
        headers={
            "x-api-key": "test-key",
            "anthropic-version": "2023-06-01",
            "user-agent": _CLAUDE_CODE_UA,
        },
        json={
            "model": model,
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "say hi"}],
        },
    )


def test_routed_model_reaches_upstream() -> None:
    """The whole point of routing: upstream must receive the cheaper model."""
    with _make_client() as client:
        proxy = client.app.state.proxy
        proxy._model_router = _downgrade_router()
        captured = _capture_upstream(proxy)

        response = _post(client, "claude-opus-4-5")

        assert response.status_code == 200
        assert captured["body"]["model"] == "claude-haiku-4-5"


def test_unrouted_model_passes_through_unchanged() -> None:
    """A model with no matching route must not be rewritten."""
    with _make_client() as client:
        proxy = client.app.state.proxy
        proxy._model_router = _downgrade_router()
        captured = _capture_upstream(proxy)

        response = _post(client, "claude-sonnet-4-5")

        assert response.status_code == 200
        assert captured["body"]["model"] == "claude-sonnet-4-5"


def test_no_router_leaves_model_untouched() -> None:
    with _make_client() as client:
        proxy = client.app.state.proxy
        proxy._model_router = None
        captured = _capture_upstream(proxy)

        response = _post(client, "claude-opus-4-5")

        assert response.status_code == 200
        assert captured["body"]["model"] == "claude-opus-4-5"


def test_router_failure_does_not_break_the_request() -> None:
    """Routing stays best-effort: a broken router must not drop traffic.

    The original code achieved this with a bare ``except: pass``, which is
    also what hid the override bug. Behaviour is preserved; the swallow now
    logs, and this test pins the passthrough guarantee independently.
    """

    class _ExplodingRouter:
        config = object()

        def maybe_route(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
            raise RuntimeError("router exploded")

    with _make_client() as client:
        proxy = client.app.state.proxy
        proxy._model_router = _ExplodingRouter()
        captured = _capture_upstream(proxy)

        response = _post(client, "claude-opus-4-5")

        assert response.status_code == 200
        assert captured["body"]["model"] == "claude-opus-4-5"

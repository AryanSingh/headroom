from __future__ import annotations

import pytest


class _StatsStub:
    def __init__(self, payload: dict):
        self._payload = payload

    def get_stats(self) -> dict:
        return dict(self._payload)


class _ToinStub:
    def get_stats(self) -> dict:
        return {"patterns": 0}


def test_stats_surface_truthful_knowledge_graph_status(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import cutctx.proxy.server as server
    from cutctx.proxy.server import ProxyConfig, create_app

    monkeypatch.setattr(
        server,
        "get_compression_store",
        lambda **kwargs: _StatsStub({}),
    )
    monkeypatch.setattr(
        server,
        "get_telemetry_collector",
        lambda **kwargs: _StatsStub({}),
    )
    monkeypatch.setattr(
        server,
        "get_compression_feedback",
        lambda **kwargs: _StatsStub({}),
    )
    monkeypatch.setattr(server, "_get_context_tool_stats", lambda: None)
    monkeypatch.setattr(server, "get_toin", lambda: _ToinStub())

    app = create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            log_requests=False,
            ccr_inject_tool=False,
            ccr_handle_responses=False,
            ccr_context_tracking=False,
        )
    )

    app.state.proxy.knowledge_graph_status = {
        "requested": True,
        "enabled": True,
        "available": False,
        "active": False,
        "status": "unavailable",
        "reason": "graphify_not_installed",
        "interceptor_registered": False,
        "version": None,
    }
    monkeypatch.setattr(server, "_kg_idx", None, raising=False)
    monkeypatch.setattr(server, "_kg_indexer", None, raising=False)

    with TestClient(app) as client:
        response = client.get("/stats")

    assert response.status_code == 200
    payload = response.json()
    knowledge_graph = payload["knowledge_graph"]
    assert knowledge_graph["requested"] is True
    assert knowledge_graph["available"] is False
    assert knowledge_graph["active"] is False
    assert knowledge_graph["status"] == "unavailable"
    assert knowledge_graph["reason"] == "graphify_not_installed"
    assert knowledge_graph["interceptor_registered"] is False


def test_requested_knowledge_graph_fails_with_install_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit graph request must not silently leave the proxy inactive."""
    pytest.importorskip("fastapi")
    import cutctx.graph.graphify as graphify
    from cutctx.proxy.server import CutctxProxy, ProxyConfig

    monkeypatch.setattr(graphify, "graphify_available", lambda: False)
    monkeypatch.setattr(graphify, "networkx_available", lambda: True)

    with pytest.raises(RuntimeError, match=r"graphify.*cutctx-ai\[knowledge-graph\]"):
        CutctxProxy(
            ProxyConfig(
                optimize=False,
                cache_enabled=False,
                rate_limit_enabled=False,
                cost_tracking_enabled=False,
                log_requests=False,
                ccr_inject_tool=False,
                ccr_handle_responses=False,
                ccr_context_tracking=False,
                knowledge_graph_enabled=True,
            )
        )


def test_stats_do_not_claim_active_graph_without_live_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import cutctx.proxy.server as server
    from cutctx.proxy.server import ProxyConfig, create_app

    monkeypatch.setattr(
        server,
        "get_compression_store",
        lambda **kwargs: _StatsStub({}),
    )
    monkeypatch.setattr(
        server,
        "get_telemetry_collector",
        lambda **kwargs: _StatsStub({}),
    )
    monkeypatch.setattr(
        server,
        "get_compression_feedback",
        lambda **kwargs: _StatsStub({}),
    )
    monkeypatch.setattr(server, "_get_context_tool_stats", lambda: None)
    monkeypatch.setattr(server, "get_toin", lambda: _ToinStub())

    app = create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            log_requests=False,
            ccr_inject_tool=False,
            ccr_handle_responses=False,
            ccr_context_tracking=False,
        )
    )

    app.state.proxy.knowledge_graph_status = {
        "requested": True,
        "enabled": True,
        "available": True,
        "active": True,
        "status": "building",
        "reason": None,
        "interceptor_registered": True,
        "version": "test-v1",
    }

    with TestClient(app) as client:
        response = client.get("/stats")

    assert response.status_code == 200
    payload = response.json()
    knowledge_graph = payload["knowledge_graph"]
    assert knowledge_graph["requested"] is True
    assert knowledge_graph["available"] is True
    assert knowledge_graph["active"] is False
    assert knowledge_graph["status"] == "building"
    assert knowledge_graph["interceptor_registered"] is True
    assert knowledge_graph["version"] == "test-v1"

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


def test_stats_do_not_claim_active_graph_without_live_index(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_stats_surface_truthful_llmlingua_status_when_runtime_module_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import cutctx.proxy.server as server
    from cutctx.proxy.server import ProxyConfig, create_app

    original_find_spec = server.importlib.util.find_spec

    def fake_find_spec(name: str):  # type: ignore[no-untyped-def]
        if name == "llmlingua":
            return object()
        if name == "cutctx.transforms.llmlingua_compressor":
            return None
        return original_find_spec(name)

    monkeypatch.setattr(server.importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(server, "get_compression_store", lambda **kwargs: _StatsStub({}))
    monkeypatch.setattr(server, "get_telemetry_collector", lambda **kwargs: _StatsStub({}))
    monkeypatch.setattr(server, "get_compression_feedback", lambda **kwargs: _StatsStub({}))
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
    app.state.proxy.config.use_llmlingua = True

    with TestClient(app) as client:
        response = client.get("/stats")

    assert response.status_code == 200
    payload = response.json()
    llmlingua = payload["feature_availability"]["llmlingua"]
    assert llmlingua["requested"] is True
    assert llmlingua["available"] is False
    assert llmlingua["reason"] == "text_compression_runtime_missing"

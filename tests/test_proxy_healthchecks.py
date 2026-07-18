import os
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from cutctx.proxy.server import ProxyConfig, create_app


@pytest.fixture
def client(monkeypatch):
    # Skip the live upstream connectivity probe in unit tests — tests verify
    # the check logic separately (see test_readyz_upstream_check_* below).
    monkeypatch.setenv("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
    )
    app = create_app(config)
    with TestClient(app) as test_client:
        yield test_client


def test_livez_reports_process_health(client):
    response = client.get("/livez")

    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "cutctx-proxy"
    assert data["status"] == "healthy"
    assert data["alive"] is True
    assert data["uptime_seconds"] >= 0


def test_readyz_reports_core_subsystem_checks(client):
    response = client.get("/readyz")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["status"] == "healthy"
    assert "config" not in data
    assert data["checks"]["startup"]["status"] == "healthy"
    assert data["checks"]["http_client"]["status"] == "healthy"
    assert data["checks"]["cache"]["status"] == "disabled"
    assert data["checks"]["rate_limiter"]["status"] == "disabled"
    assert data["checks"]["memory"]["status"] == "disabled"
    runtime = data["runtime"]
    assert runtime["anthropic_pre_upstream"]["resolved_concurrency"] == max(
        2, min(8, os.cpu_count() or 4)
    )
    assert runtime["anthropic_pre_upstream"]["source"] == "auto"
    assert runtime["anthropic_pre_upstream"]["acquire_timeout_seconds"] == 15.0
    assert runtime["anthropic_pre_upstream"]["compression_timeout_seconds"] == 30.0
    assert runtime["anthropic_pre_upstream"]["memory_context_timeout_seconds"] == 2.0
    assert runtime["anthropic_pre_upstream"]["codex_ws_gated"] is False
    assert runtime["websocket_sessions"]["active_sessions"] == 0
    assert runtime["websocket_sessions"]["active_relay_tasks"] == 0


def test_health_does_not_leak_config_to_unauthenticated_callers(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["ready"] is True
    assert "config" not in data
    assert "url" not in data["checks"]["upstream"]
    assert "error" not in data["checks"]["upstream"]


def test_health_config_preserves_backwards_compatible_config_payload(client):
    response = client.get("/health/config")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["ready"] is True
    config = data["config"]
    assert config["backend"] == "anthropic"
    assert config["optimize"] is False
    assert config["cache"] is False
    assert config["rate_limit"] is False
    assert config["compression_mode"] == "safe"
    assert config["memory"] is False
    assert config["learn"] is False
    assert config["code_graph"] is False
    assert config["savings_profile"] is None
    assert config["target_ratio"] is None
    assert config["max_items_after_crush"] == 50
    assert config["smart_crusher_with_compaction"] is None
    assert isinstance(config["pid"], int)
    assert "url" in data["checks"]["upstream"]
    assert "error" in data["checks"]["upstream"]


def test_health_reports_agent_savings_config():
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        savings_profile="agent-90",
        target_ratio=0.10,
        compress_user_messages=True,
        compress_system_messages=True,
        protect_recent=2,
        protect_analysis_context=True,
        min_tokens_to_crush=120,
        max_items_after_crush=8,
        smart_crusher_with_compaction=False,
        accuracy_guard="strict",
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.get("/health/config")

    assert response.status_code == 200
    reported = response.json()["config"]
    assert reported["savings_profile"] == "agent-90"
    assert reported["target_ratio"] == 0.10
    assert reported["compress_user_messages"] is True
    assert reported["compress_system_messages"] is True
    assert reported["protect_recent"] == 2
    assert reported["protect_analysis_context"] is True
    assert reported["min_tokens_to_crush"] == 120
    assert reported["max_items_after_crush"] == 8
    assert reported["smart_crusher_with_compaction"] is False
    assert reported["accuracy_guard"] == "strict"


def test_health_reports_explicit_compression_policy():
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        compression_mode="aggressive",
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.get("/health/config")

    assert response.status_code == 200
    assert response.json()["config"]["compression_mode"] == "aggressive"


def test_health_includes_deployment_metadata_when_present(monkeypatch):
    monkeypatch.setenv("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
    monkeypatch.setenv("CUTCTX_DEPLOYMENT_PROFILE", "default")
    monkeypatch.setenv("CUTCTX_DEPLOYMENT_PRESET", "persistent-service")
    monkeypatch.setenv("CUTCTX_DEPLOYMENT_RUNTIME", "python")
    monkeypatch.setenv("CUTCTX_DEPLOYMENT_SUPERVISOR", "service")
    monkeypatch.setenv("CUTCTX_DEPLOYMENT_SCOPE", "user")

    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["deployment"] == {
        "profile": "default",
        "preset": "persistent-service",
        "runtime": "python",
        "supervisor": "service",
        "scope": "user",
    }


def test_health_returns_503_when_proxy_is_not_ready(client):
    client.app.state.ready = False

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["ready"] is False


def test_readyz_reports_memory_backend_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        memory_enabled=True,
        memory_backend="local",
        memory_db_path=str(tmp_path / "cutctx_memory.db"),
        memory_inject_tools=True,
        memory_inject_context=True,
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    data = response.json()
    assert data["checks"]["memory"]["status"] == "healthy"
    assert data["checks"]["memory"]["backend"] == "local"
    assert data["checks"]["memory"]["initialized"] is True


def test_readyz_initializes_qdrant_memory_backend(monkeypatch):
    monkeypatch.setenv("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
    from cutctx.memory.backends import direct_mem0

    init_calls: list[str] = []

    class FakeDirectMem0Adapter:
        def __init__(self, config):
            self.config = config

        async def ensure_initialized(self):
            init_calls.append("initialized")

    monkeypatch.setattr(direct_mem0, "DirectMem0Adapter", FakeDirectMem0Adapter)

    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        memory_enabled=True,
        memory_backend="qdrant-neo4j",
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    data = response.json()
    assert init_calls == ["initialized"]
    assert data["checks"]["memory"]["status"] == "healthy"
    assert data["checks"]["memory"]["backend"] == "qdrant-neo4j"
    assert data["checks"]["memory"]["initialized"] is True


def test_shutdown_tolerates_stubbed_memory_handler(monkeypatch):
    monkeypatch.setenv("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
    )
    app = create_app(config)

    with TestClient(app) as client:
        client.app.state.proxy.memory_handler = SimpleNamespace(
            health_status=lambda: {
                "enabled": False,
                "backend": None,
                "initialized": False,
                "native_tool": False,
                "bridge_enabled": False,
            }
        )
        response = client.get("/health")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Upstream connectivity check tests
# ---------------------------------------------------------------------------


def test_readyz_upstream_check_disabled_by_env_var(monkeypatch):
    """CUTCTX_SKIP_UPSTREAM_CHECK=1 suppresses the probe and reports ready."""
    monkeypatch.setenv("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
    )
    app = create_app(config)

    with TestClient(app) as test_client:
        response = test_client.get("/readyz")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    # When the check is skipped the component is reported as "disabled"
    assert data["checks"]["upstream"]["enabled"] is False
    assert data["checks"]["upstream"]["ready"] is True


def test_readyz_upstream_check_failure_returns_503(monkeypatch):
    """A failed upstream probe makes /readyz return HTTP 503."""
    from unittest.mock import AsyncMock, patch

    import httpx

    monkeypatch.delenv("CUTCTX_SKIP_UPSTREAM_CHECK", raising=False)

    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
    )
    app = create_app(config)

    # Patch the proxy's shared http_client.head so the probe uses the same
    # client as real traffic (which also means TLS/CA config is consistent).
    with TestClient(app) as test_client:
        with patch.object(
            test_client.app.state.proxy.http_client,
            "head",
            new=AsyncMock(side_effect=httpx.ConnectError("connection refused (test)")),
        ):
            response = test_client.get("/readyz")

    assert response.status_code == 503
    data = response.json()
    assert data["ready"] is False
    assert data["checks"]["upstream"]["ready"] is False
    assert "error" not in data["checks"]["upstream"]


def test_health_includes_upstream_check_result(monkeypatch):
    """/health exposes the upstream check result alongside health status."""
    monkeypatch.setenv("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
    )
    app = create_app(config)

    with TestClient(app) as test_client:
        response = test_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "upstream" in data["checks"]
    upstream = data["checks"]["upstream"]
    assert "enabled" in upstream
    assert "ready" in upstream
    assert "status" in upstream


def test_health_upstream_success_is_cached_within_ttl(monkeypatch):
    """A successful upstream probe must be cached: /health previously
    re-probed the provider on every poll (expires_at was never set on the
    success path) while failures were pinned for the full TTL — producing
    flapping 503s that read as proxy outages to monitors and k8s probes."""
    monkeypatch.delenv("CUTCTX_SKIP_UPSTREAM_CHECK", raising=False)
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
    )
    app = create_app(config)

    with TestClient(app) as test_client:
        proxy = app.state.proxy
        calls = {"head": 0}

        class _StubResponse:
            status_code = 200

        class _StubClient:
            async def head(self, url, timeout=None):
                calls["head"] += 1
                return _StubResponse()

            async def aclose(self):
                return None

        proxy.http_client = _StubClient()

        for _ in range(3):
            response = test_client.get("/health")
            assert response.status_code == 200

        assert calls["head"] == 1, "successful upstream probe must be cached for the TTL"


def test_health_upstream_failure_is_reported_and_cached(monkeypatch):
    monkeypatch.delenv("CUTCTX_SKIP_UPSTREAM_CHECK", raising=False)
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
    )
    app = create_app(config)

    with TestClient(app) as test_client:
        proxy = app.state.proxy
        calls = {"head": 0}

        class _FailingClient:
            async def head(self, url, timeout=None):
                calls["head"] += 1
                raise RuntimeError("connection reset")

            async def aclose(self):
                return None

        proxy.http_client = _FailingClient()

        first = test_client.get("/health")
        second = test_client.get("/health")

        assert first.status_code == 503
        assert second.status_code == 503
        assert calls["head"] == 1, "failed probe must also be cached (short retry TTL)"


def test_security_headers_present_on_responses(client):
    """Hardening headers must be present so a network-facing dashboard is
    not clickjackable / MIME-sniffable, and the server framework is not
    advertised. Applies to every response via middleware."""
    resp = client.get("/livez")
    h = resp.headers
    assert h.get("x-content-type-options") == "nosniff"
    assert h.get("x-frame-options") == "DENY"
    assert "no-referrer" in (h.get("referrer-policy") or "")
    csp = h.get("content-security-policy") or ""
    assert "frame-ancestors 'none'" in csp
    assert "default-src 'self'" in csp
    # Framework fingerprint must not be advertised.
    assert (h.get("server") or "").lower() != "uvicorn"

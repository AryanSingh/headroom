from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def _base_config() -> ProxyConfig:
    config = ProxyConfig()
    config.admin_api_key = "test_admin"
    config.optimize = False
    config.cache_enabled = False
    config.rate_limit_enabled = False
    config.cost_tracking_enabled = False
    return config


def test_stats_reset_allows_authenticated_non_loopback_client() -> None:
    app = create_app(_base_config())

    with TestClient(app, client=("10.0.0.5", 50000)) as client:
        response = client.post(
            "/stats/reset",
            headers={"X-Cutctx-Admin-Key": "test_admin"},
        )

    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True, "status": "reset"}


def test_stats_reset_warns_when_audit_logging_fails(monkeypatch, caplog) -> None:
    class FailingAuditLogger:
        async def async_log(self, _event) -> None:
            raise RuntimeError("audit offline")

    caplog.set_level(logging.WARNING, logger="cutctx.proxy")

    app = create_app(_base_config())
    app.state.proxy.audit_logger = FailingAuditLogger()

    with TestClient(app) as client:
        response = client.post(
            "/stats/reset",
            headers={"X-Cutctx-Admin-Key": "test_admin"},
        )

    assert response.status_code == 200, response.text
    assert any("Failed to audit stats reset" in rec.getMessage() for rec in caplog.records), (
        f"expected audit failure warning, got: {[r.getMessage() for r in caplog.records]}"
    )


def test_cors_wildcard_disables_credentials_header() -> None:
    config = _base_config()
    config.cors_origins = ["*"]
    app = create_app(config)

    with TestClient(app) as client:
        response = client.options(
            "/v1/messages",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200, response.text
    assert response.headers.get("access-control-allow-origin") == "*"
    assert response.headers.get("access-control-allow-credentials") is None


def test_cors_explicit_allowlist_keeps_credentials_header() -> None:
    config = _base_config()
    config.cors_origins = ["https://app.example.com"]
    app = create_app(config)

    with TestClient(app) as client:
        response = client.options(
            "/v1/messages",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200, response.text
    assert response.headers.get("access-control-allow-origin") == "https://app.example.com"
    assert response.headers.get("access-control-allow-credentials") == "true"

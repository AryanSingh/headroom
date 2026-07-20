from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

import cutctx.proxy.agent_auth as agent_auth
from cutctx.proxy.deployment_security import (
    DeploymentSecurityError,
    require_secure_deployment,
)
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


@pytest.fixture
def separated_client() -> TestClient:
    app = create_app(
        ProxyConfig(
            host="127.0.0.1",
            admin_api_key="admin-secret",
            client_api_key="client-secret",
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
        )
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client


def test_client_key_can_compress_but_cannot_read_admin_stats(
    separated_client: TestClient,
) -> None:
    headers = {"Authorization": "Bearer client-secret"}

    compressed = separated_client.post(
        "/v1/compress",
        headers=headers,
        json={"messages": [], "model": "gpt-4o"},
    )
    stats = separated_client.get("/stats", headers=headers)

    assert compressed.status_code == 200
    assert stats.status_code == 401


def test_client_auth_rejection_has_stable_redaction_safe_payload(
    separated_client: TestClient,
) -> None:
    response = separated_client.post(
        "/v1/compress",
        headers={"Authorization": "Bearer wrong-secret"},
        json={"messages": [], "model": "gpt-4o"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "type": "client_authentication_error",
            "code": "invalid_or_expired_client_key",
            "message": "Invalid or expired Cutctx client credential.",
            "remediation": "Run `cutctx auth login --proxy-url <origin>`.",
        }
    }
    assert "wrong-secret" not in response.text
    assert "admin" not in response.text.lower()


def test_explicit_client_header_authenticates_agent_routes(
    separated_client: TestClient,
) -> None:
    response = separated_client.get(
        "/v1/auth/client/status",
        headers={"X-Cutctx-Api-Key": "client-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "valid",
        "scope": "agent",
        "expires_at": None,
    }


def test_admin_key_compatibility_on_agent_route_is_audited_once(
    separated_client: TestClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agent_auth, "_admin_compat_warning_emitted", False)
    caplog.set_level(logging.WARNING, logger="cutctx.proxy.agent_auth")
    headers = {"Authorization": "Bearer admin-secret"}

    first = separated_client.post(
        "/v1/compress",
        headers=headers,
        json={"messages": [], "model": "gpt-4o"},
    )
    second = separated_client.post(
        "/v1/compress",
        headers=headers,
        json={"messages": [], "model": "gpt-4o"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert sum(
        "deprecated_agent_admin_auth" in record.message for record in caplog.records
    ) == 1


def test_loopback_remains_open_when_no_client_key_is_configured() -> None:
    app = create_app(
        ProxyConfig(
            host="127.0.0.1",
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
        )
    )

    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(
            "/v1/compress",
            json={"messages": [], "model": "gpt-4o"},
        )

    assert response.status_code == 200


def test_tool_call_route_uses_agent_client_auth(
    separated_client: TestClient,
) -> None:
    rejected = separated_client.post(
        "/v1/retrieve/tool_call",
        json={"tool_call": {}, "provider": "anthropic"},
    )
    accepted = separated_client.post(
        "/v1/retrieve/tool_call",
        headers={"Authorization": "Bearer client-secret"},
        json={"tool_call": {}, "provider": "anthropic"},
    )

    assert rejected.status_code == 401
    assert rejected.json()["error"]["type"] == "client_authentication_error"
    assert accepted.status_code == 400


def test_non_loopback_requires_dedicated_agent_client_key() -> None:
    with pytest.raises(DeploymentSecurityError, match="client authentication"):
        require_secure_deployment(
            ProxyConfig(
                host="0.0.0.0",
                admin_api_key="admin",
                proxy_api_key="proxy",
                client_api_key=None,
            )
        )


def test_non_loopback_accepts_separate_agent_client_key() -> None:
    require_secure_deployment(
        ProxyConfig(
            host="0.0.0.0",
            admin_api_key="admin",
            proxy_api_key="proxy",
            client_api_key="client",
        )
    )

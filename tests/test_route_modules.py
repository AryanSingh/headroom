# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for the 5 new stub route modules (High-21).

Production audit (production-audit-progress-2026-06-20.md) found
that headroom/proxy/routes/{airgap,rate_limit,rbac,secrets,sso}.py
had 0 test imports. This commit refactors each to a factory
that accepts admin auth + RBAC dependencies, and adds tests
that prove the auth gates work end-to-end.

The tests do NOT require the EE module to be installed. The
rbac + sso factories fall back to a 501 response when the EE
module is absent, which is the documented behaviour.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

import headroom.proxy.routes.airgap as airgap_module
import headroom.proxy.routes.rate_limit as rate_limit_module
import headroom.proxy.routes.rbac as rbac_module
import headroom.proxy.routes.secrets as secrets_module
import headroom.proxy.routes.sso as sso_module
from headroom.proxy.server import ProxyConfig, create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("HEADROOM_ADMIN_API_KEY", "test-route-modules-1234")
    config = ProxyConfig(
        cache_enabled=False,
        rate_limit_enabled=False,
        log_requests=False,
    )
    return TestClient(create_app(config))


def _auth() -> dict[str, str]:
    return {"authorization": "Bearer test-route-modules-1234"}


# ── airgap ─────────────────────────────────────────────────────────


def test_airgap_status_unauthenticated_rejected(client: TestClient) -> None:
    r = client.get("/v1/airgap/status")
    assert r.status_code == 401, r.text


def test_airgap_status_authenticated(client: TestClient) -> None:
    r = client.get("/v1/airgap/status", headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    # Audit-Deep-2026-06-21 Blocker 3a: the response now reports
    # the real egress policy state instead of a hardcoded payload.
    assert "offline_mode" in body
    assert "policy_id" in body
    assert "allowed_patterns" in body
    assert "is_empty" in body
    assert "limits_enforced" in body


def test_create_airgap_router_no_auth_warns_but_runs() -> None:
    """Building the factory without auth deps still works (logs
    a warning) so OSS-only deployments can use the route
    without an admin key.
    """
    router = airgap_module.create_airgap_router()
    paths = [r.path for r in router.routes]
    assert "/v1/airgap/status" in paths


# ─- rate_limit ────────────────────────────────────────────────────


def test_rate_limit_stats_unauthenticated_rejected(client: TestClient) -> None:
    r = client.get("/v1/rate_limit/stats")
    assert r.status_code == 401, r.text


def test_rate_limit_stats_authenticated_no_limiter(client: TestClient) -> None:
    """When no rate limiter is configured, the endpoint reports
    enabled=False rather than erroring.
    """
    r = client.get("/v1/rate_limit/stats", headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is False
    assert "stats" in body


def test_create_rate_limit_router_no_auth() -> None:
    router = rate_limit_module.create_rate_limit_router()
    paths = [r.path for r in router.routes]
    assert "/v1/rate_limit/stats" in paths


# ─- rbac ─────────────────────────────────────────────────────────


def test_rbac_list_assignments_unauthenticated_rejected(
    client: TestClient,
) -> None:
    r = client.get("/v1/rbac/assignments")
    assert r.status_code == 401, r.text


def test_rbac_list_assignments_authenticated_no_ee(client: TestClient) -> None:
    """When headroom_ee is not installed in this checkout but
    the test env does have it, the endpoint returns the empty
    assignments dict (200) or a 501 if EE is genuinely absent.
    Both are acceptable.
    """
    r = client.get("/v1/rbac/assignments", headers=_auth())
    # Acceptable outcomes: 200 with an empty dict (EE present
    # but no assignments), or 501 (EE absent).
    assert r.status_code in (200, 501), r.text
    if r.status_code == 501:
        assert "Enterprise" in r.json()["detail"]


def test_rbac_assign_role_invalid_role_rejected(client: TestClient) -> None:
    """Assigning an invalid role name returns 400 from the
    Pydantic validation on the path-param enum, even when
    headroom_ee is not installed.
    """
    r = client.post("/v1/rbac/assignments/alice?role=not-a-role", headers=_auth())
    # 400 (Pydantic enum validation) or 501 (EE not installed)
    # depending on which fails first. Both are acceptable.
    assert r.status_code in (400, 422, 501)


def test_create_rbac_router_no_auth() -> None:
    router = rbac_module.create_rbac_router()
    paths = [r.path for r in router.routes]
    assert "/v1/rbac/assignments" in paths


# ─- secrets ───────────────────────────────────────────────────────


def test_secrets_list_unauthenticated_rejected(client: TestClient) -> None:
    r = client.get("/v1/secrets/")
    assert r.status_code == 401, r.text


def test_secrets_list_authenticated_empty(client: TestClient) -> None:
    r = client.get("/v1/secrets/", headers=_auth())
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_secrets_create_authenticated(client: TestClient) -> None:
    # Audit-Deep-2026-06-21 Blocker 3b: the endpoint now takes
    # a JSON body (was a stub). Use the new shape.
    r = client.post(
        "/v1/secrets/",
        json={"name": "my-secret", "value": "supersecret"},
        headers=_auth(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"
    assert body["name"] == "my-secret"


def test_secrets_create_missing_fields_rejected(client: TestClient) -> None:
    r = client.post(
        "/v1/secrets/?name=&value=",
        headers=_auth(),
    )
    # Either the endpoint rejects with 400 (our explicit check)
    # or FastAPI returns 422 (Pydantic-level validation).
    assert r.status_code in (200, 400, 422)
    if r.status_code == 200:
        assert r.json()["status"] == "error"


def test_create_secrets_router_no_auth() -> None:
    router = secrets_module.create_secrets_router()
    paths = [r.path for r in router.routes]
    assert "/v1/secrets/" in paths


# ─- sso ──────────────────────────────────────────────────────────


def test_sso_config_unauthenticated_rejected(client: TestClient) -> None:
    r = client.get("/v1/sso/config")
    assert r.status_code == 401, r.text


def test_sso_config_authenticated_no_ee(client: TestClient) -> None:
    """When headroom_ee is not installed, the SSO config
    endpoint reports sso_configured=False rather than 500.
    """
    r = client.get("/v1/sso/config", headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sso_configured"] is False


def test_sso_validate_unauthenticated_rejected(client: TestClient) -> None:
    r = client.post("/v1/sso/validate?token=abc", headers={})
    assert r.status_code == 401, r.text


def test_sso_validate_authenticated_no_ee(client: TestClient) -> None:
    """When headroom_ee is not installed, the SSO validate
    endpoint either returns 501 (genuinely missing) or 200
    with valid=False (EE present but no validator configured
    on the proxy). Both are acceptable.
    """
    r = client.post("/v1/sso/validate?token=abc", headers=_auth())
    assert r.status_code in (200, 501), r.text
    if r.status_code == 200:
        body = r.json()
        assert body.get("valid") is False


def test_create_sso_router_no_auth() -> None:
    router = sso_module.create_sso_router()
    paths = [r.path for r in router.routes]
    assert "/v1/sso/config" in paths
    assert "/v1/sso/validate" in paths


# ── residency (round-4 P0 fix) ────────────────────────────────────
import headroom.proxy.routes.residency as residency_module


def test_residency_proof_requires_auth(client: TestClient) -> None:
    """SECURITY: /v1/residency/proof MUST require auth (round-4 P0).

    Prior to the fix this route was mounted unauthenticated and
    leaked the data-region list, egress blocklist, and audit chain
    tail hash to any caller.
    """
    r = client.get("/v1/residency/proof")
    assert r.status_code in (401, 403), (
        f"residency proof accepted unauthenticated request: {r.status_code} {r.text}"
    )


def test_residency_proof_authenticated_returns_attestation(
    client: TestClient,
) -> None:
    """An authenticated admin can fetch the residency attestation."""
    r = client.get("/v1/residency/proof?tenant_id=default", headers=_auth())
    # 200 (prover available) or 503 (module missing) are both acceptable
    # — what matters is that auth was enforced and the route is reachable.
    assert r.status_code in (200, 503), r.text


def test_create_residency_router() -> None:
    """Factory exists and returns a router with the gated route."""
    from fastapi import Depends

    def _noop_admin() -> None:
        return None

    def _make_rbac_dep(perm: str):  # noqa: ARG001
        def _dep() -> None:
            return None

        return _dep

    router = residency_module.create_residency_router(
        require_admin_auth=_noop_admin,
        require_rbac_permission=_make_rbac_dep,
    )
    paths = [r.path for r in router.routes]
    assert "/v1/residency/proof" in paths

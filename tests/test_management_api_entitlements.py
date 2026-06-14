from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from headroom.audit import reset_audit_logger
from headroom.fleet import reset_fleet_store
from headroom.org import reset_org_store
from headroom.proxy.server import ProxyConfig, create_app
from headroom.rbac import reset_rbac_checker
from headroom.scim import reset_scim_store
from headroom.sso import SsoClaims, SsoConfig, SsoTokenInvalidError, SsoValidator


def _make_client(tmp_path, *, tier: str) -> TestClient:
    reset_audit_logger()
    reset_fleet_store()
    reset_org_store()
    reset_rbac_checker()
    reset_scim_store()
    config = ProxyConfig(
        admin_api_key="secret",
        entitlement_tier=tier,
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        audit_db_path=str(tmp_path / f"audit-{tier}.db"),
        fleet_db_path=str(tmp_path / f"fleet-{tier}.db"),
        org_db_path=str(tmp_path / f"org-{tier}.db"),
        scim_db_path=str(tmp_path / f"scim-{tier}.db"),
    )
    return TestClient(create_app(config))


def test_team_can_access_team_analytics_but_not_business_or_enterprise_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("HEADROOM_TELEMETRY", "off")
    with _make_client(tmp_path, tier="team") as client:
        headers = {"X-Headroom-Admin-Key": "secret"}

        dashboard = client.get("/analytics/dashboard", headers=headers)
        assert dashboard.status_code == 200

        reports = client.get("/reports/savings", headers=headers)
        assert reports.status_code == 200

        orgs = client.get("/orgs", headers=headers)
        assert orgs.status_code == 403
        assert orgs.json()["detail"]["feature"] == "workspace_model"

        audit = client.get("/audit/events", headers=headers)
        assert audit.status_code == 403
        assert audit.json()["detail"]["feature"] == "audit_logs"


def test_business_can_access_org_and_project_routes_but_not_enterprise_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("HEADROOM_TELEMETRY", "off")
    with _make_client(tmp_path, tier="business") as client:
        headers = {"X-Headroom-Admin-Key": "secret"}

        orgs = client.get("/orgs", headers=headers)
        assert orgs.status_code == 200
        assert orgs.json() == {"orgs": []}

        projects = client.get("/analytics/projects", headers=headers)
        assert projects.status_code == 200

        retention = client.get("/retention/stats", headers=headers)
        assert retention.status_code == 403
        assert retention.json()["detail"]["feature"] == "retention_controls"

        rbac = client.get("/rbac/roles", headers=headers)
        assert rbac.status_code == 403
        assert rbac.json()["detail"]["feature"] == "rbac"

        fleet = client.get("/fleet/summary", headers=headers)
        assert fleet.status_code == 403
        assert fleet.json()["detail"]["feature"] == "fleet_management"

        scim = client.get("/scim/v2/Users", headers=headers)
        assert scim.status_code == 403
        assert scim.json()["detail"]["feature"] == "scim"


def test_enterprise_can_access_enterprise_management_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("HEADROOM_TELEMETRY", "off")
    with _make_client(tmp_path, tier="enterprise") as client:
        headers = {"X-Headroom-Admin-Key": "secret"}

        audit = client.get("/audit/events", headers=headers)
        assert audit.status_code == 200
        assert "events" in audit.json()

        retention = client.get("/retention/stats", headers=headers)
        assert retention.status_code == 200
        assert "retention" in retention.json()

        rbac = client.get("/rbac/roles", headers=headers)
        assert rbac.status_code == 200
        assert rbac.json() == {"assignments": {}}

        heartbeat = client.post(
            "/fleet/deployments/heartbeat",
            headers=headers,
            json={"name": "prod-us-east", "status": "healthy", "environment": "prod"},
        )
        assert heartbeat.status_code == 201
        deployment_id = heartbeat.json()["deployment"]["deployment_id"]

        summary = client.get("/fleet/summary", headers=headers)
        assert summary.status_code == 200
        assert summary.json()["summary"]["total"] == 1

        user = client.post(
            "/scim/v2/Users",
            headers=headers,
            json={"userName": "alice@example.com", "displayName": "Alice"},
        )
        assert user.status_code == 201
        user_id = user.json()["id"]

        fetched = client.get(f"/scim/v2/Users/{user_id}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["userName"] == "alice@example.com"

        delete_deployment = client.delete(
            f"/fleet/deployments/{deployment_id}",
            headers=headers,
        )
        assert delete_deployment.status_code == 200


def test_license_status_remains_available_with_admin_auth_across_tiers(tmp_path, monkeypatch):
    monkeypatch.setenv("HEADROOM_TELEMETRY", "off")
    with _make_client(tmp_path, tier="builder") as client:
        response = client.get("/license-status", headers={"X-Headroom-Admin-Key": "secret"})
        assert response.status_code == 200
        body = response.json()
        assert body["has_license_key"] is False
        assert body["status"] == "no_license"


def test_sso_config_can_be_built_from_proxy_config() -> None:
    config = ProxyConfig(
        sso_provider_type="jwt",
        sso_jwks_uri="https://idp.example.com/jwks.json",
        sso_issuer="https://idp.example.com",
        sso_audience="headroom-api",
        sso_role_mapping={"groups:value=platform-admin": "admin"},
        sso_default_role="operator",
    )

    sso = SsoConfig.from_proxy_config(config)

    assert sso.provider_type == "jwt"
    assert sso.jwks_uri == "https://idp.example.com/jwks.json"
    assert sso.issuer == "https://idp.example.com"
    assert sso.audience == "headroom-api"
    assert sso.role_mapping == {"groups:value=platform-admin": "admin"}
    assert sso.default_role == "operator"
    assert sso.enabled is True


@pytest.mark.no_auto_admin
def test_sso_can_secure_admin_routes_without_admin_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("HEADROOM_TELEMETRY", "off")
    monkeypatch.delenv("HEADROOM_ADMIN_API_KEY", raising=False)
    reset_audit_logger()
    reset_fleet_store()
    reset_org_store()
    reset_rbac_checker()
    reset_scim_store()
    config = ProxyConfig(
        admin_api_key=None,
        entitlement_tier="enterprise",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        audit_db_path=str(tmp_path / "audit-sso.db"),
        org_db_path=str(tmp_path / "org-sso.db"),
        fleet_db_path=str(tmp_path / "fleet-sso.db"),
        scim_db_path=str(tmp_path / "scim-sso.db"),
        sso_provider_type="jwt",
        sso_jwks_uri="https://idp.example.com/jwks.json",
        sso_issuer="https://idp.example.com",
        sso_audience="headroom-api",
        sso_default_role="viewer",
    )

    async def _valid_claims(self, token: str) -> SsoClaims:
        if token != "valid-sso-token":
            raise SsoTokenInvalidError("bad token")
        return SsoClaims(
            subject="admin@example.com",
            issuer="https://idp.example.com",
            audience="headroom-api",
            role="admin",
        )

    with patch.object(SsoValidator, "validate_token", _valid_claims):
        with TestClient(create_app(config)) as client:
            missing = client.get("/license-status")
            assert missing.status_code == 401

            valid = client.get(
                "/license-status",
                headers={"Authorization": "Bearer valid-sso-token"},
            )
            assert valid.status_code == 200
            assert valid.json()["status"] == "no_license"

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cutctx.audit import reset_audit_logger
from cutctx.fleet import reset_fleet_store
from cutctx.org import reset_org_store
from cutctx.proxy.server import ProxyConfig, _apply_validated_license, create_app
from cutctx.rbac import reset_rbac_checker
from cutctx.retention import get_retention_manager, reset_retention_manager
from cutctx.scim import reset_scim_store
from cutctx.sso import SsoClaims, SsoConfig, SsoTokenInvalidError, SsoValidator
from cutctx.telemetry.reporter import LicenseInfo


def _make_client(tmp_path, monkeypatch, *, tier: str) -> TestClient:
    reset_audit_logger()
    reset_fleet_store()
    reset_org_store()
    reset_rbac_checker()
    reset_scim_store()
    monkeypatch.setenv("CUTCTX_RBAC_DB_PATH", str(tmp_path / f"rbac-{tier}.db"))
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
    app = create_app(config)
    if tier and tier != "builder":
        _apply_validated_license(app.state.proxy, LicenseInfo(status="active", plan=tier))
    return TestClient(app)


def test_team_can_access_team_analytics_but_not_business_or_enterprise_routes(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    with _make_client(tmp_path, monkeypatch, tier="team") as client:
        headers = {"X-Cutctx-Admin-Key": "secret"}

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


def test_proxy_lifecycle_starts_and_stops_retention_manager(tmp_path, monkeypatch):
    """Configured retention must run periodically, not only on admin demand."""
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    reset_retention_manager()
    manager = get_retention_manager()

    try:
        with _make_client(tmp_path, monkeypatch, tier="enterprise") as client:
            assert client.app.state.retention_manager is manager
            assert manager._running is True

        assert manager._running is False
    finally:
        reset_retention_manager()


def test_health_exposes_enterprise_component_initialization_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    monkeypatch.setenv("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
    reset_audit_logger()
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("block child creation", encoding="utf-8")
    config = ProxyConfig(
        admin_api_key="secret",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        audit_db_path=str(blocking_file / "audit.db"),
        org_db_path=str(tmp_path / "org-health.db"),
        fleet_db_path=str(tmp_path / "fleet-health.db"),
        scim_db_path=str(tmp_path / "scim-health.db"),
    )

    with TestClient(create_app(config)) as client:
        response = client.get("/health")

    assert response.status_code == 503
    initialization = response.json()["checks"]["component_initialization"]
    assert initialization["status"] == "unhealthy"
    assert "audit" in initialization["errors"]


def test_business_can_access_org_and_project_routes_but_not_enterprise_controls(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    with _make_client(tmp_path, monkeypatch, tier="business") as client:
        headers = {"X-Cutctx-Admin-Key": "secret"}

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
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    with _make_client(tmp_path, monkeypatch, tier="enterprise") as client:
        headers = {"X-Cutctx-Admin-Key": "secret"}

        audit = client.get("/audit/events", headers=headers)
        assert audit.status_code == 200
        assert "events" in audit.json()

        retention = client.get("/retention/stats", headers=headers)
        assert retention.status_code == 200
        assert "retention" in retention.json()

        rbac = client.get("/rbac/roles", headers=headers)
        assert rbac.status_code == 200
        assert rbac.json() == {"assignments": {}}

        firewall = client.get("/firewall/status", headers=headers)
        assert firewall.status_code == 200
        firewall_payload = firewall.json()
        assert "patterns_loaded" in firewall_payload
        assert firewall_payload["telemetry_available"] is False

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


def test_unset_entitlement_tier_defaults_to_builder_not_enterprise(tmp_path, monkeypatch):
    """Regression test: an unconfigured entitlement_tier must fail closed
    (builder) rather than fail open (enterprise) for admin-gated enterprise
    routes. _runtime_require_entitlement previously re-derived the tier from
    raw config.entitlement_tier with a fail-open "enterprise" default,
    unconditionally granting audit/rbac/fleet/scim access to any deployment
    that never configured a license or entitlement tier.
    """
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    with _make_client(tmp_path, monkeypatch, tier=None) as client:
        headers = {"X-Cutctx-Admin-Key": "secret"}

        audit = client.get("/audit/events", headers=headers)
        assert audit.status_code == 403
        assert audit.json()["detail"]["feature"] == "audit_logs"
        assert audit.json()["detail"]["current_tier"] == "builder"

        rbac = client.get("/rbac/roles", headers=headers)
        assert rbac.status_code == 403
        assert rbac.json()["detail"]["feature"] == "rbac"

        fleet = client.get("/fleet/summary", headers=headers)
        assert fleet.status_code == 403
        assert fleet.json()["detail"]["feature"] == "fleet_management"

        scim = client.get("/scim/v2/Users", headers=headers)
        assert scim.status_code == 403
        assert scim.json()["detail"]["feature"] == "scim"


def test_builder_cannot_toggle_entitlement_gated_governance_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    with _make_client(tmp_path, monkeypatch, tier="builder") as client:
        headers = {"X-Cutctx-Admin-Key": "secret"}

        episodic = client.post(
            "/config/flags",
            headers=headers,
            json={"episodic_memory_enabled": True},
        )
        assert episodic.status_code == 403
        assert episodic.json()["detail"]["feature"] == "episodic_memory"

        shared = client.post(
            "/config/flags",
            headers=headers,
            json={"shared_context_enabled": True},
        )
        assert shared.status_code == 403
        assert shared.json()["detail"]["feature"] == "cross_agent_memory"

        audit = client.post(
            "/config/flags",
            headers=headers,
            json={"audit_enabled": False},
        )
        assert audit.status_code == 403
        assert audit.json()["detail"]["feature"] == "audit_logs"


def test_license_status_remains_available_with_admin_auth_across_tiers(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    with _make_client(tmp_path, monkeypatch, tier="builder") as client:
        response = client.get("/license-status", headers={"X-Cutctx-Admin-Key": "secret"})
        assert response.status_code == 200
        body = response.json()
        assert body["has_license_key"] is False
        assert body["status"] == "no_license"


def test_sso_config_can_be_built_from_proxy_config() -> None:
    config = ProxyConfig(
        sso_provider_type="jwt",
        sso_jwks_uri="https://idp.example.com/jwks.json",
        sso_issuer="https://idp.example.com",
        sso_audience="cutctx-api",
        sso_role_mapping={"groups:value=platform-admin": "admin"},
        sso_default_role="operator",
    )

    sso = SsoConfig.from_proxy_config(config)

    assert sso.provider_type == "jwt"
    assert sso.jwks_uri == "https://idp.example.com/jwks.json"
    assert sso.issuer == "https://idp.example.com"
    assert sso.audience == "cutctx-api"
    assert sso.role_mapping == {"groups:value=platform-admin": "admin"}
    assert sso.default_role == "operator"
    assert sso.enabled is True


def test_failed_admin_authentication_is_rate_limited_by_client(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    config = ProxyConfig(
        admin_api_key="secret",
        admin_auth_failures_per_minute=2,
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        audit_db_path=str(tmp_path / "audit-rate-limit.db"),
        org_db_path=str(tmp_path / "org-rate-limit.db"),
        fleet_db_path=str(tmp_path / "fleet-rate-limit.db"),
        scim_db_path=str(tmp_path / "scim-rate-limit.db"),
    )

    with TestClient(create_app(config)) as client:
        assert client.get("/license-status").status_code == 401
        assert client.get("/license-status").status_code == 401
        blocked = client.get("/license-status")
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) >= 1

        # A valid credential is never passed through the failure limiter.
        valid = client.get("/license-status", headers={"X-Cutctx-Admin-Key": "secret"})
        assert valid.status_code == 200


@pytest.mark.no_auto_admin
def test_sso_can_secure_admin_routes_without_admin_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
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
        sso_audience="cutctx-api",
        sso_default_role="viewer",
    )

    async def _valid_claims(self, token: str) -> SsoClaims:
        if token != "valid-sso-token":
            raise SsoTokenInvalidError("bad token")
        return SsoClaims(
            subject="admin@example.com",
            issuer="https://idp.example.com",
            audience="cutctx-api",
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

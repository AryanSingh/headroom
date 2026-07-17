"""Request-path entitlement enforcement for BUSINESS-tier features.

Guards the revenue-leak class from the 2026-07-17 commercial audit: paid
features must not activate on deployments whose tier (declared or licensed)
does not include them — at proxy init, via the legacy ``/config/flags``
endpoint, and after startup license validation.
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import _apply_validated_license, create_app
from cutctx.telemetry.reporter import LicenseInfo


def _config(**overrides) -> ProxyConfig:
    base = dict(
        backend="mock",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        admin_api_key="admin_12345",
    )
    base.update(overrides)
    return ProxyConfig(**base)


def test_episodic_memory_refused_at_init_without_business_tier() -> None:
    app = create_app(_config(episodic_memory_enabled=True))
    with TestClient(app):
        proxy = app.state.proxy
        assert proxy.episodic_tracker is None
        assert "episodic_memory" in proxy.component_init_errors


def test_episodic_memory_activates_with_business_tier() -> None:
    app = create_app(_config(episodic_memory_enabled=True, entitlement_tier="business"))
    with TestClient(app):
        proxy = app.state.proxy
        assert proxy.episodic_tracker is not None
        assert "episodic_memory" not in proxy.component_init_errors


import pytest


@pytest.mark.parametrize("endpoint", ["/config/flags", "/admin/config/flags"])
def test_config_flags_memory_requires_entitlement(endpoint: str) -> None:
    app = create_app(_config())
    with TestClient(app) as client:
        response = client.post(
            endpoint,
            json={"memory": True},
            headers={"x-cutctx-admin-key": "admin_12345"},
        )
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["error"] == "feature_not_available"
        assert detail["feature"] == "episodic_memory"
        assert app.state.proxy.episodic_tracker is None


@pytest.mark.parametrize("endpoint", ["/config/flags", "/admin/config/flags"])
def test_config_flags_memory_allows_entitled_tier(endpoint: str) -> None:
    app = create_app(_config(entitlement_tier="business"))
    with TestClient(app) as client:
        response = client.post(
            endpoint,
            json={"memory": True},
            headers={"x-cutctx-admin-key": "admin_12345"},
        )
        assert response.status_code == 200
        assert app.state.proxy.episodic_tracker is not None


def test_validated_license_plan_overrides_declared_tier() -> None:
    proxy = SimpleNamespace(entitlement_checker=None, episodic_tracker=None)

    _apply_validated_license(
        proxy,
        LicenseInfo(status="active", plan="business"),
    )
    assert proxy.entitlement_checker.is_entitled("episodic_memory") is True

    # Expired/invalid licenses fail closed to the free tier, even when an
    # operator declared a higher tier on the command line.
    _apply_validated_license(proxy, LicenseInfo(status="expired"))
    assert proxy.entitlement_checker.is_entitled("episodic_memory") is False
    assert proxy.entitlement_checker.is_entitled("smart_crusher") is True


def test_unvalidated_license_result_keeps_configured_checker() -> None:
    sentinel = object()
    proxy = SimpleNamespace(entitlement_checker=sentinel, episodic_tracker=None)
    _apply_validated_license(proxy, None)
    assert proxy.entitlement_checker is sentinel

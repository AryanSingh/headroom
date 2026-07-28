"""Integration tests for dynamic initialization of proxy modules."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import _apply_validated_license, create_app
from cutctx.proxy.ws_session_registry import WSSessionHandle
from cutctx.telemetry.reporter import LicenseInfo
from cutctx.transforms.content_router import ContentRouter

os.environ["CUTCTX_SKIP_INTEGRITY_CHECK"] = "1"


@pytest.fixture(autouse=True)
def _isolate_governance_desired_state(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUTCTX_CONFIG_DIR", str(tmp_path / "config"))


def test_reversible_code_live_toggle_updates_existing_routers_without_restart(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CUTCTX_CONFIG_DIR", str(tmp_path / "config"))
    config = ProxyConfig(
        admin_api_key="test_admin",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
    )
    app = create_app(config)
    proxy = app.state.proxy
    routers = [
        transform
        for pipeline in (proxy.anthropic_pipeline, proxy.openai_pipeline)
        for transform in pipeline.transforms
        if isinstance(transform, ContentRouter)
    ]
    router_ids = [id(router) for router in routers]
    pipeline_ids = (id(proxy.anthropic_pipeline), id(proxy.openai_pipeline))
    assert routers and all(router.config.enable_reversible_code for router in routers)

    with TestClient(app) as client:
        disabled = client.post(
            "/config/flags",
            json={"reversible_code": False},
            headers={"x-cutctx-admin-key": "test_admin"},
        )
        assert disabled.status_code == 200
        assert disabled.json()["applied_live"]["reversible_code"] == {
            "enabled": False,
            "routers_updated": len(set(router_ids)),
        }
        assert (
            client.get("/config/flags", headers={"x-cutctx-admin-key": "test_admin"}).json()[
                "live_toggleable"
            ]["reversible_code"]["enabled"]
            is False
        )

        enabled = client.post(
            "/config/flags",
            json={"reversible_code": True},
            headers={"x-cutctx-admin-key": "test_admin"},
        )
        assert enabled.status_code == 200
        assert (
            client.get("/config/flags", headers={"x-cutctx-admin-key": "test_admin"}).json()[
                "live_toggleable"
            ]["reversible_code"]["enabled"]
            is True
        )

    assert config.enable_reversible_code is True
    assert [id(router) for router in routers] == router_ids
    assert (id(proxy.anthropic_pipeline), id(proxy.openai_pipeline)) == pipeline_ids
    assert all(router.config.enable_reversible_code for router in routers)
    assert not (tmp_path / "config" / "feature_flags.json").exists()


def test_reversible_code_live_toggle_requires_admin_authentication() -> None:
    app = create_app(
        ProxyConfig(
            admin_api_key="test_admin",
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
        )
    )

    with TestClient(app) as client:
        response = client.post("/config/flags", json={"reversible_code": False})

    assert response.status_code == 401
    assert app.state.proxy.config.enable_reversible_code is True


def test_config_flag_boolean_rejects_string_without_mutating_or_persisting(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CUTCTX_CONFIG_DIR", str(tmp_path / "config"))
    config = ProxyConfig(
        admin_api_key="test_admin",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/config/flags",
            json={"firewall_enabled": "false"},
            headers={"x-cutctx-admin-key": "test_admin"},
        )

    assert response.status_code == 422
    assert config.firewall_enabled is False
    assert not (tmp_path / "config" / "feature_flags.json").exists()


def test_multiple_flag_update_uses_each_normalized_value() -> None:
    config = ProxyConfig(
        admin_api_key="test_admin",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/config/flags",
            json={"orchestrator_mode": "balanced", "dedup_enabled": True},
            headers={"x-cutctx-admin-key": "test_admin"},
        )

    assert response.status_code == 200
    assert response.json()["applied_live"]["orchestrator_mode"] == {"mode": "auto"}
    assert config.orchestrator_enabled is True


def test_legacy_config_flags_reports_live_rate_limit_state() -> None:
    app = create_app(
        ProxyConfig(
            admin_api_key="test_admin",
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=True,
        )
    )

    with TestClient(app) as client:
        response = client.get(
            "/admin/config/flags",
            headers={"x-cutctx-admin-key": "test_admin"},
        )

    assert response.status_code == 200
    assert response.json()["rate_limiter"] is True


def test_legacy_config_flag_boolean_rejects_string_without_mutating() -> None:
    config = ProxyConfig(
        admin_api_key="test_admin",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/admin/config/flags",
            json={"ccr": "false"},
            headers={"x-cutctx-admin-key": "test_admin"},
        )

    assert response.status_code == 422
    assert config.ccr_context_tracking is True


def test_reversible_code_live_toggle_does_not_drain_active_websocket_sessions() -> None:
    config = ProxyConfig(
        admin_api_key="test_admin",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
    )
    app = create_app(config)
    proxy = app.state.proxy
    proxy.ws_sessions.register(WSSessionHandle(session_id="live-session", request_id="req-live"))

    with TestClient(app) as client:
        response = client.post(
            "/config/flags",
            json={"reversible_code": False},
            headers={"x-cutctx-admin-key": "test_admin"},
        )

    assert response.status_code == 200
    assert proxy.ws_sessions.active_count() == 1
    assert proxy.ws_sessions.get("live-session") is not None


def test_legacy_admin_reversible_code_toggle_updates_live_router() -> None:
    config = ProxyConfig(
        admin_api_key="test_admin",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/admin/config/flags",
            json={"reversible_code": False},
            headers={"x-cutctx-admin-key": "test_admin"},
        )
        flags = client.get("/admin/config/flags", headers={"x-cutctx-admin-key": "test_admin"})

    assert response.status_code == 200
    assert response.json()["applied_live"]["reversible_code"]["enabled"] is False
    assert flags.json()["reversible_code"] is False


def test_legacy_restart_flag_persists_desired_state_without_claiming_live() -> None:
    config = ProxyConfig(
        admin_api_key="test_admin",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        firewall_enabled=False,
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/admin/config/flags",
            json={"firewall": True},
            headers={"x-cutctx-admin-key": "test_admin"},
        )
        flags = client.get(
            "/admin/config/flags",
            headers={"x-cutctx-admin-key": "test_admin"},
        )

    assert response.status_code == 200
    assert response.json()["restart_required"]["firewall_enabled"] == {
        "requested": True,
        "current": False,
        "desired": True,
    }
    assert config.firewall_enabled is False
    assert flags.json()["firewall"] is False
    assert flags.json()["desired_overrides"]["firewall_enabled"] is True


@pytest.mark.asyncio
async def test_dynamic_initialization_of_memory_module(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the canonical config route can initialize episodic memory live."""
    monkeypatch.setitem(sys.modules, "cutctx.memory.session_tracker", MagicMock())
    monkeypatch.setitem(sys.modules, "cutctx.memory.store", MagicMock())
    monkeypatch.setitem(sys.modules, "cutctx.intelligence_pipeline", MagicMock())
    monkeypatch.setenv("CUTCTX_CONFIG_DIR", str(tmp_path / "config"))

    config = ProxyConfig()
    config.episodic_memory_enabled = False
    config.firewall_enabled = False
    config.admin_api_key = "test_admin"
    config.entitlement_tier = "business"

    app = create_app(config)
    proxy = app.state.proxy
    assert getattr(proxy, "episodic_tracker", None) is None
    _apply_validated_license(proxy, LicenseInfo(status="active", plan="business"))

    with TestClient(app) as client:
        flags_before = client.get(
            "/config/flags",
            headers={"x-cutctx-admin-key": "test_admin"},
        )
        assert flags_before.status_code == 200
        assert flags_before.json()["legacy_aliases"]["memory"] == "episodic_memory_enabled"

        response = client.post(
            "/config/flags",
            json={"memory": True, "firewall": True},
            headers={"x-cutctx-admin-key": "test_admin"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["applied_live"]["episodic_memory_enabled"]["enabled"] is True
        assert payload["applied_live"]["memory"]["normalized_to"] == "episodic_memory_enabled"
        assert payload["restart_required"]["firewall_enabled"]["requested"] is True
        assert payload["restart_required"]["firewall_enabled"]["current"] is False
        assert payload["restart_required"]["firewall_enabled"]["desired"] is True

        flags_after = client.get(
            "/config/flags",
            headers={"x-cutctx-admin-key": "test_admin"},
        ).json()
        assert flags_after["restart_required"]["firewall_enabled"]["enabled"] is False
        assert flags_after["restart_required"]["firewall_enabled"]["desired"] is True

    assert proxy.config.episodic_memory_enabled is True
    assert proxy.episodic_tracker is not None
    assert proxy.config.firewall_enabled is False


def test_business_tier_can_enable_episodic_memory_live_without_mocks(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the shipped config route enables the real tracker for entitled tiers."""
    monkeypatch.setenv("CUTCTX_SKIP_INTEGRITY_CHECK", "1")
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    monkeypatch.setenv("CUTCTX_EPISODIC_MEMORY_DIR", str(tmp_path / "episodic-memory"))

    config = ProxyConfig(
        admin_api_key="test_admin",
        entitlement_tier="business",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        episodic_memory_enabled=False,
    )

    app = create_app(config)
    proxy = app.state.proxy
    assert getattr(proxy, "episodic_tracker", None) is None
    _apply_validated_license(proxy, LicenseInfo(status="active", plan="business"))

    with TestClient(app) as client:
        response = client.post(
            "/config/flags",
            json={"memory": True},
            headers={"x-cutctx-admin-key": "test_admin"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["applied_live"]["episodic_memory_enabled"]["enabled"] is True
        assert payload["applied_live"]["memory"]["normalized_to"] == "episodic_memory_enabled"

    assert proxy.config.episodic_memory_enabled is True
    assert proxy.episodic_tracker is not None
    assert proxy.episodic_tracker.enabled is True
    assert proxy.episodic_tracker._sweep_task is not None


def test_legacy_admin_flags_can_enable_real_episodic_memory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The legacy dashboard route must use the shipped tracker constructor."""

    monkeypatch.setenv("CUTCTX_SKIP_INTEGRITY_CHECK", "1")
    monkeypatch.setenv("CUTCTX_TELEMETRY", "off")
    monkeypatch.setenv("CUTCTX_EPISODIC_MEMORY_DIR", str(tmp_path / "episodic-memory"))

    config = ProxyConfig(
        admin_api_key="test_admin",
        entitlement_tier="business",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        episodic_memory_enabled=False,
    )
    app = create_app(config)
    proxy = app.state.proxy
    _apply_validated_license(proxy, LicenseInfo(status="active", plan="business"))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/admin/config/flags",
            json={"memory": True},
            headers={"x-cutctx-admin-key": "test_admin"},
        )

    assert response.status_code == 200
    assert proxy.episodic_tracker is not None
    assert proxy.episodic_tracker.enabled is True
    assert proxy.episodic_tracker._sweep_task is not None


def test_dashboard_orchestrator_toggle_loads_codex_mini_preset() -> None:
    """The dashboard toggle must install usable GPT-5.6 Mini routes live."""
    config = ProxyConfig(
        admin_api_key="test_admin",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
    )
    assert config.model_routing_preset is None

    app = create_app(config)
    proxy = app.state.proxy
    with TestClient(app) as client:
        response = client.post(
            "/config/flags",
            json={"orchestrator": True},
            headers={"x-cutctx-admin-key": "test_admin"},
        )

    assert response.status_code == 200
    assert config.model_routing_preset == "codex-gpt54mini-high"
    assert proxy._model_router.config.enabled is True
    assert any(
        route.source == "gpt-5.6-terra" and route.target == "gpt-5.4-mini"
        for route in proxy._model_router.config.routes
    )

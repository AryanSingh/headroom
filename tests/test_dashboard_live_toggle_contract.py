"""BDD contract tests for dashboard-managed live intelligence controls."""

import pytest
from fastapi.testclient import TestClient

from cutctx.proxy.intelligence_pipeline import (
    IntelligencePipeline,
    clear_runtime_flag,
    get_runtime_flag,
)
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app

LIVE_INTELLIGENCE_FLAGS = (
    "task_aware_enabled",
    "dedup_enabled",
    "context_budget_enabled",
    "profiles_enabled",
    "cost_forecast_enabled",
    "autopilot_enabled",
)
PIPELINE_ATTRIBUTES = {
    "task_aware_enabled": "task_aware",
    "dedup_enabled": "dedup",
    "context_budget_enabled": "context_budget",
    "profiles_enabled": "profiles",
    "cost_forecast_enabled": "cost_forecast",
    "autopilot_enabled": "autopilot",
}


@pytest.fixture
def dashboard_config_client():
    """A clean, authenticated proxy instance for toggle contract coverage."""
    for key in LIVE_INTELLIGENCE_FLAGS:
        clear_runtime_flag(key)

    config = ProxyConfig(
        backend="mock",
        admin_api_key="dashboard-toggle-test",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
    )
    app = create_app(config)
    with TestClient(app) as client:
        yield client, config

    for key in LIVE_INTELLIGENCE_FLAGS:
        clear_runtime_flag(key)


@pytest.mark.parametrize("flag_key", LIVE_INTELLIGENCE_FLAGS)
def test_dashboard_live_intelligence_toggle_applies_to_next_request_runtime(
    dashboard_config_client,
    flag_key: str,
) -> None:
    """Given an enabled dashboard control, its runtime state is immediately observable."""
    client, config = dashboard_config_client
    headers = {"x-cutctx-admin-key": "dashboard-toggle-test"}

    response = client.post("/config/flags", headers=headers, json={flag_key: True})

    assert response.status_code == 200
    assert response.json()["applied_live"][flag_key]["enabled"] is True
    assert get_runtime_flag(flag_key) is True
    assert getattr(config, flag_key) is True
    assert getattr(IntelligencePipeline.from_config(config), PIPELINE_ATTRIBUTES[flag_key]) is True

    flags = client.get("/config/flags", headers=headers)
    assert flags.status_code == 200
    assert flags.json()["live_toggleable"][flag_key]["enabled"] is True

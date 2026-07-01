"""Integration tests for dynamic initialization of proxy modules."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app

os.environ["CUTCTX_SKIP_INTEGRITY_CHECK"] = "1"


@pytest.mark.asyncio
async def test_dynamic_initialization_of_memory_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the canonical config route can initialize episodic memory live."""
    monkeypatch.setitem(sys.modules, "cutctx.memory.session_tracker", MagicMock())
    monkeypatch.setitem(sys.modules, "cutctx.memory.store", MagicMock())
    monkeypatch.setitem(sys.modules, "cutctx.intelligence_pipeline", MagicMock())

    config = ProxyConfig()
    config.episodic_memory_enabled = False
    config.firewall_enabled = False
    config.admin_api_key = "test_admin"

    app = create_app(config)
    proxy = app.state.proxy
    assert getattr(proxy, "episodic_tracker", None) is None

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

    assert proxy.config.episodic_memory_enabled is True
    assert proxy.episodic_tracker is not None
    assert proxy.config.firewall_enabled is True

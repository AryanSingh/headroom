"""Integration tests for dynamic initialization of proxy modules."""

import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app

os.environ["CUTCTX_SKIP_INTEGRITY_CHECK"] = "1"


@pytest.mark.asyncio
async def test_dynamic_initialization_of_memory_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that toggling episodic memory on dynamically initializes the tracker."""
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

    client = TestClient(app)
    response = client.post(
        "/admin/config/flags",
        json={"memory": True, "firewall": True},
        headers={"x-cutctx-admin-key": "test_admin"},
    )

    assert response.status_code == 200
    assert proxy.config.episodic_memory_enabled is True
    assert proxy.episodic_tracker is not None
    assert proxy.config.firewall_enabled is True

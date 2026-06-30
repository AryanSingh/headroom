"""Integration tests for dynamic initialization of proxy modules."""

import pytest

from cutctx.proxy.server import create_app

import os
import sys
from unittest.mock import MagicMock

# Mock memory modules to avoid EE import failures in tests
sys.modules['cutctx.memory.session_tracker'] = MagicMock()
sys.modules['cutctx.memory.store'] = MagicMock()
sys.modules['cutctx.intelligence_pipeline'] = MagicMock()

from cutctx.proxy.models import ProxyConfig
os.environ["CUTCTX_SKIP_INTEGRITY_CHECK"] = "1"

@pytest.mark.asyncio
async def test_dynamic_initialization_of_memory_module():
    """Verify that toggling episodic memory ON dynamically initializes the tracker."""

    config = ProxyConfig()
    config.episodic_memory_enabled = False
    config.firewall_enabled = False
    config.admin_api_key = "test_admin"

    app = create_app(config)
    proxy = app.state.proxy

    assert getattr(proxy, "episodic_tracker", None) is None

    from fastapi.testclient import TestClient

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

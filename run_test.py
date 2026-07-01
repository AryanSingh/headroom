import asyncio
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app
from fastapi.testclient import TestClient
import logging
logging.basicConfig(level=logging.WARNING)

config = ProxyConfig()
config.admin_api_key = "test_admin"
config.episodic_memory_enabled = False
app = create_app(config)
proxy = app.state.proxy

client = TestClient(app)
print("Before Tracker:", getattr(proxy, "episodic_tracker", "MISSING"))
response = client.post(
    "/admin/config/flags",
    json={"memory": True},
    headers={"Authorization": "Bearer test_admin"}
)
print("After Tracker:", getattr(proxy, "episodic_tracker", "MISSING"))

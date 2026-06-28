import asyncio
import json
from fastapi.testclient import TestClient
from fastapi import FastAPI
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import CutctxProxy
from cutctx.proxy.routes.admin import create_admin_router

async def test_admin_routes():
    config = ProxyConfig(
        memory_mode="in_memory",
        memory_storage_mode="project"
    )
    proxy = CutctxProxy(config)
    
    async def require_admin_auth():
        pass
        
    def require_rbac_permission(permission):
        async def dependency():
            pass
        return dependency
        
    def require_entitlement(feature):
        async def dependency():
            pass
        return dependency

    router = create_admin_router(
        proxy=proxy,
        config=config,
        require_admin_auth=require_admin_auth,
        require_rbac_permission=require_rbac_permission,
        require_entitlement=require_entitlement,
    )
    
    app = FastAPI()
    app.include_router(router)
    
    client = TestClient(app)
    
    # Test each governance endpoint
    endpoints = [
        "/orgs",
        "/quota",
        "/rbac/roles",
        "/retention/stats",
        "/subscription-window",
        "/audit/stats",
    ]
    
    results = {}
    for endpoint in endpoints:
        try:
            resp = client.get(endpoint)
            results[endpoint] = {
                "status_code": resp.status_code,
                "json": resp.json() if resp.status_code == 200 else resp.text
            }
        except Exception as e:
            results[endpoint] = {
                "status_code": 500,
                "error": str(e)
            }
        
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(test_admin_routes())

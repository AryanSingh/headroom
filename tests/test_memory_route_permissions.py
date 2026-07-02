from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

import cutctx_ee.memory_service.api as memory_api
from cutctx.proxy.routes.memory import create_memory_router
from cutctx_ee.memory_service.store import MemoryStore


def _allow_admin_auth() -> None:
    return None


def test_memory_query_uses_read_permission(tmp_path, monkeypatch) -> None:
    store = MemoryStore(f"sqlite:///{tmp_path / 'memory.db'}")
    monkeypatch.setattr(memory_api, "_store", store, raising=False)

    seen: list[str] = []

    def _rbac(permission: str):
        async def _dependency(_request: Request) -> None:
            seen.append(permission)
            if permission != "memory.read":
                raise HTTPException(status_code=403, detail="wrong permission")

        return _dependency

    app = FastAPI()
    app.include_router(
        create_memory_router(
            require_admin_auth=_allow_admin_auth,
            require_rbac_permission=_rbac,
        )
    )

    with TestClient(app) as client:
        response = client.get("/v1/memory/query")

    assert response.status_code == 200, response.text
    assert seen == ["memory.read"]


def test_memory_sync_uses_write_permission(tmp_path, monkeypatch) -> None:
    store = MemoryStore(f"sqlite:///{tmp_path / 'memory.db'}")
    monkeypatch.setattr(memory_api, "_store", store, raising=False)

    seen: list[str] = []

    def _rbac(permission: str):
        async def _dependency(_request: Request) -> None:
            seen.append(permission)
            if permission != "memory.write":
                raise HTTPException(status_code=403, detail="wrong permission")

        return _dependency

    app = FastAPI()
    app.include_router(
        create_memory_router(
            require_admin_auth=_allow_admin_auth,
            require_rbac_permission=_rbac,
        )
    )

    now = datetime.now(UTC).isoformat()

    with TestClient(app) as client:
        response = client.post(
            "/v1/memory/sync",
            json={
                "org_id": "org-a",
                "workspace_id": "ws-a",
                "since_watermark": 0.0,
                "local_deltas": [
                    {
                        "id": "mem-1",
                        "content": "Cross-agent fact",
                        "user_id": "user-a",
                        "created_at": now,
                        "valid_from": now,
                    }
                ],
            },
        )

    assert response.status_code == 200, response.text
    assert seen == ["memory.write"]


def test_memory_query_supports_zero_arg_rbac_dependencies(tmp_path, monkeypatch) -> None:
    store = MemoryStore(f"sqlite:///{tmp_path / 'memory.db'}")
    monkeypatch.setattr(memory_api, "_store", store, raising=False)
    seen: list[str] = []

    def _rbac(permission: str):
        def _dependency() -> None:
            seen.append(permission)

        return _dependency

    app = FastAPI()
    app.include_router(
        create_memory_router(
            require_admin_auth=_allow_admin_auth,
            require_rbac_permission=_rbac,
        )
    )
    client = TestClient(app)

    response = client.get("/v1/memory/query")

    assert response.status_code == 200, response.text
    assert seen == ["memory.read"]

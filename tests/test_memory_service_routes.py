from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

import cutctx_ee.memory_service.api as memory_api
from cutctx.proxy.routes.memory import create_memory_router
from cutctx_ee.memory_service.models import MemoryRecord
from cutctx_ee.memory_service.store import MemoryStore


def _allow_admin_auth() -> None:
    return None


def _allow_rbac(_permission: str) -> Callable[[], None]:
    def _dependency() -> None:
        return None

    return _dependency


def test_memory_router_mounts_sync_and_review(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "memory.db"
    store = MemoryStore(f"sqlite:///{db_path}")
    monkeypatch.setattr(memory_api, "_store", store, raising=False)

    app = FastAPI()
    app.include_router(
        create_memory_router(
            require_admin_auth=_allow_admin_auth,
            require_rbac_permission=_allow_rbac,
        )
    )

    client = TestClient(app)
    # The route requires admin auth, so a GET should return 401 or 405 (Method Not Allowed since it's a POST)
    # Either way, if it returns 404, it means the route is not mounted.
    r_sync = client.post("/v1/memory/sync", json={})
    assert r_sync.status_code != 404
    r_review = client.post("/v1/memory/review", json={})
    assert r_review.status_code != 404
    r_query = client.post("/v1/memory/query", json={})
    # Query is typically not exposed here unless we have it, wait the original test asserted it is NOT in router paths
    assert r_query.status_code == 404

    client = TestClient(app)
    now = datetime.now(UTC).isoformat()
    sync_resp = client.post(
        "/v1/memory/sync",
        json={
            "org_id": "org-a",
            "workspace_id": "ws-a",
            "since_watermark": 0.0,
            "local_deltas": [
                {
                    "id": "mem-1",
                    "content": "The first shared memory",
                    "user_id": "user-a",
                    "created_at": now,
                    "valid_from": now,
                }
            ],
        },
    )

    assert sync_resp.status_code == 200, sync_resp.text
    assert sync_resp.json()["server_deltas"] == []

    review_resp = client.post(
        "/v1/memory/review",
        json={
            "org_id": "org-a",
            "memory_id": "mem-1",
            "action": "APPROVE",
        },
    )

    assert review_resp.status_code == 200, review_resp.text
    assert review_resp.json()["state"] == "APPROVE"

    with store.SessionLocal() as session:
        record = (
            session.query(MemoryRecord)
            .filter_by(id="mem-1", org_id="org-a")
            .first()
        )
        assert record is not None
        assert record.review_state == "APPROVE"

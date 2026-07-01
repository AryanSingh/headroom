from datetime import UTC, datetime

from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def test_runtime_memory_routes_sync_query_and_review(tmp_path) -> None:
    config = ProxyConfig()
    config.admin_api_key = "test_admin"
    config.memory_db_path = str(tmp_path / "team-memory.db")
    config.optimize = False
    config.cache_enabled = False
    config.rate_limit_enabled = False
    config.cost_tracking_enabled = False

    app = create_app(config)
    now = datetime.now(UTC).isoformat()

    with TestClient(app) as client:
        sync = client.post(
            "/v1/memory/sync",
            headers={"X-Cutctx-Admin-Key": "test_admin"},
            json={
                "org_id": "org-a",
                "workspace_id": "ws-a",
                "since_watermark": 0.0,
                "local_deltas": [
                    {
                        "id": "mem-1",
                        "content": "Cross-agent fact runtime app",
                        "user_id": "user-a",
                        "created_at": now,
                        "valid_from": now,
                    }
                ],
            },
        )
        assert sync.status_code == 200, sync.text

        query = client.get(
            "/v1/memory/query?org_id=org-a&workspace_id=ws-a&limit=5",
            headers={"X-Cutctx-Admin-Key": "test_admin"},
        )
        assert query.status_code == 200, query.text

        items = query.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == "mem-1"
        assert items[0]["content"] == "Cross-agent fact runtime app"

        review = client.post(
            "/v1/memory/review",
            headers={"X-Cutctx-Admin-Key": "test_admin"},
            json={
                "org_id": "org-a",
                "memory_id": "mem-1",
                "action": "APPROVE",
            },
        )
        assert review.status_code == 200, review.text
        review_payload = review.json()
        assert review_payload["status"] == "success"
        assert review_payload["memory_id"] == "mem-1"
        assert review_payload["state"] == "APPROVE"
        assert review_payload["actor"].startswith("key:")

        reviewed = client.get(
            "/v1/memory/query?org_id=org-a&workspace_id=ws-a&limit=5",
            headers={"X-Cutctx-Admin-Key": "test_admin"},
        )
        assert reviewed.status_code == 200, reviewed.text
        reviewed_items = reviewed.json()["items"]
        assert reviewed_items[0]["id"] == "mem-1"

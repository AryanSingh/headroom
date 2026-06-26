# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial

from datetime import UTC, datetime

from cutctx_ee.memory_service.store import MemoryStore


def test_team_sync_store(tmp_path):
    """Test convergence and tenant isolation in the Team Memory Service."""
    db_path = tmp_path / "team_memory.db"
    store = MemoryStore(f"sqlite:///{db_path}")

    org_id = "org_a"
    workspace_id = "proj_1"

    # Client 1 syncs a new memory
    client1_deltas = [
        {
            "id": "mem_1",
            "content": "Client 1 thought",
            "user_id": "u1",
            "valid_from": datetime.now(UTC).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
        }
    ]

    res1 = store.sync(
        org_id=org_id, workspace_id=workspace_id, since_watermark=0.0, local_deltas=client1_deltas
    )

    # Client 1 should receive no server deltas
    assert len(res1["server_deltas"]) == 0

    # Client 2 syncs
    res2 = store.sync(
        org_id=org_id, workspace_id=workspace_id, since_watermark=0.0, local_deltas=[]
    )

    # Client 2 should receive Client 1's memory
    assert len(res2["server_deltas"]) == 1
    assert res2["server_deltas"][0]["id"] == "mem_1"
    assert res2["server_deltas"][0]["content"] == "Client 1 thought"

    # Tenant isolation test
    res_b = store.sync(
        org_id="org_b", workspace_id=workspace_id, since_watermark=0.0, local_deltas=[]
    )
    assert len(res_b["server_deltas"]) == 0

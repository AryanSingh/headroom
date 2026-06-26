from __future__ import annotations

from cutctx.fleet import FleetStore


def test_fleet_store_upsert_and_summary(tmp_path):
    store = FleetStore(db_path=tmp_path / "fleet.db")

    first = store.upsert_heartbeat(
        deployment_id="dep-1",
        name="prod-east",
        org_id="org-1",
        workspace_id="ws-1",
        project_id="proj-1",
        environment="prod",
        region="us-east-1",
        version="1.0.0",
        status="healthy",
        metadata={"replicas": 3},
    )
    assert first["deployment_id"] == "dep-1"
    assert first["metadata"] == {"replicas": 3}

    second = store.upsert_heartbeat(
        deployment_id="dep-1",
        name="prod-east",
        org_id="org-1",
        status="degraded",
    )
    assert second["status"] == "degraded"

    deployments = store.list_deployments(org_id="org-1")
    assert len(deployments) == 1
    assert deployments[0]["deployment_id"] == "dep-1"

    summary = store.summarize()
    assert summary["total"] == 1
    assert summary["status_counts"]["degraded"] == 1


def test_fleet_store_delete(tmp_path):
    store = FleetStore(db_path=tmp_path / "fleet.db")
    store.upsert_heartbeat(deployment_id="dep-2", name="staging")

    assert store.delete_deployment("dep-2") is True
    assert store.get_deployment("dep-2") is None
    assert store.delete_deployment("dep-2") is False

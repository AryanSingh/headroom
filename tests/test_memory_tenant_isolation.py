"""Two-tenant isolation and review-action validation for the team memory API.

Audit C4 (Critical, cross-tenant read / IDOR): ``GET /v1/memory/query`` took
its tenant scope from an optional ``org_id`` query parameter. Omitting it
returned every tenant's rows; supplying another tenant's id returned theirs.
Every pre-existing memory test seeded a single org (``org-a``), so nothing
could observe the leak. These tests seed two orgs and authenticate as one.

Audit H18 (High): ``POST /v1/memory/review`` stored ``action.upper()``
unvalidated, so ``action:"banana"`` returned 200, and the documented verb
``DEPRECATE`` stored "DEPRECATE" while ``/query`` filters on
``review_state != "DEPRECATED"`` — a "successfully deprecated" record kept
being served.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import cutctx_ee.memory_service.api as memory_api
from cutctx.proxy.routes.memory import create_memory_router
from cutctx_ee.memory_service.store import MemoryStore

ORG_A = "org-a"
ORG_B = "org-b"
ORG_B_SECRET = "sk_live_orgb_should_never_leak"


def _seed_two_tenants(tmp_path) -> MemoryStore:
    store = MemoryStore(f"sqlite:///{tmp_path / 'memory.db'}")
    now = datetime.now(UTC).isoformat()
    for org, workspace, memory_id, content in (
        (ORG_A, "ws-a", "mem-a", "Tenant A deploys on Fridays"),
        (ORG_B, "ws-b", "mem-b", f"Tenant B root credential is {ORG_B_SECRET}"),
    ):
        store.sync(
            org_id=org,
            workspace_id=workspace,
            since_watermark=0.0,
            local_deltas=[
                {
                    "id": memory_id,
                    "content": content,
                    "user_id": f"user-{org}",
                    "project_id": f"proj-{org}",
                    "created_at": now,
                    "valid_from": now,
                }
            ],
        )
    return store


def _allow_rbac(_permission: str) -> Callable[[], None]:
    def _dependency() -> None:
        return None

    return _dependency


def _build_app(*, principal_org: str | None, rbac=_allow_rbac) -> FastAPI:
    """Mount the memory router behind an auth dep bound to ``principal_org``.

    ``request.state.cutctx_org_id`` is the trusted, server-set tenant binding
    that ``resolve_principal_org`` reads. ``principal_org=None`` models the
    root admin key, which belongs to no single tenant.
    """

    def _auth(request: Request) -> None:
        if principal_org is not None:
            request.state.cutctx_org_id = principal_org

    app = FastAPI()
    app.include_router(create_memory_router(require_admin_auth=_auth, require_rbac_permission=rbac))
    return app


@pytest.fixture()
def store(tmp_path, monkeypatch) -> MemoryStore:
    seeded = _seed_two_tenants(tmp_path)
    monkeypatch.setattr(memory_api, "_store", seeded, raising=False)
    return seeded


class TestMemoryTenantIsolation:
    """Authenticated as tenant A, tenant B must be unreachable."""

    def test_query_without_org_id_does_not_leak_other_tenant(self, store) -> None:
        with TestClient(_build_app(principal_org=ORG_A)) as client:
            response = client.get("/v1/memory/query")

        assert response.status_code == 200, response.text
        assert ORG_B_SECRET not in response.text
        items = response.json()["items"]
        assert {item["org_id"] for item in items} == {ORG_A}

    def test_query_with_other_tenant_org_id_is_denied(self, store) -> None:
        with TestClient(_build_app(principal_org=ORG_A)) as client:
            response = client.get(f"/v1/memory/query?org_id={ORG_B}")

        assert response.status_code == 403, response.text
        assert ORG_B_SECRET not in response.text

    def test_search_alias_is_scoped_identically(self, store) -> None:
        with TestClient(_build_app(principal_org=ORG_A)) as client:
            unscoped = client.get("/v1/memory/search")
            targeted = client.get(f"/v1/memory/search?org_id={ORG_B}")

        assert unscoped.status_code == 200, unscoped.text
        assert {item["org_id"] for item in unscoped.json()["items"]} == {ORG_A}
        assert ORG_B_SECRET not in unscoped.text
        assert targeted.status_code == 403, targeted.text
        assert ORG_B_SECRET not in targeted.text

    def test_tenant_bound_principal_cannot_request_all_orgs(self, store) -> None:
        with TestClient(_build_app(principal_org=ORG_A)) as client:
            response = client.get("/v1/memory/query?all_orgs=true")

        assert response.status_code == 403, response.text
        assert ORG_B_SECRET not in response.text

    def test_review_cannot_target_another_tenant(self, store) -> None:
        with TestClient(_build_app(principal_org=ORG_A)) as client:
            response = client.post(
                "/v1/memory/review",
                json={"org_id": ORG_B, "memory_id": "mem-b", "action": "DEPRECATE"},
            )

        assert response.status_code == 403, response.text

    def test_unbound_principal_must_name_an_org(self, store) -> None:
        """Omitting the scope is never a wildcard, even for the root admin key."""
        with TestClient(_build_app(principal_org=None)) as client:
            response = client.get("/v1/memory/query")

        assert response.status_code == 400, response.text
        assert ORG_B_SECRET not in response.text

    def test_cross_org_read_requires_a_distinct_permission(self, store) -> None:
        seen: list[str] = []

        def _recording_rbac(permission: str) -> Callable[[], None]:
            def _dependency() -> None:
                seen.append(permission)

            return _dependency

        app = _build_app(principal_org=None, rbac=_recording_rbac)
        with TestClient(app) as client:
            assert client.get(f"/v1/memory/query?org_id={ORG_A}").status_code == 200
            assert client.get("/v1/memory/query?all_orgs=true").status_code == 200

        assert seen == ["memory.read.cross_org", "memory.read.cross_org"]

    def test_project_id_is_enforceable_on_query(self, store) -> None:
        with TestClient(_build_app(principal_org=ORG_A)) as client:
            match = client.get(f"/v1/memory/query?project_id=proj-{ORG_A}")
            miss = client.get(f"/v1/memory/query?project_id=proj-{ORG_B}")

        assert [item["id"] for item in match.json()["items"]] == ["mem-a"]
        assert miss.json()["items"] == []


class TestMemoryReviewActionValidation:
    """H18: only the documented verbs are accepted, and DEPRECATE bites."""

    @pytest.mark.parametrize("action", ["banana", "", "DELETE", "APPROVED"])
    def test_unknown_review_action_is_rejected(self, store, action) -> None:
        with TestClient(_build_app(principal_org=ORG_A)) as client:
            response = client.post(
                "/v1/memory/review",
                json={"org_id": ORG_A, "memory_id": "mem-a", "action": action},
            )
            after = client.get("/v1/memory/query")

        assert response.status_code == 422, response.text
        assert after.json()["items"][0]["review_state"] == "PROPOSED"

    def test_query_exposes_review_state(self, store) -> None:
        with TestClient(_build_app(principal_org=ORG_A)) as client:
            items = client.get("/v1/memory/query").json()["items"]

        assert items[0]["review_state"] == "PROPOSED"

    def test_approve_maps_to_the_approved_review_state(self, store) -> None:
        with TestClient(_build_app(principal_org=ORG_A)) as client:
            response = client.post(
                "/v1/memory/review",
                json={"org_id": ORG_A, "memory_id": "mem-a", "action": "approve"},
            )
            items = client.get("/v1/memory/query").json()["items"]

        assert response.status_code == 200, response.text
        assert response.json()["state"] == "APPROVED"
        assert items[0]["review_state"] == "APPROVED"

    def test_deprecate_actually_stops_the_record_being_served(self, store) -> None:
        with TestClient(_build_app(principal_org=ORG_A)) as client:
            response = client.post(
                "/v1/memory/review",
                json={"org_id": ORG_A, "memory_id": "mem-a", "action": "DEPRECATE"},
            )
            default_items = client.get("/v1/memory/query").json()["items"]
            explicit_items = client.get("/v1/memory/query?include_deprecated=true").json()["items"]

        assert response.status_code == 200, response.text
        assert response.json()["state"] == "DEPRECATED"
        assert default_items == []
        assert [item["id"] for item in explicit_items] == ["mem-a"]
        assert explicit_items[0]["review_state"] == "DEPRECATED"


class TestDashboardMemoryPageContract:
    """R5: the dashboard Memory page broke when C4 landed.

    ``dashboard/src/pages/Memory.jsx`` queried ``/v1/memory/query`` with no
    scope. That is now a 400 for the dashboard's admin key (which is bound to
    no org), so the page rendered an error instead of listing memories. The
    page now retries with the explicit cross-org parameter; these tests pin
    both halves of the sequence it performs.
    """

    def test_unscoped_admin_query_is_the_400_that_broke_the_page(self, store) -> None:
        with TestClient(_build_app(principal_org=None)) as client:
            response = client.get("/v1/memory/query?limit=20")

        assert response.status_code == 400, response.text
        assert "org_id is required" in response.text

    def test_dashboard_fallback_all_orgs_lists_memories(self, store) -> None:
        """The exact retry URL Memory.jsx now issues must succeed."""
        with TestClient(_build_app(principal_org=None)) as client:
            response = client.get("/v1/memory/query?limit=20&all_orgs=true")

        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert {item["org_id"] for item in items} == {ORG_A, ORG_B}

    def test_org_bound_operator_still_uses_the_first_call(self, store) -> None:
        """An org-bound principal must not need the cross-org fallback."""
        with TestClient(_build_app(principal_org=ORG_A)) as client:
            response = client.get("/v1/memory/query?limit=20")

        assert response.status_code == 200, response.text
        assert {item["org_id"] for item in response.json()["items"]} == {ORG_A}


def test_memory_page_issues_the_cross_org_fallback() -> None:
    """Guard the client half of R5 in the same commit as the contract."""
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "dashboard/src/pages/Memory.jsx"
    text = source.read_text(encoding="utf-8")
    assert "all_orgs=true" in text, "Memory.jsx no longer sends the cross-org fallback"
    assert "includes('400')" in text, "Memory.jsx no longer detects the 400 scope error"

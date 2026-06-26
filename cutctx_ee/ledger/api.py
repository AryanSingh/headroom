# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

import csv
import io
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from cutctx_ee.ledger.query import LedgerQuery
from cutctx_ee.ledger.store import LedgerStore

logger = logging.getLogger(__name__)

# A simple global store reference, typically initialized at startup.
_store: LedgerStore | None = None


def init_store(db_url: str = "sqlite:///spend_ledger.db") -> LedgerStore | None:
    """Initialize the global ledger store (idempotent).

    Called from the proxy startup path to ensure the ledger store
    is ready before the first request arrives.  Safe to call
    multiple times — subsequent calls are no-ops.

    Returns the store on success, ``None`` if the store could not be
    initialized (e.g. SQLAlchemy not installed).  When the store is
    ``None`` the /v1/spend/query endpoint will return a 500 with
    "Ledger store not initialized"; the proxy should catch this and
    return empty data.
    """
    global _store
    if _store is not None:
        return _store
    try:
        _store = LedgerStore(db_url=db_url)
        return _store
    except Exception as exc:
        logger.warning("Ledger store init failed: %s", exc)
        return None


class _NullSession:
    """Minimal session-like context manager for the null store.

    Returned by ``_NullStore.SessionLocal()`` so that
    ``with store.SessionLocal() as session:`` succeeds.
    """

    def __enter__(self) -> "_NullSession":
        return self

    def __exit__(self, *args: object) -> None:
        pass


class _NullStore:
    """Graceful fallback when the real LedgerStore cannot be initialised.

    Provides ``SessionLocal`` so the /v1/spend/query endpoint returns
    ``[]`` (empty list) instead of raising a 500 error.
    """

    SessionLocal = _NullSession


def get_store() -> LedgerStore:
    if _store is None:
        init_store()
    if _store is None:
        logger.warning("Ledger store not initialized; using null store (empty results)")
        return _NullStore()  # type: ignore[return-value]
    return _store


router = APIRouter(prefix="/v1/spend", tags=["Spend Ledger"])


class SpendEventPayload(BaseModel):
    ts: int
    org_id: str | None = None
    workspace_id: str | None = None
    project_id: str | None = None
    agent_id: str | None = None
    model: str | None = None
    provider: str | None = None
    auth_mode: str
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_saved: int = 0
    est_cost_usd: float | None = None
    est_cost_saved_usd: float | None = None
    request_id: str


@router.post("/events", status_code=202)
async def ingest_spend_events(
    events: list[SpendEventPayload], store: LedgerStore = Depends(get_store)
) -> dict[str, Any]:
    """Ingest spend events asynchronously from proxy instances."""
    # Convert Pydantic models to dicts for the store
    event_dicts = [e.model_dump() for e in events]
    try:
        store.insert_events(event_dicts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"status": "accepted", "count": len(events)}


@router.get("/query")
async def query_spend(
    request: Request,
    group_by: list[str] = Query(..., description="Columns to group by, e.g. 'org_id', 'model'"),
    start_ts: int | None = None,
    end_ts: int | None = None,
    org_id: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    store: LedgerStore = Depends(get_store),
) -> list[dict[str, Any]]:
    """Time-series aggregation of spend data.

    Audit-Deep-2026-06-21: an authenticated admin with spend.read
    could previously dump aggregate spend across all orgs by
    omitting the org_id filter. The endpoint now requires an
    explicit tenant filter (org_id / workspace_id / project_id)
    UNLESS the caller has the cross-tenant admin scope.
    """
    from cutctx.proxy.routes.admin import _resolve_audit_actor
    from cutctx_ee.rbac import has_permission

    actor = _resolve_audit_actor(request)
    has_cross_tenant = has_permission(actor, "spend.read.cross_tenant")
    if not has_cross_tenant and not (org_id or workspace_id or project_id):
        raise HTTPException(
            status_code=400,
            detail=(
                "Explicit tenant filter required (org_id, "
                "workspace_id, or project_id). Cross-tenant "
                "queries require the spend.read.cross_tenant "
                "permission."
            ),
        )

    with store.SessionLocal() as session:
        query_engine = LedgerQuery(session)
        results = query_engine.aggregate_spend(
            group_by=group_by,
            start_ts=start_ts,
            end_ts=end_ts,
            org_id=org_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    return results


@router.get("/export/csv")
async def export_spend_csv(
    request: Request,
    group_by: list[str] = Query(..., description="Columns to group by, e.g. 'org_id', 'model'"),
    start_ts: int | None = None,
    end_ts: int | None = None,
    org_id: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    store: LedgerStore = Depends(get_store),
) -> StreamingResponse:
    """Export aggregated spend data as CSV.

    Audit-Deep-2026-06-21: same tenant-scoping rule as /query
    (explicit filter required unless cross-tenant scope).
    """
    from cutctx.proxy.routes.admin import _resolve_audit_actor
    from cutctx_ee.rbac import has_permission

    actor = _resolve_audit_actor(request)
    has_cross_tenant = has_permission(actor, "spend.read.cross_tenant")
    if not has_cross_tenant and not (org_id or workspace_id or project_id):
        raise HTTPException(
            status_code=400,
            detail=(
                "Explicit tenant filter required (org_id, "
                "workspace_id, or project_id). Cross-tenant "
                "exports require the spend.read.cross_tenant "
                "permission."
            ),
        )

    with store.SessionLocal() as session:
        query_engine = LedgerQuery(session)
        results = query_engine.aggregate_spend(
            group_by=group_by,
            start_ts=start_ts,
            end_ts=end_ts,
            org_id=org_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    if not results:
        return StreamingResponse(iter([]), media_type="text/csv")

    output = io.StringIO()
    # The keys of the first row are all columns including metrics
    fieldnames = list(results[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in results:
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=spend_export.csv"},
    )


@router.get("/dashboard")
async def spend_dashboard() -> HTMLResponse:
    """Simple dashboard for spend."""
    html = """
    <html>
        <head><title>Spend Dashboard</title></head>
        <body>
            <h1>Spend Ledger Dashboard</h1>
            <p>Use the /v1/spend/query and /v1/spend/export/csv endpoints to view spend data.</p>
        </body>
    </html>
    """
    return HTMLResponse(content=html)

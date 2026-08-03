# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

import enum
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from cutctx_ee.memory_service.models import MemoryRecord
from cutctx_ee.memory_service.store import MemoryStore

logger = logging.getLogger(__name__)

_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    if _store is None:
        raise HTTPException(status_code=500, detail="Memory store not initialized")
    return _store


router = APIRouter(prefix="/v1/memory", tags=["Team Memory"])


class SyncRequest(BaseModel):
    org_id: str
    workspace_id: str | None = None
    since_watermark: float
    local_deltas: list[dict[str, Any]]


class SyncResponse(BaseModel):
    server_deltas: list[dict[str, Any]]
    new_watermark: float


def _resolve_query_org_scope(
    request: Request, requested_org_id: str | None, all_orgs: bool
) -> str | None:
    """Decide which org ``/query`` may read, from the principal — not the URL.

    Audit C4 (cross-tenant read / IDOR): ``org_id`` used to be an optional
    caller-supplied filter. Omitting it returned every tenant's rows and
    supplying somebody else's id returned theirs. The rules are now:

      * A tenant-bound principal is pinned to its own org. It may restate
        that org for readability, but any attempt to name a different org or
        to set ``all_orgs`` is a 403 — a caller can never widen its own scope
        through a request parameter.
      * An unbound principal (the root admin key, which belongs to no single
        tenant) must name the org it wants, or opt into an all-tenant read
        with ``all_orgs=true``. Both are cross-tenant reads and are gated at
        the mount layer by the distinct ``memory.read.cross_org`` permission
        (see ``cutctx/proxy/routes/memory.py``).
      * Omitting the scope entirely is a 400. It is never a wildcard.

    Returns the org to filter on, or ``None`` for an authorised all-tenant
    read.
    """
    from cutctx.proxy.routes.memory import resolve_principal_org

    principal_org = resolve_principal_org(request)
    requested = (requested_org_id or "").strip() or None

    if principal_org:
        if all_orgs or (requested and requested != principal_org):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Memory reads are scoped to the authenticated principal's org "
                    f"({principal_org}); a request parameter cannot widen or change it."
                ),
            )
        return principal_org

    if all_orgs:
        return None
    if requested:
        return requested
    raise HTTPException(
        status_code=400,
        detail=(
            "org_id is required. This principal is not bound to a single org, so "
            "there is no implicit tenant scope; pass org_id=<org>, or all_orgs=true "
            "for an explicit cross-tenant read (requires memory.read.cross_org)."
        ),
    )


@router.get("/query")
@router.get("/search")
async def query_memory(
    request: Request,
    limit: int = 20,
    org_id: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    include_deprecated: bool = False,
    all_orgs: bool = False,
    store: MemoryStore = Depends(get_store),
):
    """Return recent team memories for dashboard and operator verification.

    /search is a compatibility alias for older clients and audit checklists
    that used search terminology before the public route settled on /query.
    """
    scope_org = _resolve_query_org_scope(request, org_id, all_orgs)
    try:
        bounded_limit = max(1, min(int(limit), 100))
        with store.SessionLocal() as session:
            query = session.query(MemoryRecord)
            if scope_org is not None:
                query = query.filter(MemoryRecord.org_id == scope_org)
            if workspace_id:
                query = query.filter(MemoryRecord.workspace_id == workspace_id)
            if project_id:
                query = query.filter(MemoryRecord.project_id == project_id)
            if not include_deprecated:
                query = query.filter(MemoryRecord.review_state != "DEPRECATED")
            rows = (
                query.order_by(
                    MemoryRecord.updated_at_ts.desc(),
                    MemoryRecord.created_at.desc(),
                )
                .limit(bounded_limit)
                .all()
            )
            items = []
            for row in rows:
                item = store._record_to_dict(row)
                # ``MemoryStore._record_to_dict`` omits review_state, so
                # operators could not see whether a row was PROPOSED,
                # APPROVED or DEPRECATED. Surface it here rather than in the
                # store: the shipped store extension module shadows store.py.
                item["review_state"] = row.review_state
                items.append(item)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"items": items}


@router.post("/sync", response_model=SyncResponse)
async def sync_memory(req: SyncRequest, store: MemoryStore = Depends(get_store)) -> SyncResponse:
    """Synchronize local client memories with the team server."""
    try:
        result = store.sync(
            org_id=req.org_id,
            workspace_id=req.workspace_id,
            since_watermark=req.since_watermark,
            local_deltas=req.local_deltas,
        )
        return SyncResponse(
            server_deltas=result["server_deltas"], new_watermark=result["new_watermark"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


class ReviewAction(str, enum.Enum):
    """The only review verbs ``POST /v1/memory/review`` accepts."""

    APPROVE = "APPROVE"
    DEPRECATE = "DEPRECATE"
    PROPOSE = "PROPOSE"


# Audit H18: the handler stored ``action.upper()`` straight into
# ``review_state``. Two bugs fell out of that. Any string was accepted, so
# ``action:"banana"`` returned 200 with ``state:"BANANA"``. And the documented
# verb DEPRECATE stored "DEPRECATE" while ``/query`` filters on
# ``review_state != "DEPRECATED"``, so a "successfully deprecated" record kept
# being served forever. Verbs now map explicitly onto the review states
# declared on ``MemoryRecord.review_state``.
REVIEW_ACTION_STATES: dict[ReviewAction, str] = {
    ReviewAction.APPROVE: "APPROVED",
    ReviewAction.DEPRECATE: "DEPRECATED",
    ReviewAction.PROPOSE: "PROPOSED",
}


class ReviewRequest(BaseModel):
    org_id: str
    memory_id: str
    action: ReviewAction

    @field_validator("action", mode="before")
    @classmethod
    def _normalize_action(cls, value: Any) -> Any:
        """Keep the pre-fix case-insensitivity; reject anything unknown (422)."""
        return value.strip().upper() if isinstance(value, str) else value


@router.post("/review")
async def review_memory(
    request: Request,
    req: ReviewRequest,
    store: MemoryStore = Depends(get_store),
) -> dict[str, Any]:
    """Review a memory candidate (curator only).

    Audit-Deep-2026-06-21 Blocker 3c: the previous code had
    explicit TODOs admitting no RBAC and no audit emission. The
    endpoint now:

      1. Resolves the audit actor via the shared helper
         (sso: > key: > admin hierarchy).
      2. Emits a ``memory.<action>`` audit event (APPROVE /
         DEPRECATE / PROPOSE) to the audit store when one is
         configured.
      3. RBAC enforcement still lives at the route mount layer
         (see ``cutctx/proxy/routes/memory.py`` which gates
         this entire router with ``memory.write`` permission).
         The audit is a defense-in-depth: even if a future call
         path bypasses the auth gate, the audit log records who
         acted.
    """
    from cutctx.proxy.routes.admin import _resolve_audit_actor
    from cutctx.proxy.routes.memory import resolve_principal_org

    actor = _resolve_audit_actor(request)

    # C4 defense-in-depth: a tenant-bound principal may only curate its own
    # org, regardless of what the body says.
    principal_org = resolve_principal_org(request)
    if principal_org and req.org_id != principal_org:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Memory review is scoped to the authenticated principal's org ({principal_org})."
            ),
        )

    new_state = REVIEW_ACTION_STATES[req.action]
    try:
        store.update_review_state(org_id=req.org_id, memory_id=req.memory_id, new_state=new_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Audit emission (best-effort; never let an audit failure
    # roll back the review).
    try:
        from cutctx_ee.audit.api import get_store as get_audit_store

        audit_store = get_audit_store()
        audit_store.append_event(
            tenant_id=req.org_id,
            actor=actor,
            action=f"memory.{req.action.value.lower()}",
            payload={"memory_id": req.memory_id},
        )
    except Exception as exc:
        # Audit store not configured (OSS-only deployment) or
        # transient failure. The review itself succeeded.
        logger.debug("Audit event for memory %s skipped: %s", req.memory_id, exc)

    return {
        "status": "success",
        "memory_id": req.memory_id,
        "state": new_state,
        "actor": actor,
    }

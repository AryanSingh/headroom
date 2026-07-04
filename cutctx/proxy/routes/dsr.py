# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""GDPR/CCPA Data Subject Request (DSR) endpoints.

Blocker-2 (production-audit-2026-06-20.md): the audit found zero
right-to-delete or right-to-export endpoints. The audit, memory,
CCR, and org stores all support individual row CRUD but no
end-user "delete me from all stores" flow existed.

This module adds two endpoints behind admin auth + the
``privacy.dsr`` RBAC permission:

  GET  /v1/me/export
      Returns a JSON document with every record the system holds
      for the supplied user_id. The caller identifies the target
      via (in priority order): explicit ``user_id`` query param,
      ``request.state.cutctx_user_id`` (set by SSO auth), or the
      ``X-Cutctx-User-Id`` request header.

  POST /v1/me/delete
      Cascades the user_id out of every store that holds
      user-scoped data:
        - Memory (via ``MemoryHandler.delete_for_user``)
        - Audit log (via ``cutctx_ee.audit.AuditLogger.delete_for_actor``)
        - Spend ledger: NO-OP (SpendEvent has no user_id column;
          only org_id / agent_id / workspace_id / project_id).
          The response reports a note explaining the gap; production
          deployments handling DSR for spend data must implement
          tenant-scoped deletion by org_id.

The response reports per-store counts. A failed deletion is
logged but does not abort the cascade — DSR is best-effort and
the operator runs a periodic VACUUM afterward to reclaim space.

Production deployments must add a follow-up periodic GC pass to
sweep the SQLite vacuum after bulk DSR deletes (issue P0-DSR-1).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DSRDeleteRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=256, description="User id to delete")


def _resolve_target_user_id(
    request: Request, body_user_id: str | None, query_user_id: str | None
) -> str:
    """Decide which user_id the DSR request targets.

    Priority:
      1. ``body_user_id`` (POST /v1/me/delete explicit body field)
      2. ``query_user_id`` (GET /v1/me/export ?user_id=... param)
      3. ``request.state.cutctx_user_id`` (set by SSO auth)
      4. ``X-Cutctx-User-Id`` request header (SSO claim passthrough)

    Raises 400 if none of the above is set — the system will never
    silently target an empty user_id.
    """
    if body_user_id:
        return body_user_id
    if query_user_id:
        return query_user_id
    state_user = getattr(request.state, "cutctx_user_id", None)
    if state_user:
        return str(state_user)
    header_user = request.headers.get("X-Cutctx-User-Id", "").strip()
    if header_user:
        return header_user
    raise HTTPException(
        status_code=400,
        detail=(
            "No user_id resolved from body, query param, SSO claim, or X-Cutctx-User-Id header"
        ),
    )


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_dsr_router(
    proxy: Any | None = None,
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the DSR router with auth dependencies applied.

    The DSR endpoints require admin auth + the ``privacy.dsr`` RBAC
    permission. Admin auth is required because the DSR surface is
    sensitive: it can dump or delete every record for a user_id.

    Parameters
    ----------
    proxy : CutctxProxy | None
        The live proxy instance. Required to reach the memory
        subsystem. If ``None``, the memory export/delete paths
        are reported as ``not_available`` in the response.
    require_admin_auth, require_rbac_permission : Callable | None
        Auth dependencies passed in by ``server.py``.
    """
    router = APIRouter(prefix="/v1/dsr", tags=["Privacy"])

    dependencies: list[Any] = []
    if require_admin_auth is not None:
        dependencies.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        # The ``privacy.dsr`` permission is a new addition. EE
        # deployments must add this to the PERMISSION_MAP in
        # ``cutctx_ee/rbac.py`` (mapped to AdminRole.ADMIN).
        # OSS-only deployments fall through the RBAC check because
        # the ``_require_rbac_permission`` factory in server.py
        # returns (allows) when no RBAC checker is configured.
        dependencies.append(Depends(require_rbac_permission("privacy.dsr")))
    if not dependencies:
        logger.warning(
            "create_dsr_router built without auth dependencies — "
            "/v1/me/* will be reachable without auth. "
            "This must be fixed in production deployments."
        )

    @router.get("/export", dependencies=dependencies)
    async def export_user_data(
        request: Request,
        user_id: str | None = None,
    ) -> dict:
        """Return a JSON document with every record the system holds
        for the supplied (or SSO-resolved) user_id.

        Each store is asked whether it has data for the user;
        stores that error out are reported in the ``store_errors``
        field but do not abort the export.
        """
        target = _resolve_target_user_id(request, body_user_id=None, query_user_id=user_id)
        logger.info("event=dsr_export user_id=%s", target)
        payload: dict[str, Any] = {
            "user_id": target,
            "generated_at": _now_iso(),
            "stores": {},
            "store_errors": {},
        }

        # Memory store: export memories for the user.
        memory_handler = getattr(proxy, "memory_handler", None) if proxy is not None else None
        if memory_handler is not None:
            try:
                result = await memory_handler.export_for_user(target)
                # Audit-Deep-2026-06-21 P0 GDPR fix: the memory
                # records can contain numpy arrays (the embedding
                # vector) which FastAPI's default JSON encoder
                # cannot serialize. We pre-encode with
                # jsonable_encoder so the route returns 200, not
                # 500, for users whose memories include embeddings.
                payload["stores"]["memory"] = {
                    "count": result.get("count", 0),
                    "records": jsonable_encoder(result.get("records", [])),
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("event=dsr_export_memory_error user_id=%s error=%r", target, exc)
                payload["store_errors"]["memory"] = str(exc)
        else:
            payload["store_errors"]["memory"] = "memory_handler not configured"

        # Spend ledger: query events for the user.
        #
        # The spend ledger (cutctx_ee.ledger.models.SpendEvent) is
        # keyed by org_id / agent_id / workspace_id / project_id —
        # there is no ``user_id`` column. The DSR target user_id
        # cannot be reliably linked to spend events, so the export
        # path reports this honestly instead of pretending to export
        # unrelated rows. The delete path is a no-op for the same
        # reason; production deployments handling DSR for spend
        # data must implement a tenant-scoped policy (e.g. require
        # org_id in the request and delete by org_id).
        try:
            from cutctx_ee.ledger.api import query_spend  # noqa: F401

            # query_spend is a FastAPI route handler (Request,
            # Query, Depends), not a plain function. It is
            # importable to confirm EE is installed, but it is not
            # callable from this context — DSR cannot bridge the
            # user_id → org_id gap.
            payload["stores"]["spend_ledger"] = {
                "count": 0,
                "records": [],
                "note": (
                    "spend_ledger is keyed by org_id/agent_id, not "
                    "user_id; DSR cannot map this user_id to spend "
                    "events. Provide org_id in the body for tenant-"
                    "scoped spend export."
                ),
            }
        except ImportError:
            payload["store_errors"]["spend_ledger"] = "EE module not installed"
        except Exception as exc:  # noqa: BLE001
            logger.exception("event=dsr_export_spend_error user_id=%s error=%r", target, exc)
            payload["store_errors"]["spend_ledger"] = str(exc)

        # Audit log: query events for the actor == user_id.
        try:
            from cutctx_ee.audit import get_audit_logger

            audit_logger = get_audit_logger()
            events = audit_logger.query(actor=target, limit=1000)
            payload["stores"]["audit"] = {
                "count": len(events) if events else 0,
                "records": jsonable_encoder(events) if events else [],
            }
        except ImportError:
            payload["store_errors"]["audit"] = "EE module not installed"
        except Exception as exc:  # noqa: BLE001
            logger.exception("event=dsr_export_audit_error user_id=%s error=%r", target, exc)
            payload["store_errors"]["audit"] = str(exc)

        return payload

    @router.post("/delete", dependencies=dependencies)
    async def delete_user_data(
        request: Request,
        body: DSRDeleteRequest | None = None,
    ) -> dict:
        """Cascade-delete every record the system holds for the
        supplied (or SSO-resolved) user_id.

        The response reports which stores succeeded vs failed. A
        failed deletion is logged but does not abort the cascade.
        Production deployments must run a periodic SQLite VACUUM
        after bulk DSR deletes to reclaim disk space.
        """
        body_user_id = body.user_id if body else None
        target = _resolve_target_user_id(request, body_user_id=body_user_id, query_user_id=None)
        logger.warning("event=dsr_delete user_id=%s", target)
        result: dict[str, Any] = {
            "user_id": target,
            "deleted_at": _now_iso(),
            "stores": {},
            "store_errors": {},
        }

        # Memory store: delete memories for the user.
        memory_handler = getattr(proxy, "memory_handler", None) if proxy is not None else None
        if memory_handler is not None:
            try:
                counts = await memory_handler.delete_for_user(target)
                result["stores"]["memory"] = counts
            except Exception as exc:  # noqa: BLE001
                logger.exception("event=dsr_delete_memory_error user_id=%s error=%r", target, exc)
                result["store_errors"]["memory"] = str(exc)
        else:
            result["store_errors"]["memory"] = "memory_handler not configured"

        # Spend ledger: delete events for the user.
        #
        # The spend ledger has no user_id column. See the export
        # branch for the full rationale. The delete path is
        # therefore a no-op for spend data; production deployments
        # handling DSR for spend must implement tenant-scoped
        # deletion (by org_id).
        try:
            from cutctx_ee.ledger.api import query_spend  # noqa: F401

            result["stores"]["spend_ledger"] = {
                "deleted": 0,
                "note": (
                    "spend_ledger is keyed by org_id/agent_id, not "
                    "user_id; DSR cannot map this user_id to spend "
                    "events. Provide org_id for tenant-scoped spend "
                    "deletion."
                ),
            }
        except ImportError:
            result["store_errors"]["spend_ledger"] = "EE module not installed"
        except Exception as exc:  # noqa: BLE001
            logger.exception("event=dsr_delete_spend_error user_id=%s error=%r", target, exc)
            result["store_errors"]["spend_ledger"] = str(exc)

        # Audit log: delete events for the actor == user_id.
        # GDPR right-to-be-forgotten: delete_for_actor is a
        # documented DSR exception to the audit log's append-only
        # contract.
        try:
            from cutctx_ee.audit import get_audit_logger

            audit_logger = get_audit_logger()
            n = audit_logger.delete_for_actor(target)
            result["stores"]["audit"] = {"deleted": n}
        except ImportError:
            result["store_errors"]["audit"] = "EE module not installed"
        except Exception as exc:  # noqa: BLE001
            logger.exception("event=dsr_delete_audit_error user_id=%s error=%r", target, exc)
            result["store_errors"]["audit"] = str(exc)

        return result

    return router


__all__ = ["create_dsr_router", "DSRDeleteRequest"]

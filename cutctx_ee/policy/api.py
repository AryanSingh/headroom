# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from cutctx_ee.policy.resolver import PolicyResolver
from cutctx_ee.policy.store import PolicyStore

# Global store reference
_store: PolicyStore | None = None


def get_store() -> PolicyStore:
    if _store is None:
        raise HTTPException(status_code=500, detail="Policy store not initialized")
    return _store


router = APIRouter(prefix="/v1/policies", tags=["Policy"])


class PolicyCreate(BaseModel):
    org_id: str
    workspace_id: str | None = None
    budget_limit_usd: float | None = None
    budget_period: str | None = None
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    allowed_models: list[str] | None = None
    require_compression: bool = False


@router.post("")
async def create_or_update_policy(
    request: Request,
    policy: PolicyCreate,
    store: PolicyStore = Depends(get_store),
) -> dict[str, Any]:
    """Create or update a policy."""
    kwargs = policy.model_dump(exclude={"org_id", "workspace_id"}, exclude_unset=True)
    if "allowed_models" in kwargs and kwargs["allowed_models"] is not None:
        kwargs["allowed_models"] = ",".join(kwargs["allowed_models"])

    result = store.upsert_policy(org_id=policy.org_id, workspace_id=policy.workspace_id, **kwargs)

    try:
        from cutctx.proxy.routes.admin import _resolve_audit_actor
        from cutctx_ee.audit.api import get_store as get_audit_store

        # Audit-Deep-2026-06-21: use the shared actor resolver so the
        # audit attribution matches the sso: > key: > admin hierarchy
        # used by every other admin path. The previous code hardcoded
        # actor="admin", which made it impossible to attribute policy
        # changes to the actual authenticated identity.
        audit_store = get_audit_store()
        audit_store.append_event(
            tenant_id=policy.org_id,
            actor=_resolve_audit_actor(request),
            action="policy.upsert",
            payload={"workspace_id": policy.workspace_id, "changes": kwargs},
        )
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Failed to emit audit event: {e}")

    return result


@router.get("/{org_id}/signed")
async def get_signed_policy(
    org_id: str,
    workspace_id: str | None = None,
    store: PolicyStore = Depends(get_store),
) -> dict[str, str]:
    """Get the signed policy payload for the proxy cache."""
    resolver = PolicyResolver(store)
    signed = resolver.resolve_and_sign(org_id, workspace_id)
    if not signed:
        raise HTTPException(status_code=404, detail="No policy found")
    return {"signed_policy": signed}

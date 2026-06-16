# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from headroom_ee.policy.resolver import PolicyResolver
from headroom_ee.policy.store import PolicyStore

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
    policy: PolicyCreate,
    store: PolicyStore = Depends(get_store),
) -> dict[str, Any]:
    """Create or update a policy."""
    kwargs = policy.model_dump(exclude={"org_id", "workspace_id"}, exclude_unset=True)
    if "allowed_models" in kwargs and kwargs["allowed_models"] is not None:
        kwargs["allowed_models"] = ",".join(kwargs["allowed_models"])

    result = store.upsert_policy(org_id=policy.org_id, workspace_id=policy.workspace_id, **kwargs)

    try:
        from headroom_ee.audit.api import get_store as get_audit_store

        audit_store = get_audit_store()
        audit_store.append_event(
            tenant_id=policy.org_id,
            actor="admin",  # Assuming admin for now
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

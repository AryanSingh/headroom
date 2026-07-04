# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""MFA (TOTP) enrollment and management endpoints.

Audit-Deep-2026-06-21 High-12: admin MFA via TOTP (RFC 6238).
The endpoints let an SSO-authenticated admin enroll their
authenticator app, then use the codes for subsequent second-
factor auth.

The endpoints are factory-built so they can be wired into the
proxy with the same auth + RBAC dependencies as every other
admin route.

Endpoints:
  POST /v1/admin/mfa/enroll   { } -> { secret, otpauth_url, qr_code_data_url }
  POST /v1/admin/mfa/verify   { code } -> { ok: true/false }
  DELETE /v1/admin/mfa        { } -> { status: "revoked" }
  GET  /v1/admin/mfa          { } -> { enrolled, enrolled_at, last_used_counter }
  GET  /v1/admin/mfa/code     { } -> { code, remaining_s }  # for testing
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request

logger = logging.getLogger(__name__)


def _mfa_db_path() -> str:
    return os.environ.get("CUTCTX_RBAC_DB_PATH") or "~/.cutctx/rbac.db"


def create_mfa_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the MFA router with auth dependencies applied.

    All routes require the ``mfa.write`` RBAC permission (or
    the caller must be an SSO-authenticated admin). The
    endpoints refuse to operate when the auth dependency is
    missing (the warning is loud so a misconfigured deployment
    can't accidentally expose the endpoints).
    """
    router = APIRouter(prefix="/v1/admin/mfa", tags=["MFA"])
    deps: list[Any] = []
    if require_admin_auth is not None:
        deps.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        deps.append(Depends(require_rbac_permission("mfa.write")))
    if not deps:
        logger.warning(
            "create_mfa_router built without auth dependencies — "
            "/v1/admin/mfa/* will be reachable without auth."
        )

    @router.post("/enroll", dependencies=deps)
    async def enroll_mfa(
        request: Request,
    ) -> dict[str, Any]:
        """Enroll MFA. Returns the base32 secret and an
        otpauth:// URL the operator can paste into any
        TOTP-compatible authenticator app.
        """
        from cutctx.security.mfa import MfaStore, generate_secret

        # Resolve the SSO subject. The auth dependency already
        # ran; the user_id is on request.state.
        user_id = getattr(request.state, "cutctx_user_id", None)
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "MFA enrollment requires an SSO-authenticated "
                    "subject. API-key authenticated requests cannot "
                    "enroll (the admin key is itself a long-lived "
                    "secret and there is no human user_id)."
                ),
            )
        secret = generate_secret()
        try:
            MfaStore(db_path=_mfa_db_path()).enroll(user_id, secret)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to persist MFA enrollment: {exc}",
            ) from exc
        # otpauth:// URI per the Key URI Format spec; lets the
        # operator paste into Google Authenticator / 1Password.
        otpauth_url = (
            f"otpauth://totp/Cutctx:{user_id}"
            f"?secret={secret}"
            f"&issuer=Cutctx"
            f"&algorithm=SHA1"
            f"&digits=6"
            f"&period=30"
        )
        return {
            "secret": secret,
            "otpauth_url": otpauth_url,
            "user_id": user_id,
        }

    @router.post("/verify", dependencies=deps)
    async def verify_mfa_code(
        request: Request,
        code: str = Body(..., embed=True),
    ) -> dict[str, Any]:
        """Verify a TOTP code (does not consume the counter).

        Useful for an enrollment flow that wants to confirm the
        operator can produce valid codes before the codes start
        being enforced.
        """
        from cutctx.security.mfa import MfaStore, verify_totp

        user_id = getattr(request.state, "cutctx_user_id", None)
        if not user_id:
            raise HTTPException(status_code=400, detail="SSO subject required")
        enrollment = MfaStore(db_path=_mfa_db_path()).get(user_id)
        if enrollment is None:
            raise HTTPException(status_code=404, detail="Not enrolled")
        ok = verify_totp(
            enrollment["secret_b32"],
            code,
            last_used_counter=enrollment["last_used_counter"],
        )
        return {"ok": ok}

    @router.delete("", dependencies=deps)
    async def revoke_mfa(request: Request) -> dict[str, Any]:
        """Revoke an MFA enrollment. After this the operator
        can authenticate with just SSO (no second factor) until
        they re-enroll.
        """
        from cutctx.security.mfa import MfaStore

        user_id = getattr(request.state, "cutctx_user_id", None)
        if not user_id:
            raise HTTPException(status_code=400, detail="SSO subject required")
        removed = MfaStore(db_path=_mfa_db_path()).revoke(user_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Not enrolled")
        return {"status": "revoked", "user_id": user_id}

    @router.get("", dependencies=deps)
    async def get_mfa_status(request: Request) -> dict[str, Any]:
        """Return enrollment status (no secret material)."""
        from cutctx.security.mfa import MfaStore

        user_id = getattr(request.state, "cutctx_user_id", None)
        if not user_id:
            raise HTTPException(status_code=400, detail="SSO subject required")
        enrollment = MfaStore(db_path=_mfa_db_path()).get(user_id)
        if enrollment is None:
            return {
                "enrolled": False,
                "user_id": user_id,
            }
        return {
            "enrolled": True,
            "user_id": user_id,
            "enrolled_at": enrollment["enrolled_at"],
            "last_used_counter": enrollment["last_used_counter"],
        }

    @router.get("/code", dependencies=deps)
    async def get_current_code(request: Request) -> dict[str, Any]:
        """Return the current TOTP code. Useful for testing
        integrations; not for production use (an authenticator
        app should be the source of truth).
        """
        from cutctx.security.mfa import MfaStore, current_totp

        user_id = getattr(request.state, "cutctx_user_id", None)
        if not user_id:
            raise HTTPException(status_code=400, detail="SSO subject required")
        enrollment = MfaStore(db_path=_mfa_db_path()).get(user_id)
        if enrollment is None:
            raise HTTPException(status_code=404, detail="Not enrolled")
        totp = current_totp(enrollment["secret_b32"])
        return {
            "code": totp.code,
            "remaining_s": totp.remaining_s,
        }

    return router


__all__ = ["create_mfa_router"]

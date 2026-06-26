# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs contributors.
# Licensed under the Apache License, Version 2.0 — see LICENSE for details.
"""FastAPI router for the data-residency proof endpoint.

Mounts ``GET /v1/residency/proof`` which returns a JSON attestation of the
current data-residency posture.  Signed attestations are produced when the
``sign=true`` query parameter is supplied **and** ``cutctx_ee`` is installed
with Ed25519 key material configured in environment variables.

This file contains only OSS (Apache-2.0) code.  All commercial logic lives
exclusively in ``cutctx_ee``.

SECURITY: prior to the round-4 fix this route was mounted WITHOUT auth,
which leaked the data-region list, egress blocklist, and audit chain tail
hash to any unauthenticated caller (an attacker could set tenant_id=acme-corp
and harvest the chain tail of any tenant). Now the route requires admin auth
plus the ``residency.read`` RBAC permission.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger("cutctx.proxy.routes.residency")


def create_residency_router(
    require_admin_auth: Any = None,
    require_rbac_permission: Any = None,
) -> APIRouter:
    """Build the residency router with auth dependencies wired in.

    Factory pattern (rather than a module-level ``router``) so the
    FastAPI ``Depends(...)`` callables can be injected from the proxy
    server. This is the same pattern used by ``admin.py``,
    ``secrets.py``, ``rbac.py`` and other authenticated route modules.
    """
    router = APIRouter(prefix="/v1/residency", tags=["Residency"])
    deps: list[Any] = []
    if require_admin_auth is not None:
        deps.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        deps.append(Depends(require_rbac_permission("residency.read")))
    if not deps:
        logger.warning(
            "create_residency_router built without auth dependencies — "
            "/v1/residency/* will be reachable without auth. This is "
            "the round-4 P0; do not deploy without require_admin_auth."
        )

    @router.get(
        "/proof",
        summary="Data-residency attestation",
        response_description="A JSON object describing the current residency posture.",
        dependencies=deps,
    )
    async def get_residency_proof(
        tenant_id: Annotated[
            str,
            Query(description="Tenant identifier to include in the attestation."),
        ] = "default",
        data_regions: Annotated[
            str,
            Query(
                description=(
                    "Comma-separated list of data-region labels "
                    "(e.g. 'eu-west-1,eu-central-1')."
                )
            ),
        ] = "",
        sign: Annotated[
            bool,
            Query(
                description=(
                    "When true, sign the attestation with the EE Ed25519 key "
                    "(requires cutctx_ee and CUTCTX_LICENSE_* env vars)."
                )
            ),
        ] = False,
    ) -> dict:
        """Return a verifiable residency attestation for the given tenant.

        The response is a JSON object matching the ``ResidencyAttestation``
        dataclass.  When ``sign=false`` (the default) the ``signature_hex`` and
        ``signer_kid`` fields will be ``null``.

        When ``sign=true`` the EE Ed25519 private key is used to sign a SHA-256
        digest of the canonical payload.  Verification requires the corresponding
        public key (see ``docs/data-residency.md``).
        """
        try:
            from cutctx.security.residency_proof import ResidencyProver
        except ImportError as exc:  # pragma: no cover
            raise HTTPException(
                status_code=503,
                detail=f"Residency proof module unavailable: {exc}",
            ) from exc

        regions = [r.strip() for r in data_regions.split(",") if r.strip()]

        try:
            prover = ResidencyProver(tenant_id=tenant_id)
            attestation = prover.generate(data_regions=regions, sign=sign)
            import json

            return json.loads(prover.export_json(attestation))
        except RuntimeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error generating residency proof: %s", exc)
            raise HTTPException(
                status_code=500, detail="Internal error generating residency proof"
            ) from exc

    return router

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs contributors.
# Licensed under the Apache License, Version 2.0 — see LICENSE for details.
"""FastAPI router for the data-residency proof endpoint.

Mounts ``GET /v1/residency/proof`` which returns a JSON attestation of the
current data-residency posture.  Signed attestations are produced when the
``sign=true`` query parameter is supplied **and** ``headroom_ee`` is installed
with Ed25519 key material configured in environment variables.

This file contains only OSS (Apache-2.0) code.  All commercial logic lives
exclusively in ``headroom_ee``.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("headroom.proxy.routes.residency")

router = APIRouter(prefix="/v1/residency", tags=["Residency"])


@router.get(
    "/proof",
    summary="Data-residency attestation",
    response_description="A JSON object describing the current residency posture.",
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
                "(requires headroom_ee and HEADROOM_LICENSE_* env vars)."
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
        from headroom.security.residency_proof import ResidencyProver
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

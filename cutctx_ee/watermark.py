# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs.

"""Read-only release identity markers for enterprise artifacts.

Release tooling may place a signed manifest alongside an artifact. This module
only creates and parses the marker payload; it never edits package files or
inspects binaries. That boundary keeps runtime installations predictable and
avoids behavior commonly associated with endpoint-protection false positives.
"""

from __future__ import annotations

import base64
import json
import secrets
import sqlite3
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MARKER_PREFIX = "CTXWM:"
MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Watermark:
    """A release-identity marker associated with one enterprise license."""

    lic_id: str
    customer_id: str
    build_id: str
    canary_token: str = field(default_factory=lambda: secrets.token_hex(16))
    embedded_at: float = field(default_factory=time.time)

    def to_marker(self) -> str:
        """Serialize this marker in the compatibility-preserving CTXWM form."""

        payload = json.dumps(
            {
                "lic": self.lic_id,
                "cus": self.customer_id,
                "bld": self.build_id,
                "cny": self.canary_token,
                "ts": int(self.embedded_at),
            },
            separators=(",", ":"),
        )
        return MARKER_PREFIX + base64.urlsafe_b64encode(payload.encode()).decode()

    @classmethod
    def from_marker(cls, marker: str) -> Watermark | None:
        """Parse a marker without raising for malformed or untrusted input."""

        if not marker.startswith(MARKER_PREFIX):
            return None
        try:
            payload = json.loads(base64.urlsafe_b64decode(marker[len(MARKER_PREFIX) :]))
            if not isinstance(payload, dict):
                return None
            return cls(
                lic_id=str(payload["lic"]),
                customer_id=str(payload["cus"]),
                build_id=str(payload["bld"]),
                canary_token=str(payload["cny"]),
                embedded_at=float(payload["ts"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None


def watermark_manifest(watermark: Watermark) -> dict[str, str | int]:
    """Return metadata for a release pipeline to write into a signed manifest."""

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "marker": watermark.to_marker(),
    }


def extract_watermark_from_manifest(manifest: Mapping[str, Any]) -> Watermark | None:
    """Extract a marker from already-loaded release metadata."""

    marker = manifest.get("marker")
    return Watermark.from_marker(marker) if isinstance(marker, str) else None


def verify_watermark_traceability(
    watermarks: Iterable[Watermark],
    license_db_path: Path,
) -> dict[str, bool]:
    """Verify supplied marker license IDs against a local SQLite license DB."""

    markers = list(watermarks)
    if not license_db_path.exists():
        return {watermark.lic_id: False for watermark in markers}

    with sqlite3.connect(str(license_db_path)) as connection:
        return {
            watermark.lic_id: connection.execute(
                "SELECT 1 FROM licenses WHERE license_key = ?",
                (watermark.lic_id,),
            ).fetchone()
            is not None
            for watermark in markers
        }


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "MARKER_PREFIX",
    "Watermark",
    "extract_watermark_from_manifest",
    "verify_watermark_traceability",
    "watermark_manifest",
]

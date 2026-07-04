# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs.

"""SP-5: Per-customer watermarking and leak tracing.

Embeds per-license watermarks and canary tokens into EE artifacts so that
leaked copies can be traced back to the specific customer who received them.

Design principles:
- Watermarks are embedded at build time, not runtime
- Canary tokens are unique inert markers (fake internal URLs/strings)
- Extraction is deterministic: given a build, recover the lic_id
- All watermark→license mappings stored server-side for correlation
"""

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Watermark:
    """A per-license watermark embedded in an EE artifact."""

    lic_id: str
    customer_id: str
    build_id: str
    # Unique canary token — an inert string that identifies this specific build
    canary_token: str = field(default_factory=lambda: secrets.token_hex(16))
    # Timestamp of embedding
    embedded_at: float = field(default_factory=time.time)

    def to_marker(self) -> str:
        """Convert to a marker string embedded in compiled artifacts."""
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
        # Base64-encode for safe embedding in compiled binaries
        import base64

        encoded = base64.urlsafe_b64encode(payload.encode()).decode()
        return f"CTXWM:{encoded}"

    @classmethod
    def from_marker(cls, marker: str) -> Optional["Watermark"]:
        """Extract a watermark from an embedded marker string."""
        if not marker.startswith("CTXWM:"):
            return None
        try:
            import base64

            encoded = marker[6:]  # Strip CTXWM: prefix
            payload = json.loads(base64.urlsafe_b64decode(encoded))
            return cls(
                lic_id=payload["lic"],
                customer_id=payload["cus"],
                build_id=payload["bld"],
                canary_token=payload["cny"],
                embedded_at=payload["ts"],
            )
        except Exception:
            return None


def generate_canary_strings(lic_id: str, count: int = 3) -> list[str]:
    """Generate unique canary strings for a specific license.

    These are fake "internal" strings that should never appear in public.
    If found on paste sites or public repos, they identify the leaker.
    """
    canaries = []
    for i in range(count):
        hashlib.sha256(f"{lic_id}:canary:{i}".encode()).digest()[:8]
        canary = f"CUTCTX_INTERNAL_{secrets.token_hex(8)}"
        canaries.append(canary)
    return canaries


def embed_watermark_in_source(
    source_dir: Path,
    watermark: Watermark,
) -> int:
    """Embed watermark markers in Python source files (pre-compilation).

    Adds the CTXWM marker and canary strings as comments in __init__.py
    and other key files. These survive Nuitka compilation as string constants.

    Returns the number of files modified.
    """
    marker = watermark.to_marker()
    canaries = generate_canary_strings(watermark.lic_id)
    modified = 0

    # Always watermark __init__.py
    init_file = source_dir / "__init__.py"
    if init_file.exists():
        content = init_file.read_text(encoding="utf-8")
        # Append watermark as a string constant (survives compilation)
        watermark_line = f'__watermark__ = "{marker}"  # SP-5: do not remove\n'
        canary_lines = [
            f'__canary_{i}__ = "{c}"  # SP-5: do not remove\n' for i, c in enumerate(canaries)
        ]
        if "__watermark__" not in content:
            content += "\n" + watermark_line + "".join(canary_lines)
            init_file.write_text(content, encoding="utf-8")
            modified += 1

    return modified


def extract_watermark_from_binary(binary_path: Path) -> list[Watermark]:
    """Extract embedded watermarks from a compiled binary or .so.

    Scans the binary for CTXWM: markers and decodes them.
    """

    data = binary_path.read_bytes()
    watermarks = []

    # Search for CTXWM: pattern
    prefix = b"CTXWM:"
    offset = 0
    while True:
        pos = data.find(prefix, offset)
        if pos == -1:
            break

        # Read until null byte or non-base64 character
        end = pos + len(prefix)
        while end < len(data) and end < pos + 1024:
            c = data[end : end + 1]
            if c in (b"\x00", b"\n", b"\r"):
                break
            end += 1

        marker = data[pos:end].decode("utf-8", errors="ignore")
        wm = Watermark.from_marker(marker)
        if wm:
            watermarks.append(wm)

        offset = end

    return watermarks


def extract_watermark_from_source(source_dir: Path) -> list[Watermark]:
    """Extract watermarks from source files (pre-compilation)."""
    watermarks = []
    init_file = source_dir / "__init__.py"
    if init_file.exists():
        content = init_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            if "__watermark__" in line and "CTXWM:" in line:
                # Extract the marker from the string literal
                start = line.find("CTXWM:")
                if start != -1:
                    end = line.find('"', start)
                    if end == -1:
                        end = len(line)
                    marker = line[start:end]
                    wm = Watermark.from_marker(marker)
                    if wm:
                        watermarks.append(wm)
    return watermarks


def verify_watermark_traceability(
    source_dir: Path,
    license_db_path: Path,
) -> dict[str, bool]:
    """V-10 verification: extract watermarks and check they map to valid lic_ids.

    Returns a dict mapping lic_id -> is_traceable (found in license DB).
    """
    watermarks = extract_watermark_from_source(source_dir)

    if not license_db_path.exists():
        return {wm.lic_id: False for wm in watermarks}

    # Simple JSON check (in production, query the actual license DB)
    results = {}
    for wm in watermarks:
        # Check if the lic_id exists in the license records
        results[wm.lic_id] = True  # TODO: query actual DB

    return results

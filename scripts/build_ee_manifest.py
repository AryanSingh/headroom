#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
"""Build the cutctx_ee integrity manifest.

Scans all compiled .so/.pyd extension modules in ``cutctx_ee/``, computes
their SHA-256 hashes, and writes a signed manifest to
``cutctx_ee/MANIFEST.sha256.json``.

The manifest is HMAC-SHA256 signed with ``CUTCTX_LICENSE_HMAC_SECRET`` so it
cannot be forged by an attacker who replaces a .so file. The signature is
verified by ``cutctx.security.integrity.verify_ee_manifest()`` at EE import
time.

Usage::

    # During CI/release (after compile_ee.py):
    export CUTCTX_LICENSE_HMAC_SECRET=<production-secret>
    python scripts/build_ee_manifest.py

    # Without a secret (generates unsigned manifest for development):
    python scripts/build_ee_manifest.py --unsigned
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EE_DIR = ROOT / "cutctx_ee"
MANIFEST_PATH = EE_DIR / "MANIFEST.sha256.json"
MANIFEST_VERSION = "1"
_HMAC_SECRET_ENV = "CUTCTX_LICENSE_HMAC_SECRET"

# Extension patterns that are compiled EE modules
_SO_PATTERNS = ["*.cpython-*.so", "*.cpython-*.pyd", "*.abi3.so"]


def _find_so_files(ee_dir: Path) -> list[Path]:
    """Return all compiled extension files relative to ee_dir, sorted."""
    found: list[Path] = []
    for pattern in _SO_PATTERNS:
        found.extend(ee_dir.glob(pattern))
        # Also check billing/, audit/ etc subdirs
        found.extend(ee_dir.glob(f"**/{pattern}"))
    # Deduplicate and sort deterministically
    seen: set[Path] = set()
    result: list[Path] = []
    for p in sorted(set(found)):
        rel = p.relative_to(ee_dir)
        if rel not in seen:
            seen.add(rel)
            result.append(p)
    return result


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sign_manifest(payload: dict, secret: str) -> str:
    """Return HMAC-SHA256 hex signature of the canonical JSON payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()


def build_manifest(ee_dir: Path, secret: str | None) -> dict:
    """Scan ee_dir for .so files, hash them, build the manifest dict."""
    so_files = _find_so_files(ee_dir)
    if not so_files:
        print(
            f"WARNING: no compiled .so files found in {ee_dir}. "
            "Run scripts/compile_ee.py first.",
            file=sys.stderr,
        )

    files: dict[str, str] = {}
    for path in so_files:
        rel = str(path.relative_to(ee_dir))
        files[rel] = _sha256_file(path)
        print(f"  {rel}: {files[rel][:16]}…")

    payload: dict = {
        "version": MANIFEST_VERSION,
        "algorithm": "sha256",
        "files": files,
    }

    if secret:
        payload["signature"] = _sign_manifest(
            {k: v for k, v in payload.items() if k != "signature"},
            secret,
        )
        print(f"Manifest signed with HMAC-SHA256. {len(files)} file(s) hashed.")
    else:
        print(
            f"WARNING: manifest unsigned (no {_HMAC_SECRET_ENV}). "
            "This manifest provides hash-integrity only — it cannot prevent "
            "manifest replacement. Use a signed manifest in production.",
            file=sys.stderr,
        )

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--unsigned",
        action="store_true",
        help="Generate an unsigned manifest (development only)",
    )
    parser.add_argument(
        "--ee-dir",
        type=Path,
        default=EE_DIR,
        help=f"Path to cutctx_ee/ directory (default: {EE_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=MANIFEST_PATH,
        help=f"Output path for the manifest (default: {MANIFEST_PATH})",
    )
    args = parser.parse_args()

    secret: str | None = None
    if not args.unsigned:
        secret = os.environ.get(_HMAC_SECRET_ENV, "").strip() or None
        if not secret:
            print(
                f"ERROR: {_HMAC_SECRET_ENV} is not set. "
                "Use --unsigned for development or set the env var for production.",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Scanning {args.ee_dir} for compiled extension modules…")
    manifest = build_manifest(args.ee_dir, secret)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest written to {args.output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
"""Fail if any compiled cutctx_ee extension is older than its Python source.

Audit-2026-08-03 H1: ``cutctx_ee/*.so`` shadows the ``.py`` next to it, so a
stale build silently keeps running superseded code. Five modules had drifted —
including ``billing/client.py`` and ``trial.py``, which carry the entitlement
fail-closed fixes — and the drift went unnoticed for weeks because the
git-tracked ``MANIFEST.sha256.json`` never matched a local build anyway, so the
integrity warning it produced was permanent background noise.

Usage::

    python scripts/check_ee_freshness.py            # fail on stale artifacts
    python scripts/check_ee_freshness.py --list     # report only, always exit 0

Wire into CI and pre-commit before packaging. Exit 0 when clean or when the
tree is an uncompiled source checkout (no ``.so`` at all).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EE_DIR = ROOT / "cutctx_ee"

#: Sources that are never compiled to their own extension module.
_SKIP_NAMES = {"__init__.py"}
_SKIP_PARTS = {"__pycache__", "tests"}


def _extension_candidates(py_path: Path) -> list[Path]:
    """Return the possible compiled artifacts for ``py_path``."""
    return sorted(py_path.parent.glob(f"{py_path.stem}.*.so")) + sorted(
        py_path.parent.glob(f"{py_path.stem}.*.pyd")
    )


def find_stale(ee_dir: Path = EE_DIR) -> tuple[list[tuple[Path, Path, float]], int]:
    """Return ``(stale, compiled_count)``.

    ``stale`` holds ``(source, artifact, seconds_ahead)`` triples.
    """
    stale: list[tuple[Path, Path, float]] = []
    compiled = 0
    for py_path in sorted(ee_dir.rglob("*.py")):
        if py_path.name in _SKIP_NAMES or _SKIP_PARTS & set(py_path.parts):
            continue
        for artifact in _extension_candidates(py_path):
            compiled += 1
            delta = py_path.stat().st_mtime - artifact.stat().st_mtime
            if delta > 0:
                stale.append((py_path, artifact, delta))
    return stale, compiled


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="report only; always exit 0")
    parser.add_argument("--ee-dir", type=Path, default=EE_DIR)
    args = parser.parse_args()

    if not args.ee_dir.is_dir():
        print(f"{args.ee_dir} does not exist — nothing to check.")
        return 0

    stale, compiled = find_stale(args.ee_dir)
    if compiled == 0:
        print("No compiled cutctx_ee extensions present — source checkout, nothing to check.")
        return 0

    if not stale:
        print(f"OK: all {compiled} compiled cutctx_ee extension(s) are at least as new as source.")
        return 0

    print(
        f"STALE: {len(stale)} compiled cutctx_ee extension(s) are older than their source.\n"
        "The .so shadows the .py, so the newer source is NOT what runs.\n"
        "Rebuild with `python scripts/compile_ee.py`, then regenerate the manifest\n"
        "with `python scripts/build_ee_manifest.py`.\n",
        file=sys.stderr,
    )
    for py_path, artifact, delta in stale:
        print(
            f"  {py_path.relative_to(args.ee_dir)} is {delta / 3600:.1f}h newer than "
            f"{artifact.name}",
            file=sys.stderr,
        )
    return 0 if args.list else 1


if __name__ == "__main__":
    raise SystemExit(main())

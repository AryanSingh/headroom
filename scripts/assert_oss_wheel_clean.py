#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Leak guard: fail if OSS distribution artifacts contain proprietary code.

The open-core split (see LICENSING.md) keeps the proprietary `cutctx_ee`
package and the `packaging/` commercial build config OUT of the Apache-2.0
wheel and sdist. This script inspects built artifacts in a dist directory and
exits non-zero if any forbidden path is present, so CI and the publish
pipelines can block a leak before it ever reaches PyPI.

Usage:
    python3 scripts/assert_oss_wheel_clean.py [dist_dir]   # default: dist
"""

from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path

FORBIDDEN = ("cutctx_ee/", "packaging/")
EXPECT_PRESENT = "cutctx/entitlements.py"  # an Apache shim that SHOULD ship


def _members(path: Path) -> list[str]:
    if path.suffix in (".whl", ".zip"):
        with zipfile.ZipFile(path) as zf:
            return zf.namelist()
    if path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, "r:gz") as tf:
            return tf.getnames()
    return []


def main(argv: list[str]) -> int:
    dist = Path(argv[1]) if len(argv) > 1 else Path("dist")
    artifacts = sorted([*dist.glob("*.whl"), *dist.glob("*.tar.gz")])
    if not artifacts:
        print(f"ERROR: no .whl/.tar.gz artifacts found in {dist}/", file=sys.stderr)
        return 1

    failed = False
    for art in artifacts:
        names = _members(art)
        leaks = sorted({n for n in names if any(f in n for f in FORBIDDEN)})
        if leaks:
            failed = True
            print(f"::error::PROPRIETARY LEAK in {art.name}: {leaks[:10]}")
        elif not any(EXPECT_PRESENT in n for n in names):
            print(f"::warning::{art.name}: expected Apache shim {EXPECT_PRESENT} missing")
        else:
            print(f"OK: {art.name} — no cutctx_ee/ or packaging/ paths")

    if failed:
        print("LEAK GUARD FAILED: proprietary code present in an OSS artifact.", file=sys.stderr)
        return 1
    print(f"Leak guard passed: {len(artifacts)} artifact(s) clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

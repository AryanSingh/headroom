#!/usr/bin/env python3
"""Write immutable evidence for a validated private EE release candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release_evidence(
    wheel: Path,
    verification: dict[str, object],
    *,
    git_sha: str,
    version: str,
    created_at: datetime | None = None,
) -> dict[str, object]:
    """Bind release validation data to the exact compiled wheel bytes."""
    manifest_sha256 = verification.get("manifest_sha256")
    native_module_count = verification.get("native_module_count")
    if not isinstance(manifest_sha256, str) or not manifest_sha256:
        raise ValueError("verification result is missing manifest_sha256")
    if not isinstance(native_module_count, int) or native_module_count < 1:
        raise ValueError("verification result is missing native_module_count")

    timestamp = created_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return {
        "git_sha": git_sha,
        "version": version,
        "wheel": wheel.name,
        "wheel_sha256": _sha256_file(wheel),
        "manifest_sha256": manifest_sha256,
        "native_module_count": native_module_count,
        "created_at": timestamp.isoformat(),
        "validation": verification,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--verification", required=True, type=Path)
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        verification: dict[str, Any] = json.loads(args.verification.read_text())
        evidence = build_release_evidence(
            args.wheel,
            verification,
            git_sha=args.git_sha,
            version=args.version,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

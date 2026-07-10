"""Reproducibility metadata for published benchmark artifacts."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "schema_version",
    "git_sha",
    "python_version",
    "platform",
    "architecture",
    "packages",
    "checkpoint_id",
    "seed",
    "fixture_hashes",
    "timestamp",
    "provider_arms",
}


def _git_sha(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_release_manifest(
    *,
    root: Path,
    checkpoint_id: str,
    seed: int,
    fixture_paths: list[Path],
    provider_arms: dict[str, str],
) -> dict[str, Any]:
    """Build a serializable manifest without touching benchmark data."""
    return {
        "schema_version": 1,
        "git_sha": _git_sha(root),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "packages": {
            name: _package_version(name)
            for name in ("cutctx-ai", "llmlingua", "transformers", "torch")
        },
        "checkpoint_id": checkpoint_id,
        "seed": seed,
        "fixture_hashes": {
            str(path.relative_to(root)): _file_hash(path) for path in fixture_paths
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider_arms": provider_arms,
    }


def validate_release_manifest(payload: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS.difference(payload)
    if missing:
        raise ValueError(f"benchmark manifest missing fields: {sorted(missing)}")
    if not isinstance(payload["fixture_hashes"], dict) or not payload["fixture_hashes"]:
        raise ValueError("benchmark manifest requires fixture hashes")
    if not isinstance(payload["provider_arms"], dict):
        raise ValueError("benchmark manifest provider_arms must be a mapping")
    for arm, status in payload["provider_arms"].items():
        if status not in {"available", "unavailable"}:
            raise ValueError(f"provider arm {arm!r} has invalid status {status!r}")


def write_release_manifest(path: Path, payload: dict[str, Any]) -> None:
    validate_release_manifest(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

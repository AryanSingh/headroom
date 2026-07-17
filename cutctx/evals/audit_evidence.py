"""Build reproducible local evidence for compression and routing audits."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SMART_CRUSHER_PATH = Path("crates/cutctx-core/src/transforms/smart_crusher")


def _git_value(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _source_lines(path: Path) -> dict[str, int]:
    files = sorted(path.rglob("*.rs")) if path.is_dir() else []
    return {
        "files": len(files),
        "lines": sum(len(file.read_text(encoding="utf-8").splitlines()) for file in files),
    }


def _provider_ids(provider_specs: Iterable[Any] | None) -> list[str]:
    if provider_specs is None:
        from cutctx.orchestration.providers import builtin_provider_registry

        provider_specs = builtin_provider_registry().specs()
    return sorted(str(getattr(spec, "id", spec)) for spec in provider_specs)


def build_audit_inventory(
    *,
    root: Path,
    provider_specs: Iterable[Any] | None = None,
    git_sha: str | None = None,
    worktree_dirty: bool | None = None,
) -> dict[str, Any]:
    """Return local facts without converting them into release claims."""
    root = root.resolve()
    status = _git_value(root, "status", "--porcelain")
    resolved_dirty = status != "unavailable" and bool(status) if worktree_dirty is None else worktree_dirty
    providers = _provider_ids(provider_specs)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha or _git_value(root, "rev-parse", "HEAD"),
        "worktree_dirty": resolved_dirty,
        "provider_catalog": {
            "count": len(providers),
            "spec_ids": providers,
            "scope": "built_in_orchestration_provider_specs",
        },
        "source_inventory": {
            str(_SMART_CRUSHER_PATH): _source_lines(root / _SMART_CRUSHER_PATH),
        },
    }


def build_audit_evidence_index(*, root: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    """Bind local inventory to release evidence without masking its absence."""
    try:
        from cutctx.evals.release_evidence import evaluate_release_evidence

        release_evidence: dict[str, Any] = {
            "status": "available",
            "payload": evaluate_release_evidence(root=root),
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        release_evidence = {"status": "unavailable", "reason": str(exc)}
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inventory": inventory,
        "release_evidence": release_evidence,
    }


def write_audit_evidence(path: Path, payload: dict[str, Any]) -> None:
    """Write a stable JSON artifact for documentation and review."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

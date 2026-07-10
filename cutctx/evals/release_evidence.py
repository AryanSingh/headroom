"""Evaluate whether a release has local proof and external market-claim proof."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from cutctx.evals.release_bundle import validate_release_bundle
from cutctx.evals.release_manifest import validate_release_manifest
from cutctx.evals.partner_telemetry import validate_partner_snapshot


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _passed_artifact(path: Path) -> bool:
    try:
        return _load_json(path).get("status") == "passed"
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _rooted_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    if root.resolve() not in candidate.parents:
        raise ValueError(f"release evidence path escapes repository root: {relative_path}")
    return candidate


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_local_artifact_integrity(
    *, root: Path, manifest: dict[str, Any], bundle: dict[str, Any]
) -> None:
    for relative_path, expected_hash in manifest["fixture_hashes"].items():
        path = _rooted_path(root, relative_path)
        if not path.is_file() or _sha256(path) != expected_hash:
            raise ValueError(f"benchmark fixture hash mismatch: {relative_path}")

    for arm, report in bundle["reports"].items():
        if report["status"] != "available":
            continue
        path = _rooted_path(root, report["path"])
        if not path.is_file() or _sha256(path) != report["sha256"]:
            raise ValueError(f"benchmark report hash mismatch: {arm}")


def evaluate_release_evidence(
    *,
    root: Path,
    partner_snapshot_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Return an honest release posture without manufacturing external proof."""
    manifest = _load_json(root / "artifacts" / "benchmark-release-manifest.json")
    bundle = _load_json(root / "artifacts" / "benchmark-release-bundle.json")
    validate_release_manifest(manifest)
    validate_release_bundle(bundle)
    _validate_local_artifact_integrity(root=root, manifest=manifest, bundle=bundle)

    required_external = {
        "remote_hosted_python": root / "artifacts" / "remote-hosted-compression-smoke.json",
        "remote_hosted_typescript": root / "artifacts" / "remote-hosted-compression-smoke-typescript.json",
        "staged_gateway": root / "artifacts" / "staged-gateway-smoke.json",
        "staging_dashboard": root / "artifacts" / "staging-dashboard-smoke" / "staging-dashboard-smoke.json",
    }
    missing = [name for name, path in required_external.items() if not _passed_artifact(path)]

    valid_snapshots = 0
    for path in partner_snapshot_paths or []:
        try:
            validate_partner_snapshot(_load_json(path))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        valid_snapshots += 1
    if valid_snapshots < 2:
        missing.append("two_valid_partner_snapshots")

    return {
        "schema_version": 1,
        "local_evidence_ready": True,
        "external_evidence_ready": not missing,
        "market_claim_eligible": not missing,
        "valid_partner_snapshots": valid_snapshots,
        "missing_external_evidence": missing,
    }

from __future__ import annotations

import json
import hashlib
from pathlib import Path

from cutctx.evals.release_evidence import evaluate_release_evidence


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _local_evidence(root: Path) -> None:
    _write_json(
        root / "artifacts" / "benchmark-release-manifest.json",
        {
            "schema_version": 1,
            "git_sha": "abc",
            "python_version": "3.11",
            "platform": "test",
            "architecture": "test",
            "packages": {},
            "checkpoint_id": "model",
            "seed": 42,
            "fixture_hashes": {"fixture": "hash"},
            "timestamp": "2026-01-01T00:00:00+00:00",
            "provider_arms": {"raw_passthrough": "available"},
        },
    )
    reports = {
        arm: {"status": "available", "path": "artifact.json", "sha256": "hash"}
        for arm in ("raw_passthrough", "content_router", "verbatim_compactor", "canonical_llmlingua_xlmr_large")
    }
    reports["provider_native_cache_or_compaction"] = {"status": "unavailable", "reason": "no signal"}
    _write_json(root / "artifacts" / "benchmark-release-bundle.json", {"schema_version": 1, "reports": reports})


def test_release_evidence_is_not_market_claim_eligible_without_external_proof(tmp_path: Path) -> None:
    _local_evidence(tmp_path)

    for name in ("fixture", "artifact.json"):
        (tmp_path / name).write_text("content", encoding="utf-8")
    manifest_path = tmp_path / "artifacts" / "benchmark-release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(b"content").hexdigest()
    manifest["fixture_hashes"] = {"fixture": expected_hash}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    bundle_path = tmp_path / "artifacts" / "benchmark-release-bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    for report in bundle["reports"].values():
        if report["status"] == "available":
            report["sha256"] = expected_hash
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    payload = evaluate_release_evidence(root=tmp_path)

    assert payload["local_evidence_ready"] is True
    assert payload["market_claim_eligible"] is False
    assert "remote_hosted_python" in payload["missing_external_evidence"]
    assert "staging_dashboard" in payload["missing_external_evidence"]
    assert "two_valid_partner_snapshots" in payload["missing_external_evidence"]


def test_release_evidence_rejects_hash_mismatch(tmp_path: Path) -> None:
    _local_evidence(tmp_path)

    try:
        evaluate_release_evidence(root=tmp_path)
    except ValueError as exc:
        assert "hash mismatch" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected evidence integrity failure")

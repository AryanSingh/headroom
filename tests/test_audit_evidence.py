from __future__ import annotations

import json
from pathlib import Path


def test_audit_inventory_records_provider_catalog_source_lines_and_dirty_state(
    tmp_path: Path,
) -> None:
    from cutctx.evals.audit_evidence import build_audit_inventory

    source = tmp_path / "crates" / "cutctx-core" / "src" / "transforms" / "smart_crusher"
    source.mkdir(parents=True)
    (source / "one.rs").write_text("one\ntwo\n", encoding="utf-8")
    (source / "two.rs").write_text("three\n", encoding="utf-8")

    inventory = build_audit_inventory(
        root=tmp_path,
        provider_specs=["openai", "anthropic"],
        git_sha="abc123",
        worktree_dirty=True,
    )

    assert inventory["schema_version"] == 1
    assert inventory["git_sha"] == "abc123"
    assert inventory["worktree_dirty"] is True
    assert inventory["provider_catalog"] == {
        "count": 2,
        "spec_ids": ["anthropic", "openai"],
        "scope": "built_in_orchestration_provider_specs",
    }
    assert inventory["source_inventory"]["crates/cutctx-core/src/transforms/smart_crusher"] == {
        "files": 2,
        "lines": 3,
    }


def test_audit_evidence_index_marks_missing_release_artifacts_unavailable(tmp_path: Path) -> None:
    from cutctx.evals.audit_evidence import build_audit_evidence_index

    inventory = {
        "schema_version": 1,
        "git_sha": "abc123",
        "worktree_dirty": False,
        "provider_catalog": {"count": 0, "spec_ids": [], "scope": "test"},
        "source_inventory": {},
    }

    index = build_audit_evidence_index(root=tmp_path, inventory=inventory)

    assert index["schema_version"] == 1
    assert index["inventory"] == inventory
    assert index["release_evidence"]["status"] == "unavailable"
    assert "benchmark-release-manifest.json" in index["release_evidence"]["reason"]


def test_write_audit_evidence_creates_stable_json_artifact(tmp_path: Path) -> None:
    from cutctx.evals.audit_evidence import write_audit_evidence

    output = tmp_path / "artifacts" / "audit-evidence.json"
    write_audit_evidence(output, {"schema_version": 1, "value": "verified"})

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "value": "verified",
    }

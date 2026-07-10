from __future__ import annotations

import json
from pathlib import Path

import pytest

from cutctx.evals.release_bundle import (
    CANONICAL_LLMLINGUA_CHECKPOINT,
    build_release_bundle,
    validate_release_bundle,
)


def _write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_release_bundle_binds_named_reports_to_hashed_artifacts(tmp_path: Path) -> None:
    _write_report(tmp_path / "artifacts" / "raw-passthrough-benchmark.json", {"results": []})
    _write_report(tmp_path / "artifacts" / "benchmark-breadth.json", {"results": []})
    _write_report(tmp_path / "artifacts" / "verbatim-compaction-benchmark.json", {"results": []})
    _write_report(
        tmp_path / "artifacts" / "llmlingua-research-preset.json",
        {"metadata": {"llmlingua_model": CANONICAL_LLMLINGUA_CHECKPOINT}, "totals": {"errors": 0}},
    )

    payload = build_release_bundle(tmp_path)

    validate_release_bundle(payload)
    assert payload["reports"]["content_router"]["sha256"]
    assert payload["reports"]["provider_native_cache_or_compaction"]["status"] == "unavailable"


def test_release_bundle_rejects_noncanonical_or_error_llmlingua_report(tmp_path: Path) -> None:
    _write_report(tmp_path / "artifacts" / "raw-passthrough-benchmark.json", {})
    _write_report(tmp_path / "artifacts" / "benchmark-breadth.json", {})
    _write_report(tmp_path / "artifacts" / "verbatim-compaction-benchmark.json", {})
    _write_report(
        tmp_path / "artifacts" / "llmlingua-research-preset.json",
        {"metadata": {"llmlingua_model": "wrong"}, "totals": {"errors": 1}},
    )

    with pytest.raises(ValueError, match="XLM-R-large"):
        build_release_bundle(tmp_path)

"""Validate the named evidence arms attached to a benchmark release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CANONICAL_LLMLINGUA_CHECKPOINT = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"
REQUIRED_REPORT_ARMS = {
    "raw_passthrough",
    "content_router",
    "verbatim_compactor",
    "canonical_llmlingua_xlmr_large",
    "provider_native_cache_or_compaction",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"benchmark artifact {path} must contain a JSON object")
    return payload


def build_release_bundle(root: Path) -> dict[str, Any]:
    """Bind each public comparison arm to a real artifact or explicit absence."""
    artifacts = {
        "raw_passthrough": root / "artifacts" / "raw-passthrough-benchmark.json",
        "content_router": root / "artifacts" / "benchmark-breadth.json",
        "verbatim_compactor": root / "artifacts" / "verbatim-compaction-benchmark.json",
        "canonical_llmlingua_xlmr_large": root / "artifacts" / "llmlingua-research-preset.json",
    }
    loaded = {arm: _read_json(path) for arm, path in artifacts.items()}
    llmlingua_metadata = loaded["canonical_llmlingua_xlmr_large"].get("metadata", {})
    if llmlingua_metadata.get("llmlingua_model") != CANONICAL_LLMLINGUA_CHECKPOINT:
        raise ValueError("canonical LLMLingua report does not identify the XLM-R-large checkpoint")
    totals = loaded["canonical_llmlingua_xlmr_large"].get("totals", {})
    if not isinstance(totals, dict) or int(totals.get("errors", -1)) != 0:
        raise ValueError("canonical LLMLingua report contains fallback or error cells")

    reports: dict[str, dict[str, Any]] = {
        **{
            arm: {
                "status": "available",
                "path": str(path.relative_to(root)),
                "sha256": _sha256(path),
            }
            for arm, path in artifacts.items()
        },
        "provider_native_cache_or_compaction": {
            "status": "unavailable",
            "reason": "No provider-native signal was supplied by the evaluated provider.",
        },
    }
    return {
        "schema_version": 1,
        "reports": reports,
    }


def validate_release_bundle(payload: dict[str, Any]) -> None:
    reports = payload.get("reports")
    if not isinstance(reports, dict) or set(reports) != REQUIRED_REPORT_ARMS:
        raise ValueError("release bundle must include every named benchmark arm")
    for arm, report in reports.items():
        if report.get("status") not in {"available", "unavailable"}:
            raise ValueError(f"benchmark arm {arm!r} has an invalid status")
        if report["status"] == "available":
            if not isinstance(report.get("sha256"), str) or not report.get("path"):
                raise ValueError(f"available benchmark arm {arm!r} needs a hashed artifact path")
        if report["status"] == "unavailable" and not report.get("reason"):
            raise ValueError(f"unavailable benchmark arm {arm!r} needs an explicit reason")


def write_release_bundle(path: Path, payload: dict[str, Any]) -> None:
    validate_release_bundle(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

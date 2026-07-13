from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from cutctx.evals.release_manifest import (
    build_release_manifest,
    require_clean_checkout,
    validate_release_manifest,
    write_release_manifest,
)


def test_release_manifest_records_reproducibility_inputs(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.txt"
    fixture.write_text("fixture", encoding="utf-8")
    payload = build_release_manifest(
        root=tmp_path,
        checkpoint_id="microsoft/test-checkpoint",
        seed=42,
        fixture_paths=[fixture],
        provider_arms={"raw_passthrough": "available", "provider_native": "unavailable"},
    )

    validate_release_manifest(payload)
    output = tmp_path / "manifest.json"
    write_release_manifest(output, payload)
    assert "fixture.txt" in output.read_text(encoding="utf-8")
    assert payload["fixture_hashes"]["fixture.txt"]


def test_release_manifest_rejects_unknown_provider_status() -> None:
    payload = dict.fromkeys(
        (
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
        ),
        "value",
    )
    payload["fixture_hashes"] = {"fixture": "hash"}
    payload["provider_arms"] = {"native": "simulated"}

    try:
        validate_release_manifest(payload)
    except ValueError as exc:
        assert "invalid status" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected validation failure")


def test_release_manifest_requires_clean_git_checkout(tmp_path: Path) -> None:
    with patch(
        "cutctx.evals.release_manifest.subprocess.check_output", return_value=" M proxy.py\n"
    ):
        with pytest.raises(ValueError, match="clean checkout"):
            require_clean_checkout(tmp_path)


def test_release_manifest_reports_clean_git_revision(tmp_path: Path) -> None:
    with patch(
        "cutctx.evals.release_manifest.subprocess.check_output",
        side_effect=["", "abc123\n"],
    ):
        assert require_clean_checkout(tmp_path) == "abc123"

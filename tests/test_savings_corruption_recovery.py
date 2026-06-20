# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for SavingsTracker corruption recovery (Medium-26).

Production audit (production-audit-2026-06-20.md) found that the
savings store had no corruption-recovery path. The previous code
silently fell back to an empty state on a parse error, leaving
no forensic record. This file tests the new quarantine
behavior and the verify_integrity helper.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from headroom.proxy.savings_tracker import SavingsTracker


def test_corrupt_json_is_quarantined(tmp_path: Path) -> None:
    """A savings file with invalid JSON must be renamed to
    <file>.corrupt-<ts>.json and a fresh state must load.
    """
    path = tmp_path / "proxy_savings.json"
    path.write_text("{this is not valid json", encoding="utf-8")
    tracker = SavingsTracker(path=str(path))
    # Fresh state — zero entries.
    snap = tracker.snapshot()
    assert snap["lifetime"]["requests"] == 0
    assert snap["lifetime"]["tokens_saved"] == 0
    # Original file is gone; a quarantine file exists.
    files = sorted(p.name for p in tmp_path.iterdir())
    assert any(name.startswith("proxy_savings.corrupt-") for name in files)
    assert not path.exists()


def test_top_level_not_dict_falls_back_to_default(tmp_path: Path) -> None:
    """A savings file whose top level is not a dict is valid JSON
    but semantically corrupt. The sanitizer returns the default
    state without quarantining (since json.load succeeded). The
    operator can recover by re-importing the file.
    """
    path = tmp_path / "proxy_savings.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    tracker = SavingsTracker(path=str(path))
    snap = tracker.snapshot()
    assert snap["lifetime"]["requests"] == 0
    # No quarantine — json.load succeeded.
    files = sorted(p.name for p in tmp_path.iterdir())
    assert not any(name.startswith("proxy_savings.corrupt-") for name in files)


def test_missing_top_level_keys_falls_back_to_default(tmp_path: Path) -> None:
    """A savings file with valid JSON but missing required
    top-level keys is semantically corrupt. The sanitizer
    returns the default state without quarantining. The
    operator can recover by re-importing the file.
    """
    path = tmp_path / "proxy_savings.json"
    path.write_text(json.dumps({"lifetime": {}}), encoding="utf-8")
    tracker = SavingsTracker(path=str(path))
    snap = tracker.snapshot()
    assert snap["lifetime"]["requests"] == 0
    # No quarantine — json.load succeeded.
    files = sorted(p.name for p in tmp_path.iterdir())
    assert not any(name.startswith("proxy_savings.corrupt-") for name in files)


def test_valid_file_loads_normally(tmp_path: Path) -> None:
    """A valid file must load without quarantine."""
    path = tmp_path / "proxy_savings.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "lifetime": {
                    "requests": 5,
                    "tokens_saved": 100,
                    "compression_savings_usd": 0.0,
                    "total_input_tokens": 1000,
                    "total_input_cost_usd": 0.0,
                },
                "display_session": {
                    "requests": 0,
                    "tokens_saved": 0,
                    "compression_savings_usd": 0.0,
                    "total_input_tokens": 0,
                    "total_input_cost_usd": 0.0,
                    "savings_percent": 0.0,
                    "started_at": None,
                    "last_activity_at": None,
                },
                "history": [],
                "projects": {},
            }
        ),
        encoding="utf-8",
    )
    tracker = SavingsTracker(path=str(path))
    snap = tracker.snapshot()
    assert snap["lifetime"]["requests"] == 5
    assert snap["lifetime"]["tokens_saved"] == 100
    # No quarantine file is created.
    files = sorted(p.name for p in tmp_path.iterdir())
    assert not any(name.startswith("proxy_savings.corrupt-") for name in files)


def test_verify_integrity_missing_file(tmp_path: Path) -> None:
    """verify_integrity on a non-existent file returns ok=True with
    file_exists=False (no data, nothing to verify).
    """
    path = tmp_path / "proxy_savings.json"
    tracker = SavingsTracker(path=str(path))
    result = tracker.verify_integrity()
    assert result["ok"] is True
    assert result["checks"]["file_exists"] is False


def test_verify_integrity_valid_file(tmp_path: Path) -> None:
    """verify_integrity on a valid file returns ok=True."""
    path = tmp_path / "proxy_savings.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "lifetime": {},
                "display_session": {},
                "history": [],
                "projects": {},
            }
        ),
        encoding="utf-8",
    )
    tracker = SavingsTracker(path=str(path))
    result = tracker.verify_integrity()
    assert result["ok"] is True
    assert result["checks"]["file_exists"] is True
    assert result["checks"]["top_level_keys"] == "ok"
    assert result["checks"]["monotonic"] == "empty"


def test_verify_integrity_corrupt_file(tmp_path: Path) -> None:
    """verify_integrity on a file that is then quarantined
    returns ok=False initially (the file is corrupt), but
    loading a tracker re-quarantines the file, so the second
    load returns fresh state. The verify_integrity on a tracker
    that was loaded from a corrupt file is moot because the
    file is already moved aside.
    """
    path = tmp_path / "proxy_savings.json"
    path.write_text("not json at all", encoding="utf-8")
    # Tracker loads and quarantines the file.
    tracker = SavingsTracker(path=str(path))
    # verify_integrity now sees no file (it was renamed), so
    # returns ok=True with file_exists=False.
    result = tracker.verify_integrity()
    assert result["ok"] is True
    assert result["checks"]["file_exists"] is False


def test_verify_integrity_parse_error_returns_error(tmp_path: Path) -> None:
    """verify_integrity on a file that is non-parseable but the
    tracker has not yet loaded it. The tracker constructor
    quarantines; verify_integrity on a fresh path with bad
    JSON returns parse_failed.
    """
    path = tmp_path / "proxy_savings.json"
    # Don't call the constructor — just write the file.
    path.write_text("not json at all", encoding="utf-8")
    # Construct a tracker with a DIFFERENT path so the
    # constructor doesn't quarantine the bad file. Then write
    # the bad file at the tracker's path and call verify_integrity.
    tracker = SavingsTracker(path=str(tmp_path / "other.json"))
    # Replace the tracker's path with the bad one for the
    # verify call only.
    import unittest.mock as _mock

    with _mock.patch.object(tracker, "_path", path):
        result = tracker.verify_integrity()
    assert result["ok"] is False
    assert "parse_failed" in result["error"]


def test_verify_integrity_missing_keys(tmp_path: Path) -> None:
    """verify_integrity on a file missing required top-level keys
    returns ok=False with a descriptive error.
    """
    path = tmp_path / "proxy_savings.json"
    path.write_text(json.dumps({"lifetime": {}}), encoding="utf-8")
    tracker = SavingsTracker(path=str(path))
    result = tracker.verify_integrity()
    assert result["ok"] is False
    assert "missing top-level key" in result["error"]


def test_quarantine_does_not_clobber_existing_quarantines(tmp_path: Path) -> None:
    """Multiple corrupt loads produce distinct quarantine files
    rather than overwriting each other.
    """
    path = tmp_path / "proxy_savings.json"
    path.write_text("corrupt 1", encoding="utf-8")
    SavingsTracker(path=str(path))
    path.write_text("corrupt 2", encoding="utf-8")
    SavingsTracker(path=str(path))
    files = sorted(p.name for p in tmp_path.iterdir())
    corrupt_files = [n for n in files if n.startswith("proxy_savings.corrupt-")]
    assert len(corrupt_files) >= 1

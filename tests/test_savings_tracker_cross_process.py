# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests that SavingsTracker instances sharing a storage path see each
other's writes live, without a restart.

Two cutctx proxy processes (e.g. a persistent shared deployment plus an
auto-reassigned private port for a session that needs an upstream
override) both write to the same `~/.cutctx/proxy_savings.json`. Before
this fix, each process's SavingsTracker loaded state once at __init__ and
never re-read the file, so: (1) Attribution/lifetime totals on one
process's dashboard never reflected the other process's requests, and (2)
a write from one process could clobber the other's already-persisted
totals by saving from a stale in-memory base.
"""

from __future__ import annotations

from pathlib import Path

from cutctx.proxy.savings_tracker import SavingsTracker


def test_snapshot_sees_writes_from_a_second_tracker_instance(tmp_path: Path) -> None:
    path = tmp_path / "proxy_savings.json"
    tracker_a = SavingsTracker(path=str(path))
    tracker_b = SavingsTracker(path=str(path))

    tracker_a.record_compression_savings(model="claude-sonnet-4-6", tokens_saved=100)

    snap_b = tracker_b.snapshot()
    assert snap_b["lifetime"]["tokens_saved"] == 100


def test_writes_from_two_trackers_accumulate_instead_of_clobbering(tmp_path: Path) -> None:
    path = tmp_path / "proxy_savings.json"
    tracker_a = SavingsTracker(path=str(path))
    tracker_b = SavingsTracker(path=str(path))

    tracker_a.record_compression_savings(model="claude-sonnet-4-6", tokens_saved=100)
    tracker_b.record_compression_savings(model="claude-sonnet-4-6", tokens_saved=50)

    assert tracker_a.snapshot()["lifetime"]["tokens_saved"] == 150
    assert tracker_b.snapshot()["lifetime"]["tokens_saved"] == 150

    tracker_a.record_compression_savings(model="claude-sonnet-4-6", tokens_saved=25)
    assert tracker_b.snapshot()["lifetime"]["tokens_saved"] == 175

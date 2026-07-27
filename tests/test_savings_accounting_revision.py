"""Pre-v8 savings figures must be marked, and the mark must survive a restart.

Everything recorded before schema v8 counted "tokens" as ``len(text.split())``
— whitespace words, not BPE. On whitespace-poor output the two diverge wildly,
so those figures overstate compression and in the worst case recorded a saving
on a swap that actually grew the payload.

There is nothing to recompute: the original payloads are gone and only the
aggregate survives. Restating them would be a guess and deleting them would
destroy a customer's history, so they are kept and flagged, and the dashboard
renders the caveat next to them.

The subtle half of this is persistence. ``_snapshot_locked`` builds the dict
that gets written to disk and stamps the CURRENT ``schema_version``. It used
to drop the provenance keys, which wrote "already migrated" without the note
saying what the migration did — so the next load skipped the migration and the
caveat was gone after a single restart. That applied to the pre-existing v6/v7
markers too.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cutctx.proxy.savings_tracker import SCHEMA_VERSION, SavingsTracker


def _legacy_state(schema_version: int = 7, rows: int = 5) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "schema_version": schema_version,
        "lifetime": {"requests": 480, "tokens_saved": 1_250_000},
        "history": [
            {
                "timestamp": (now - timedelta(days=d)).isoformat(),
                "total_tokens_saved": 40_000,
                "compression_savings_usd": 0.9,
            }
            for d in range(rows, 0, -1)
        ],
    }


def _write(tmp_path: Path, state: dict) -> str:
    path = tmp_path / "proxy_savings.json"
    path.write_text(json.dumps(state))
    return str(path)


def test_pre_v8_state_is_marked(tmp_path: Path) -> None:
    tracker = SavingsTracker(path=_write(tmp_path, _legacy_state(rows=5)))

    revision = tracker._state.get("accounting_revision")

    assert revision is not None, "pre-v8 savings were left presented as accurate"
    assert revision["schema_version"] == 8
    assert revision["legacy_history_rows"] == 5
    assert revision["boundary_timestamp"] is not None


def test_marking_does_not_destroy_the_customers_history(tmp_path: Path) -> None:
    """Flag the numbers; never quietly delete or restate them."""
    tracker = SavingsTracker(path=_write(tmp_path, _legacy_state(rows=5)))

    assert len(tracker._state["history"]) == 5
    assert tracker._state["lifetime"]["tokens_saved"] == 1_250_000


def test_fresh_install_is_not_marked(tmp_path: Path) -> None:
    """A new user has no legacy data and must not see the caveat."""
    tracker = SavingsTracker(path=str(tmp_path / "new.json"))

    assert "accounting_revision" not in tracker._state


def test_marker_reaches_the_stats_history_endpoint(tmp_path: Path) -> None:
    """The dashboard reads /stats-history; a marker it can't see is useless."""
    tracker = SavingsTracker(path=_write(tmp_path, _legacy_state()))

    assert "accounting_revision" in tracker.history_response()


def test_marker_survives_a_restart(tmp_path: Path) -> None:
    """The regression that made this a one-shot notice.

    Persisting bumped schema_version while dropping the note, so the reload
    saw an up-to-date schema, skipped the migration, and lost the caveat.
    """
    path = _write(tmp_path, _legacy_state())

    first = SavingsTracker(path=path)
    first._persist_snapshot(first._snapshot_locked())

    on_disk = json.loads(Path(path).read_text())
    assert on_disk["schema_version"] == SCHEMA_VERSION
    assert "accounting_revision" in on_disk, "marker was not persisted"

    second = SavingsTracker(path=path)
    assert "accounting_revision" in second._state
    assert "accounting_revision" in second.history_response()


@pytest.mark.parametrize("key", ["attribution_note", "attribution_reconciliation"])
def test_earlier_provenance_markers_also_survive_persistence(tmp_path: Path, key: str) -> None:
    """The same drop silently erased the v6 and v7 notices."""
    state = _legacy_state(schema_version=SCHEMA_VERSION)
    state[key] = {"schema_version": 7, "note": "example", "fields": {}}
    path = _write(tmp_path, state)

    tracker = SavingsTracker(path=path)
    tracker._persist_snapshot(tracker._snapshot_locked())

    assert key in json.loads(Path(path).read_text())

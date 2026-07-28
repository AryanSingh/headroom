"""The ROI report must sum deltas, never cumulative counters.

`cutctx report buyer` is the number a buyer sees. It was reporting
**$1,740,947.38 saved in 30 days** against a lifetime ledger of ~$12,000 —
overstated by roughly 1,400x.

The collector fell back from a per-request delta to the lifetime counter
sitting beside it:

    raw.get("delta_cache_savings_usd") or raw.get("cache_savings_usd", 0.0)

`cache_savings_usd` is monotonic — $10,794 on the first history row and
$12,000 on the last. 1,006 of 5,000 real rows carried no delta, substituted
that running total, and the report summed them.

Under-reporting a row that recorded nothing is survivable. Showing a buyer a
figure four orders of magnitude wrong is not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cutctx.cli.report import _collect_savings_history
from cutctx.proxy.savings_tracker import SCHEMA_VERSION


def _history(rows: int = 40, *, with_deltas: int = 0) -> dict:
    """Rows carrying a monotonic cumulative counter, like the real ledger."""
    history = []
    running = 10_000.0
    for i in range(rows):
        running += 0.50  # the cumulative counter climbs
        row = {
            "timestamp": f"2026-07-2{(i % 8) + 1}T10:00:00Z",
            "model": "gpt-5.6-terra",
            "cache_savings_usd": running,  # CUMULATIVE — never summable
            "compression_savings_usd": running / 2,
            "total_tokens_saved": 1_000_000 + i,
        }
        if i < with_deltas:
            row["delta_cache_savings_usd"] = 0.50
            row["delta_savings_usd"] = 0.25
            row["delta_tokens_saved"] = 100
        history.append(row)
    return {"schema_version": SCHEMA_VERSION, "history": history}


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def _write(payload: dict) -> None:
        path = tmp_path / "proxy_savings.json"
        path.write_text(json.dumps(payload))
        monkeypatch.setattr(
            "cutctx.proxy.savings_tracker.get_default_savings_storage_path",
            lambda: str(path),
        )

    return _write


def test_rows_without_deltas_contribute_nothing(ledger) -> None:
    """The regression: 40 rows x a ~$10,000 counter must not read as $400,000."""
    ledger(_history(rows=40, with_deltas=0))

    rows = _collect_savings_history(days=3650)

    assert len(rows) == 40
    assert sum(r["cache_savings_usd"] for r in rows) == 0.0
    assert sum(r["compression_savings_usd"] for r in rows) == 0.0
    assert sum(r["tokens_saved"] for r in rows) == 0


def test_deltas_are_summed_exactly(ledger) -> None:
    ledger(_history(rows=10, with_deltas=10))

    rows = _collect_savings_history(days=3650)

    assert sum(r["cache_savings_usd"] for r in rows) == pytest.approx(5.00)
    assert sum(r["compression_savings_usd"] for r in rows) == pytest.approx(2.50)
    assert sum(r["tokens_saved"] for r in rows) == 1000


def test_mixed_rows_count_only_the_deltas(ledger) -> None:
    """The real ledger shape: most rows have deltas, some do not."""
    ledger(_history(rows=50, with_deltas=30))

    rows = _collect_savings_history(days=3650)

    assert sum(r["cache_savings_usd"] for r in rows) == pytest.approx(15.00)
    # 20 delta-less rows carried a ~$10,000 counter each; none of it leaks in.
    assert sum(r["cache_savings_usd"] for r in rows) < 100.0


def test_cost_savings_does_not_double_count_the_source_breakdown(ledger) -> None:
    """`savings_by_source_usd` is a breakdown OF the deltas, not an addition.

    Summing both counted every attributed request twice.
    """
    payload = _history(rows=1, with_deltas=1)
    payload["history"][0]["savings_by_source_usd"] = {
        "provider_prompt_cache": 0.50,
        "cutctx_compression": 0.25,
    }
    ledger(payload)

    row = _collect_savings_history(days=3650)[0]

    # delta_savings_usd (0.25) + delta_cache_savings_usd (0.50) = 0.75
    assert row["cost_savings_usd"] == pytest.approx(0.75)

"""Regression tests for audit C7 — eight different "tokens saved" totals.

Each test here pins one of the five root causes:

* RC-1 ``--days`` was structurally inert: the ring buffer never retained a
  row before the window start, the cumulative baseline stayed 0, and every
  window silently collapsed to all-time.
* RC-2 ``requests_total`` was the ring-buffer size, and the ROI denominator
  did not cover the same period as its numerator.
* RC-3 three accumulators measured different physical quantities with no
  reconciling invariant, and provider prompt-cache reads were presented as
  Cutctx savings.
* RC-4 ``/stats`` interleaved since-restart and lifetime scopes in one
  unlabelled payload.
* RC-5 ``report agent-context`` printed two contradictory totals side by
  side.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from click.testing import CliRunner

from cutctx.cli.report import (
    _build_agent_context_report,
    _render_agent_context_report,
    build_buyer_report_payload,
)
from cutctx.cli.savings import _compute_summary
from cutctx.proxy.savings_tracker import (
    PROVIDER_NATIVE_SAVINGS_SOURCES,
    SavingsTracker,
    split_savings_by_attribution,
)


def _tracker(tmp_path, **kwargs) -> SavingsTracker:
    return SavingsTracker(path=str(tmp_path / "proxy_savings.json"), **kwargs)


def _record(
    tracker: SavingsTracker,
    *,
    when: datetime,
    cutctx: int,
    cache: int,
    input_tokens: int = 10_000,
) -> None:
    sources = {}
    if cache:
        sources["provider_prompt_cache"] = cache
    if cutctx:
        sources["cutctx_compression"] = cutctx
    tracker.record_request(
        model="gpt-4o",
        provider="openai",
        input_tokens=input_tokens,
        tokens_saved=cutctx + cache,
        timestamp=when,
        savings_by_source_tokens=sources,
    )


# ---------------------------------------------------------------------------
# RC-1: a window that retained history cannot answer must say so.
# ---------------------------------------------------------------------------


def test_rc1_unanswerable_window_is_labelled_not_silently_all_time(tmp_path):
    """A trimmed ring buffer must not return all-time under a window label."""
    tracker = _tracker(tmp_path, max_history_points=3)
    now = datetime.now(timezone.utc)
    for age_hours in (200, 150, 100, 2, 1):
        _record(tracker, when=now - timedelta(hours=age_hours), cutctx=1_000, cache=5_000)

    all_time = tracker.get_summary_stats()
    windowed = tracker.get_summary_stats(start_time=now - timedelta(days=30))

    # The window is unanswerable: rows older than the retained slice are gone.
    assert windowed["window_covered"] is False
    assert windowed["scope"] == "window_partial_retained_history"
    assert "Insufficient history" in windowed["window_note"]
    assert windowed["history_coverage"]["history_points_dropped"] == 2
    assert windowed["history_coverage"]["history_complete"] is False
    # ...and it must report the retained lower bound, not the all-time total.
    assert windowed["total_tokens_saved"] < all_time["total_tokens_saved"]
    assert all_time["scope"] == "all_time"
    assert all_time["window_covered"] is True


def test_rc1_distinct_windows_return_distinct_totals(tmp_path):
    """--days 1 and --days 7 must not return the same number by construction."""
    tracker = _tracker(tmp_path)
    now = datetime.now(timezone.utc)
    _record(tracker, when=now - timedelta(days=5), cutctx=7_000, cache=1_000)
    _record(tracker, when=now - timedelta(hours=1), cutctx=3_000, cache=1_000)

    one_day = tracker.get_summary_stats(start_time=now - timedelta(days=1))
    seven_days = tracker.get_summary_stats(start_time=now - timedelta(days=7))

    assert one_day["total_tokens_saved"] == 3_000
    assert seven_days["total_tokens_saved"] == 10_000
    assert one_day["window_covered"] is True
    assert seven_days["window_covered"] is True


def test_rc1_untrimmed_history_answers_any_window(tmp_path):
    tracker = _tracker(tmp_path)
    now = datetime.now(timezone.utc)
    _record(tracker, when=now - timedelta(hours=2), cutctx=500, cache=100)

    stats = tracker.get_summary_stats(start_time=now - timedelta(days=365))
    assert stats["window_covered"] is True
    assert stats["scope"] == "window"
    assert stats["history_coverage"]["history_complete"] is True


# ---------------------------------------------------------------------------
# RC-2: real request counts, and an ROI whose numerator and denominator
# cover the same period.
# ---------------------------------------------------------------------------


def test_rc2_buyer_payload_uses_real_request_count_not_row_count():
    rows = [
        {"savings_by_source_tokens": {"cutctx_compression": 100}, "compressed": True},
        {"savings_by_source_tokens": {"provider_prompt_cache": 50}, "compressed": False},
    ]
    payload = build_buyer_report_payload(rows, requests_total=139_372, scope="all_time")

    assert payload["requests_total"] == 139_372
    assert payload["requests_rows_observed"] == 2
    assert payload["rates_measured_over_requests"] == 2
    # Rates stay measured over the rows we actually have.
    assert payload["all_traffic_compression_rate"] == pytest.approx(0.5)
    assert "different denominators" in payload["request_count_note"]
    assert payload["scope"] == "all_time"


def test_rc2_all_time_roi_is_not_priced_against_one_day(tmp_path):
    """`--days 0` used to divide an all-time numerator by a 1-day denominator."""

    class _Storage:
        def __init__(self, started_at):
            self._started_at = started_at

        def get_summary_stats(self, start_time=None, end_time=None):
            return {
                "total_requests": 100_000,
                "total_tokens_before": 1_000_000_000,
                "total_tokens_after": 900_000_000,
                "total_tokens_saved": 100_000_000,
                "scope": "all_time",
                "window_covered": True,
                "lifetime_requests": 100_000,
                "lifetime_started_at": self._started_at,
                "savings_by_source_tokens": {"cutctx_compression": 100_000_000},
                "cutctx_attributable_tokens_saved": 100_000_000,
                "provider_native_tokens_saved": 0,
            }

        def close(self):
            pass

    started = (datetime.now(timezone.utc) - timedelta(days=300)).isoformat()
    summary = _compute_summary(_Storage(started), days=0)
    assert summary["roi_period_basis"] == "ledger_start_to_now"
    assert summary["roi_period_days"] == pytest.approx(300, abs=1)
    # A 300-day period must be priced against ~10 months of subscription.
    assert summary["plan_cost_for_period"] == pytest.approx(49.0 * 300 / 30, rel=1e-3)

    # No ledger start date -> no denominator -> no ROI. Never a guess.
    unknown = _compute_summary(_Storage(None), days=0)
    assert unknown["roi"] is None
    assert unknown["roi_period_basis"] == "unknown_ledger_start"
    assert "not computable" in unknown["roi_note"]


def test_rc2_ledger_start_date_is_never_backfilled_onto_existing_history(tmp_path):
    """A start date stamped on a populated ledger would fake a huge ROI."""
    path = tmp_path / "proxy_savings.json"
    tracker = SavingsTracker(path=str(path))
    now = datetime.now(timezone.utc)
    _record(tracker, when=now - timedelta(days=40), cutctx=1_000, cache=0)
    tracker.flush()

    # Simulate a ledger that predates the start-date field entirely.
    raw = json.loads(path.read_text())
    raw["lifetime"].pop("first_recorded_at", None)
    path.write_text(json.dumps(raw))

    reopened = SavingsTracker(path=str(path))
    _record(reopened, when=now - timedelta(minutes=1), cutctx=1_000, cache=0)
    lifetime = reopened.snapshot()["lifetime"]
    assert "first_recorded_at" not in lifetime, (
        "a start date invented today would price 40 days of savings as one minute"
    )
    assert reopened.get_summary_stats()["lifetime_started_at"] is None

    # An implausible value already on disk must be discarded, not divided by.
    raw = json.loads(path.read_text())
    raw["lifetime"]["first_recorded_at"] = now.isoformat()
    path.write_text(json.dumps(raw))
    assert SavingsTracker(path=str(path)).get_summary_stats()["lifetime_started_at"] is None


def test_rc2_windowed_roi_denominator_matches_the_window(tmp_path):
    tracker = _tracker(tmp_path)
    now = datetime.now(timezone.utc)
    _record(tracker, when=now - timedelta(hours=3), cutctx=300_000, cache=0, input_tokens=1_000_000)

    class _Adapter:
        def get_summary_stats(self, start_time=None, end_time=None):
            return tracker.get_summary_stats(start_time=start_time, end_time=end_time)

        def close(self):
            pass

    thirty = _compute_summary(_Adapter(), days=30)
    seven = _compute_summary(_Adapter(), days=7)
    assert thirty["roi_period_days"] == 30.0
    assert seven["roi_period_days"] == 7.0
    assert thirty["plan_cost_for_period"] == pytest.approx(49.0)
    # Same savings, shorter period -> higher monthly-equivalent ROI.
    assert seven["roi"] > thirty["roi"]


# ---------------------------------------------------------------------------
# RC-3: provider-native vs Cutctx-attributable, with an enforced invariant.
# ---------------------------------------------------------------------------


def test_rc3_provider_prompt_cache_is_never_a_cutctx_claim(tmp_path):
    tracker = _tracker(tmp_path)
    now = datetime.now(timezone.utc)
    _record(tracker, when=now - timedelta(minutes=5), cutctx=1_000, cache=9_000)

    stats = tracker.get_summary_stats()
    assert stats["cutctx_attributable_tokens_saved"] == 1_000
    assert stats["provider_native_tokens_saved"] == 9_000
    # The headline is the Cutctx figure, not the 10,000 combined total.
    assert stats["total_tokens_saved"] == 1_000
    assert stats["attribution"]["headline_basis"] == "cutctx_attributable_tokens"
    assert "provider_prompt_cache" in PROVIDER_NATIVE_SAVINGS_SOURCES


def test_rc3_attribution_invariant_is_enforced_on_every_write(tmp_path):
    tracker = _tracker(tmp_path)
    now = datetime.now(timezone.utc)
    _record(tracker, when=now - timedelta(minutes=9), cutctx=1_000, cache=9_000)
    _record(tracker, when=now - timedelta(minutes=8), cutctx=0, cache=4_000)

    accounting = tracker.savings_accounting()
    assert accounting["invariant_ok"] is True
    assert accounting["invariant_violations"] == 0
    assert (
        accounting["cutctx_attributable_tokens"] + accounting["provider_native_tokens"]
        == accounting["by_source_total_tokens"]
    )
    lifetime = tracker.snapshot()["lifetime"]
    assert lifetime["attribution_invariant_ok"] is True


def test_rc3_record_compression_savings_keeps_all_accumulators_in_lockstep(tmp_path):
    """The third writer used to bump tokens_saved and nothing else."""
    tracker = _tracker(tmp_path)
    tracker.record_compression_savings(model="gpt-4o", tokens_saved=4_242, provider="openai")

    lifetime = tracker.snapshot()["lifetime"]
    assert lifetime["tokens_saved"] == 4_242
    assert lifetime["created_savings_tokens"] == 4_242
    assert lifetime["savings_by_source_tokens.cutctx_compression"] == 4_242
    accounting = tracker.savings_accounting()
    assert accounting["invariant_ok"] is True
    assert accounting["cutctx_attributable_tokens"] == 4_242
    assert accounting["provider_native_tokens"] == 0

    # The row it wrote must be visible to windowed queries and by-source sums.
    windowed = tracker.get_summary_stats(start_time=datetime.now(timezone.utc) - timedelta(hours=1))
    assert windowed["total_tokens_saved"] == 4_242
    assert windowed["savings_by_source_tokens"]["cutctx_compression"] == 4_242


def test_rc3_split_helper_is_the_single_definition():
    cutctx, provider = split_savings_by_attribution(
        {"cutctx_compression": 5, "model_routing": 3, "provider_prompt_cache": 11}
    )
    assert (cutctx, provider) == (8, 11)


# ---------------------------------------------------------------------------
# RC-4: every /stats figure carries an unambiguous scope.
# ---------------------------------------------------------------------------


def test_rc4_stats_payload_labels_every_scope(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from cutctx.proxy.server import ProxyConfig, create_app

    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(tmp_path / "proxy_savings.json"))
    config = ProxyConfig(cache_enabled=False, rate_limit_enabled=False, log_requests=False)

    with TestClient(create_app(config)) as client:
        payload = client.get("/stats").json()

    assert payload["scopes"]["since_restart"]
    assert payload["scopes"]["lifetime"]
    assert payload["summary"]["scope"] == "since_restart"
    assert payload["tokens"]["scope"] == "since_restart"
    assert payload["requests"]["scope"] == "since_restart"
    assert payload["cost"] is None or payload["cost"]["scope"] == "since_restart"
    assert payload["savings_by_source"]["scope"] == "lifetime"
    assert payload["attribution"]["scope"] == "lifetime"
    assert payload["opportunity_funnel"]["scope"] == "lifetime"
    assert payload["savings_accounting"]["scope"] == "lifetime"
    # The lifetime ledger must no longer be spliced with an in-memory counter.
    assert payload["savings_by_source_since_restart"]["scope"] == "since_restart"
    assert "rtk_cli_filtering" in payload["savings_by_source_since_restart"]["tokens"]
    assert (
        payload["savings_by_source"]["cutctx_attributable_tokens"]
        + payload["savings_by_source"]["provider_native_tokens"]
        == payload["savings_by_source"]["total_tokens"]
    )


# ---------------------------------------------------------------------------
# RC-5: report agent-context must not contradict itself.
# ---------------------------------------------------------------------------


def test_rc5_agent_context_report_reconciles_its_two_totals(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "cutctx.cli.report._collect_savings_history",
        lambda days: [
            # delta_tokens_saved deliberately disagrees with the by-source
            # ledger, exactly as it does on production data.
            {
                "tokens_saved": 10,
                "cost_savings_usd": 0.5,
                "savings_by_source_tokens": {
                    "cutctx_compression": 4,
                    "provider_prompt_cache": 96,
                },
            }
        ],
    )
    monkeypatch.setattr(
        "cutctx.cli.report._tracker_scope_facts",
        lambda days: {
            "scope": "all_time",
            "requests_total": 139_372,
            "lifetime_requests": 139_372,
            "window_covered": True,
            "window_note": None,
            "history_coverage": {},
        },
    )
    monkeypatch.setattr(
        "cutctx.cli.report._collect_request_telemetry",
        lambda days: {"status": "no_data", "requests_observed": 0},
    )
    monkeypatch.setattr(
        "cutctx.cli.report._assurance_section",
        lambda: {"status": "no_data", "note": "none"},
    )

    payload = _build_agent_context_report(0)
    summary = payload["summary"]
    reconciliation = payload["savings_reconciliation"]

    # RC-2: the real request count, not the number of retained rows.
    assert summary["requests"] == 139_372
    assert summary["savings_rows_observed"] == 1
    # RC-3/RC-5: the headline is Cutctx-only and the two totals are named.
    assert summary["tokens_saved"] == 4
    assert summary["cutctx_attributable_tokens_saved"] == 4
    assert summary["provider_native_tokens_saved"] == 96
    assert summary["raw_pipeline_delta_tokens"] == 10
    assert reconciliation["invariant_ok"] is True
    assert reconciliation["by_source_total_tokens"] == 100
    assert reconciliation["raw_vs_by_source_difference"] == 90
    assert reconciliation["explanation"]

    markdown = _render_agent_context_report(payload, "markdown")
    assert "Cutctx-attributable tokens saved: 4" in markdown
    assert "Provider-native tokens (not Cutctx): 96" in markdown
    assert "Raw pipeline delta (not a savings claim): 10" in markdown
    assert "## Savings Reconciliation" in markdown


# ---------------------------------------------------------------------------
# CLI defects: `savings --format json` and `savings --by-source`.
# ---------------------------------------------------------------------------


def _seeded_savings_path(tmp_path) -> str:
    tracker = SavingsTracker(path=str(tmp_path / "proxy_savings.json"))
    now = datetime.now(timezone.utc)
    _record(tracker, when=now - timedelta(minutes=10), cutctx=250_000, cache=750_000)
    tracker.flush()
    return str(tmp_path / "proxy_savings.json")


def test_cli_savings_format_json_emits_json_in_the_non_zero_state(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", _seeded_savings_path(tmp_path))
    from cutctx.cli.main import main as root

    result = CliRunner().invoke(root, ["savings", "--days", "1", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)  # must be parseable, not prose + JSON
    assert payload["total_tokens_saved"] == 250_000
    assert payload["cutctx_attributable_tokens"] == 250_000
    assert payload["provider_native_tokens"] == 750_000
    assert payload["savings_by_source"]["cutctx_compression"] == 250_000
    assert payload["savings_by_source"]["provider_prompt_cache"] == 750_000
    assert payload["scope"] in ("window", "window_partial_retained_history")


def test_cli_savings_by_source_shows_real_numbers(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", _seeded_savings_path(tmp_path))
    from cutctx.cli.main import main as root

    result = CliRunner().invoke(root, ["savings", "--days", "1", "--by-source", "--stats-only"])
    assert result.exit_code == 0, result.output
    assert "Savings by source:" in result.output
    assert "250.0K" in result.output
    assert "750.0K" in result.output
    assert "[provider-native]" in result.output
    assert "of which Cutctx-attributable" in result.output

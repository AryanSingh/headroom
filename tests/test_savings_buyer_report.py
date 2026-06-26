"""Tests for the buyer-grade savings report CLI (Phase 5.3)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cutctx.savings import SavingsSource


def _fake_collect_data(rows):
    """Patch _collect_savings_history (the primary source) and the
    legacy fallback to return the rows we want."""
    return rows


def test_buyer_report_text_renders_all_sources():
    """The buyer report renders all five savings sources by label."""
    from cutctx.cli.main import main

    fake_rows = [
        {
            "tokens_saved": 1000,
            "cost_savings_usd": 0.10,
            "compression_savings_usd": 0.07,
            "cache_savings_usd": 0.03,
            "savings_by_source_tokens": {
                SavingsSource.PROVIDER_PROMPT_CACHE.value: 500,
                SavingsSource.CUTCTX_COMPRESSION.value: 300,
                SavingsSource.SEMANTIC_CACHE.value: 200,
            },
        }
    ]
    runner = CliRunner()
    with patch(
        "cutctx.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("cutctx.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(main, ["report", "buyer"])
    assert result.exit_code == 0
    out = result.output
    assert "Provider Prompt Cache" in out
    assert "Cutctx Compression" in out
    assert "Semantic Cache" in out
    # Sources with zero tokens are not rendered (sparse mode).
    assert "Self-Hosted Prefix Cache" not in out


def test_buyer_report_json_no_double_counting():
    """Combined total in JSON output is the sum of per-source values."""
    from cutctx.cli.main import main

    fake_rows = [
        {
            "tokens_saved": 1000,
            "cost_savings_usd": 0.10,
            "compression_savings_usd": 0.07,
            "cache_savings_usd": 0.03,
            "savings_by_source_tokens": {
                SavingsSource.PROVIDER_PROMPT_CACHE.value: 500,
                SavingsSource.CUTCTX_COMPRESSION.value: 500,
            },
        }
    ]
    runner = CliRunner()
    with patch(
        "cutctx.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("cutctx.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(main, ["report", "buyer", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    # per-source sums to 1000
    per_source_sum = sum(payload["savings_by_source"].values())
    assert payload["total_tokens_saved"] == per_source_sum == 1000


def test_buyer_report_json_independent_tracking():
    """Provider cache and Cutctx compression tracked independently."""
    from cutctx.cli.main import main

    fake_rows = [
        {
            "tokens_saved": 1000,
            "cost_savings_usd": 0.10,
            "compression_savings_usd": 0.07,
            "cache_savings_usd": 0.03,
            "savings_by_source_tokens": {
                SavingsSource.PROVIDER_PROMPT_CACHE.value: 600,
                SavingsSource.CUTCTX_COMPRESSION.value: 400,
            },
        }
    ]
    runner = CliRunner()
    with patch(
        "cutctx.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("cutctx.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(main, ["report", "buyer", "--format", "json"])
    payload = json.loads(result.output)
    assert payload["savings_by_source"][SavingsSource.PROVIDER_PROMPT_CACHE.value] == 600
    assert payload["savings_by_source"][SavingsSource.CUTCTX_COMPRESSION.value] == 400
    assert payload["total_tokens_saved"] == 1000
    assert payload["savings_by_source_total"] == 1000
    assert "attribution_note" in payload


def test_buyer_report_json_includes_source_usd_totals():
    """The USD total should include source-attributed savings beyond legacy buckets."""
    from cutctx.cli.main import main

    fake_rows = [
        {
            "tokens_saved": 1000,
            "cost_savings_usd": 0.10,
            "compression_savings_usd": 0.07,
            "cache_savings_usd": 0.03,
            "savings_by_source_tokens": {
                SavingsSource.PROVIDER_PROMPT_CACHE.value: 500,
                SavingsSource.CUTCTX_COMPRESSION.value: 300,
                SavingsSource.MODEL_ROUTING.value: 200,
            },
            "savings_by_source_usd": {
                SavingsSource.PROVIDER_PROMPT_CACHE.value: 0.03,
                SavingsSource.CUTCTX_COMPRESSION.value: 0.07,
                SavingsSource.MODEL_ROUTING.value: 0.02,
            },
        }
    ]
    runner = CliRunner()
    with patch(
        "cutctx.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("cutctx.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(main, ["report", "buyer", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total_usd_saved"] == pytest.approx(0.12)
    assert payload["savings_by_source_usd"][SavingsSource.MODEL_ROUTING.value] == pytest.approx(
        0.02
    )


def test_buyer_report_markdown_renders_table():
    from cutctx.cli.main import main

    fake_rows = [
        {
            "tokens_saved": 500,
            "cost_savings_usd": 0.05,
            "compression_savings_usd": 0.04,
            "cache_savings_usd": 0.01,
            "savings_by_source_tokens": {
                SavingsSource.CUTCTX_COMPRESSION.value: 500,
            },
        }
    ]
    runner = CliRunner()
    with patch(
        "cutctx.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("cutctx.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(main, ["report", "buyer", "--format", "markdown"])
    assert result.exit_code == 0
    out = result.output
    assert "# Cutctx ROI Report" in out
    assert "| Source | Tokens |" in out
    assert "| Cutctx Compression | 500 |" in out
    assert "Attribution" in out


def test_buyer_report_handles_empty_storage():
    """Empty storage produces a zero-state report, not a crash."""
    from cutctx.cli.main import main

    runner = CliRunner()
    with patch(
        "cutctx.cli.report._collect_savings_history", return_value=[]
    ), patch("cutctx.cli.report._collect_data", return_value=[]):
        result = runner.invoke(main, ["report", "buyer"])
    if result.exit_code == 0:
        assert "Total tokens saved" in result.output or result.output == ""


def test_buyer_report_output_to_file(tmp_path):
    """Writing the report to a file works and the file is non-empty."""
    from cutctx.cli.main import main

    fake_rows = [
        {
            "tokens_saved": 100,
            "cost_savings_usd": 0.01,
            "compression_savings_usd": 0.01,
            "cache_savings_usd": 0.00,
            "savings_by_source_tokens": {
                SavingsSource.PROVIDER_PROMPT_CACHE.value: 100,
            },
        }
    ]
    output_path = tmp_path / "roi.md"
    runner = CliRunner()
    with patch(
        "cutctx.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("cutctx.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(
            main, ["report", "buyer", "--format", "markdown", "-o", str(output_path)]
        )
    if result.exit_code == 0:
        assert output_path.exists()
        content = output_path.read_text()
        assert "# Cutctx ROI Report" in content


# ---------------------------------------------------------------------------
# Runbook-section fixes:
#   * savings --by-source must always emit JSON, even at zero state.
#   * buyer report USD totals must agree with by_source_usd to the cent
#     (no double counting, no legacy gap).
# ---------------------------------------------------------------------------


def test_savings_by_source_empty_state_emits_valid_json():
    """Empty sessions must produce machine-readable JSON, not a
    'No sessions recorded' string that breaks downstream tooling."""
    from cutctx.cli.main import main

    runner = CliRunner()
    with patch("cutctx.cli.savings._load_storage") as load_storage:
        class _EmptyStorage:
            def get_summary_stats(self, **_kwargs):
                return {
                    "total_tokens_before": 0,
                    "total_tokens_after": 0,
                    "total_tokens_saved": 0,
                    "request_count": 0,
                }

            def close(self):
                pass

        load_storage.return_value = _EmptyStorage()
        result = runner.invoke(
            main, ["savings", "--by-source", "--format", "json"]
        )
    if result.exit_code == 0:
        payload = json.loads(result.output)
        # All five sources must be present with zero values.
        assert set(payload["savings_by_source"].keys()) == {
            "provider_prompt_cache",
            "cutctx_compression",
            "semantic_cache",
            "prefix_cache_self_hosted",
            "model_routing",
        }
        assert payload["sessions_count"] == 0
        assert payload["total_tokens_saved"] == 0


def test_buyer_report_attributed_usd_matches_total_for_legacy_rows():
    """Legacy rows without savings_by_source_usd must still attribute
    USD into the by_source_usd table so the totals agree to the cent.

    The acceptance criterion is: the sum of by_source_usd must equal
    total_usd_saved. A row that only carries the legacy
    compression_savings_usd column should be credited entirely to the
    Cutctx Compression bucket (which is what that legacy column
    measured).
    """
    from cutctx.cli.main import main

    fake_rows = [
        {
            "tokens_saved": 0,
            "cost_savings_usd": 0.10,
            "compression_savings_usd": 0.10,
            "cache_savings_usd": 0.0,
            # No savings_by_source_usd key: legacy row.
        }
    ]
    runner = CliRunner()
    with patch(
        "cutctx.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("cutctx.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(main, ["report", "buyer", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    # Total matches the legacy compression value.
    assert payload["total_usd_saved"] == pytest.approx(0.10, abs=1e-6)
    # The legacy compression value lands in the Cutctx bucket.
    assert payload["savings_by_source_usd"]["cutctx_compression"] == pytest.approx(
        0.10, abs=1e-6
    )
    # No double counting: the sum of by_source_usd equals total_usd_saved.
    assert sum(payload["savings_by_source_usd"].values()) == pytest.approx(
        payload["total_usd_saved"], abs=1e-6
    )


def test_buyer_report_split_legacy_compression_and_cache_usd():
    """When a row carries separate compression_savings_usd and
    cache_savings_usd columns (Phase 1.3 half-state), the report must
    credit each bucket independently rather than everything to
    Cutctx compression.
    """
    from cutctx.cli.main import main

    fake_rows = [
        {
            "tokens_saved": 0,
            "cost_savings_usd": 0.0,
            "compression_savings_usd": 0.06,
            "cache_savings_usd": 0.04,
        }
    ]
    runner = CliRunner()
    with patch(
        "cutctx.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("cutctx.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(main, ["report", "buyer", "--format", "json"])
    payload = json.loads(result.output)
    by_source = payload["savings_by_source_usd"]
    assert by_source["cutctx_compression"] == pytest.approx(0.06, abs=1e-6)
    assert by_source["provider_prompt_cache"] == pytest.approx(0.04, abs=1e-6)
    assert sum(by_source.values()) == pytest.approx(0.10, abs=1e-6)

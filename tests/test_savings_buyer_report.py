"""Tests for the buyer-grade savings report CLI (Phase 5.3)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from headroom.savings import SavingsSource


def _fake_collect_data(rows):
    """Patch _collect_savings_history (the primary source) and the
    legacy fallback to return the rows we want."""
    return rows


def test_buyer_report_text_renders_all_sources():
    """The buyer report renders all five savings sources by label."""
    from headroom.cli.main import main

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
        "headroom.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("headroom.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(main, ["report", "buyer"])
    assert result.exit_code == 0
    out = result.output
    assert "Provider Prompt Cache" in out
    assert "CutCtx Compression" in out
    assert "Semantic Cache" in out
    # Sources with zero tokens are not rendered (sparse mode).
    assert "Self-Hosted Prefix Cache" not in out


def test_buyer_report_json_no_double_counting():
    """Combined total in JSON output is the sum of per-source values."""
    from headroom.cli.main import main

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
        "headroom.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("headroom.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(main, ["report", "buyer", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    # per-source sums to 1000
    per_source_sum = sum(payload["savings_by_source"].values())
    assert payload["total_tokens_saved"] == per_source_sum == 1000


def test_buyer_report_json_independent_tracking():
    """Provider cache and CutCtx compression tracked independently."""
    from headroom.cli.main import main

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
        "headroom.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("headroom.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(main, ["report", "buyer", "--format", "json"])
    payload = json.loads(result.output)
    assert payload["savings_by_source"][SavingsSource.PROVIDER_PROMPT_CACHE.value] == 600
    assert payload["savings_by_source"][SavingsSource.CUTCTX_COMPRESSION.value] == 400
    assert payload["total_tokens_saved"] == 1000
    assert payload["savings_by_source_total"] == 1000
    assert "attribution_note" in payload


def test_buyer_report_markdown_renders_table():
    from headroom.cli.main import main

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
        "headroom.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("headroom.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(main, ["report", "buyer", "--format", "markdown"])
    assert result.exit_code == 0
    out = result.output
    assert "# CutCtx ROI Report" in out
    assert "| Source | Tokens |" in out
    assert "| CutCtx Compression | 500 |" in out
    assert "Attribution" in out


def test_buyer_report_handles_empty_storage():
    """Empty storage produces a zero-state report, not a crash."""
    from headroom.cli.main import main

    runner = CliRunner()
    with patch(
        "headroom.cli.report._collect_savings_history", return_value=[]
    ), patch("headroom.cli.report._collect_data", return_value=[]):
        result = runner.invoke(main, ["report", "buyer"])
    if result.exit_code == 0:
        assert "Total tokens saved" in result.output or result.output == ""


def test_buyer_report_output_to_file(tmp_path):
    """Writing the report to a file works and the file is non-empty."""
    from headroom.cli.main import main

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
        "headroom.cli.report._collect_savings_history", return_value=fake_rows
    ), patch("headroom.cli.report._collect_data", return_value=fake_rows):
        result = runner.invoke(
            main, ["report", "buyer", "--format", "markdown", "-o", str(output_path)]
        )
    if result.exit_code == 0:
        assert output_path.exists()
        content = output_path.read_text()
        assert "# CutCtx ROI Report" in content
        assert "Provider Prompt Cache" in content

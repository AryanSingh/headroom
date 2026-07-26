"""Regression test for savings percentage > 100% bug (issue with tool schema savings).

When tool schema compression is reported alongside message compression,
tokens_saved can exceed tokens_before, leading to impossible percentages > 100%.
This test ensures per-model and fleet-level savings percentages stay within [0, 100].
"""

import pytest

from cutctx.perf.analyzer import PerfRecord, PerfReport, build_perf_summary, format_report


def test_savings_pct_stays_within_bounds_with_tool_schema_savings():
    """Verify savings % never exceeds 100% when tool schema savings are present.

    Synthetic scenario: a model receives requests with only tool schema compression
    (no message compression). Tool schema savings dwarf message token counts,
    yielding tokens_saved > tokens_before without the fix.
    """
    # Simulate 5 requests where:
    # - Message compression: 1479 -> 1479 (no change)
    # - Tool schema savings: 3385 tokens
    # Total: 7395 tokens before, 7395 tokens after, 16925 tokens saved -> 228% without fix
    #
    # After fix, using (tokens_after + tokens_saved) as denominator:
    # 16925 / (7395 + 16925) = 16925 / 24320 = 69.6%
    records = [
        PerfRecord(
            timestamp="2026-07-24 13:00:00,000",
            request_id="req_1",
            model="minimax-m3",
            num_messages=1,
            tokens_before=1479,
            tokens_after=1479,
            tokens_saved=3385,  # Tool schema savings only
            cache_read=0,
            cache_write=0,
            cache_hit_pct=0,
            optimization_ms=68,
            transforms=["tool_schema_compaction"],
        ),
        PerfRecord(
            timestamp="2026-07-24 13:00:01,000",
            request_id="req_2",
            model="minimax-m3",
            num_messages=1,
            tokens_before=1313,
            tokens_after=1313,
            tokens_saved=3268,  # Tool schema savings only
            cache_read=0,
            cache_write=0,
            cache_hit_pct=0,
            optimization_ms=78,
            transforms=["tool_schema_compaction"],
        ),
        PerfRecord(
            timestamp="2026-07-24 13:00:02,000",
            request_id="req_3",
            model="minimax-m3",
            num_messages=1,
            tokens_before=1304,
            tokens_after=1304,
            tokens_saved=3385,  # Tool schema savings only
            cache_read=0,
            cache_write=0,
            cache_hit_pct=0,
            optimization_ms=83,
            transforms=["tool_schema_compaction"],
        ),
        PerfRecord(
            timestamp="2026-07-24 13:00:03,000",
            request_id="req_4",
            model="minimax-m3",
            num_messages=1,
            tokens_before=1287,
            tokens_after=1287,
            tokens_saved=3268,  # Tool schema savings only
            cache_read=0,
            cache_write=0,
            cache_hit_pct=0,
            optimization_ms=71,
            transforms=["tool_schema_compaction"],
        ),
        PerfRecord(
            timestamp="2026-07-24 13:00:04,000",
            request_id="req_5",
            model="minimax-m3",
            num_messages=1,
            tokens_before=1290,
            tokens_after=1290,
            tokens_saved=3301,  # Tool schema savings only
            cache_read=0,
            cache_write=0,
            cache_hit_pct=0,
            optimization_ms=75,
            transforms=["tool_schema_compaction"],
        ),
    ]

    report = PerfReport(
        perf_records=records,
        log_files_read=1,
        total_lines_parsed=100,
        requested_hours=24.0,
        oldest_kept_ts="2026-07-24 13:00:00,000",
        newest_kept_ts="2026-07-24 13:00:04,000",
    )

    # Check JSON summary
    summary = build_perf_summary(report)
    assert summary["savings_pct"] <= 100.0, (
        f"Fleet-level savings_pct {summary['savings_pct']}% exceeds 100% (unbounded numerator)"
    )
    assert summary["savings_pct"] >= 0.0, f"savings_pct {summary['savings_pct']}% is negative"

    # Check per-model breakdown
    minimax_model = next((m for m in summary["by_model"] if m["model"] == "minimax-m3"), None)
    assert minimax_model is not None, "minimax-m3 not found in summary"
    assert minimax_model["savings_pct"] <= 100.0, (
        f"minimax-m3 savings_pct {minimax_model['savings_pct']}% exceeds 100% (bug: tool savings in numerator)"
    )
    assert minimax_model["savings_pct"] >= 0.0, (
        f"minimax-m3 savings_pct {minimax_model['savings_pct']}% is negative"
    )

    # Check text format output
    text_output = format_report(report)
    assert "Per-Model Breakdown" in text_output
    # Extract the percentage from the text output for minimax-m3
    for line in text_output.split("\n"):
        if "minimax-m3" in line:
            # Line format: "  minimax-m3: 5 reqs, 16925 tokens saved (69%), list price unknown"
            # Extract the percentage between parentheses
            import re

            match = re.search(r"\((\d+)%\)", line)
            if match:
                pct = int(match.group(1))
                assert pct <= 100, f"Text output shows minimax-m3 {pct}% (exceeds 100%)"
            break


def test_savings_pct_at_100_percent_boundary():
    """Ensure calculations work correctly at the 100% boundary.

    If all tokens are saved (tokens_after = 0), the percentage should be 100%.
    """
    records = [
        PerfRecord(
            timestamp="2026-07-24 13:00:00,000",
            request_id="req_1",
            model="test-model",
            num_messages=1,
            tokens_before=1000,
            tokens_after=0,  # All tokens saved
            tokens_saved=1000,
            cache_read=0,
            cache_write=0,
            cache_hit_pct=0,
            optimization_ms=10,
            transforms=["compression"],
        ),
    ]

    report = PerfReport(
        perf_records=records,
        log_files_read=1,
        total_lines_parsed=10,
    )

    summary = build_perf_summary(report)
    assert summary["savings_pct"] == 100.0, (
        f"Expected exactly 100% when tokens_after=0, got {summary['savings_pct']}%"
    )


def test_savings_pct_with_mixed_compression_sources():
    """Test realistic scenario with both message and tool schema compression.

    Some requests have message compression, others have tool schema compression,
    and the fleet-level percentage should be accurate.
    """
    records = [
        # Request 1: Pure message compression
        PerfRecord(
            timestamp="2026-07-24 13:00:00,000",
            request_id="req_1",
            model="model-a",
            num_messages=5,
            tokens_before=1000,
            tokens_after=400,
            tokens_saved=600,  # message compression only
            cache_read=0,
            cache_write=0,
            cache_hit_pct=0,
            optimization_ms=12,
            transforms=["compression"],
        ),
        # Request 2: Tool schema compression (no message compression)
        PerfRecord(
            timestamp="2026-07-24 13:00:01,000",
            request_id="req_2",
            model="model-b",
            num_messages=1,
            tokens_before=100,
            tokens_after=100,
            tokens_saved=500,  # tool schema savings only
            cache_read=0,
            cache_write=0,
            cache_hit_pct=0,
            optimization_ms=50,
            transforms=["tool_schema_compaction"],
        ),
    ]

    report = PerfReport(
        perf_records=records,
        log_files_read=1,
        total_lines_parsed=20,
    )

    summary = build_perf_summary(report)
    # Fleet total: 1100 tokens before, 500 tokens after, 1100 tokens saved
    # Expected: 1100 / (500 + 1100) = 1100 / 1600 = 68.75%
    assert 68.0 <= summary["savings_pct"] <= 70.0, (
        f"Fleet savings_pct {summary['savings_pct']}% is outside expected range [68, 70]"
    )

    # Per-model: model-a should be 60% (600 / 1000)
    model_a = next((m for m in summary["by_model"] if m["model"] == "model-a"), None)
    assert model_a is not None
    assert 59.0 <= model_a["savings_pct"] <= 61.0, (
        f"model-a savings_pct {model_a['savings_pct']}% should be ~60%"
    )

    # Per-model: model-b should be ~83% (500 / (100 + 500))
    model_b = next((m for m in summary["by_model"] if m["model"] == "model-b"), None)
    assert model_b is not None
    assert 82.0 <= model_b["savings_pct"] <= 84.0, (
        f"model-b savings_pct {model_b['savings_pct']}% should be ~83%"
    )

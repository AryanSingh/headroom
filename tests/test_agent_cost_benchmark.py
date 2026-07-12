from __future__ import annotations

from benchmarks.agent_cost_benchmark import (
    benchmark_coding_agent_explosion,
    benchmark_quality_preservation,
)


def test_quality_preservation_benchmark_supports_compact_wire_formats() -> None:
    result = benchmark_quality_preservation()

    assert result.tokens_optimized < result.tokens_original
    assert result.critical_items_total > 0
    assert 0.0 <= result.retention_rate <= 1.0


def test_coding_agent_benchmark_measures_compact_output_retention() -> None:
    result = benchmark_coding_agent_explosion()

    assert result.tokens_optimized < result.tokens_original
    assert result.critical_items_total > 0
    assert result.retention_rate >= 0.99

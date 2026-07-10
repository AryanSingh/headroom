from __future__ import annotations

import json


def _sample_suite_result():
    from cutctx.evals.reports.report_card import BenchmarkRunResult, SuiteResult

    return SuiteResult(
        model="gpt-5.4-mini",
        tiers_run=[2],
        total_cost_usd=0.0,
        total_duration_seconds=1.2,
        benchmarks=[
            BenchmarkRunResult(
                name="TruthfulQA",
                category="factual",
                tier=1,
                baseline_score=0.81,
                cutctx_score=0.80,
                delta=-0.01,
                avg_compression_ratio=0.28,
                tokens_saved=123,
                n_samples=100,
                metric_name="bleu_acc",
                passed=True,
            ),
            BenchmarkRunResult(
                name="Verbatim Compaction",
                category="compression",
                tier=2,
                accuracy_rate=0.9333,
                avg_compression_ratio=0.2861,
                tokens_saved=151,
                tokens_per_second=4245075.52,
                critical_item_recall=0.9333,
                verbatim_fidelity=0.9333,
                n_samples=3,
                metric_name="verbatim_fidelity",
                passed=True,
            ),
        ],
    )


def test_benchmark_run_result_serializes_metric_label_and_value() -> None:
    from cutctx.evals.reports.report_card import BenchmarkRunResult

    result = BenchmarkRunResult(
        name="Verbatim Compaction",
        category="compression",
        tier=2,
        accuracy_rate=0.9333,
        avg_compression_ratio=0.2861,
        tokens_saved=151,
        tokens_per_second=4245075.52,
        critical_item_recall=0.9333,
        verbatim_fidelity=0.9333,
        metric_name="verbatim_fidelity",
        passed=True,
    )

    data = result.to_dict()

    assert data["metric"] == "verbatim_fidelity"
    assert data["metric_label"] == "Verbatim Fidelity"
    assert data["metric_value"] == 0.9333
    assert data["tokens_per_second"] == 4245075.52
    assert data["critical_item_recall"] == 0.9333
    assert data["verbatim_fidelity"] == 0.9333


def test_benchmark_run_result_uses_tool_schema_metric_label() -> None:
    from cutctx.evals.reports.report_card import BenchmarkRunResult

    result = BenchmarkRunResult(
        name="Tool Schema Compaction",
        category="compression",
        tier=2,
        accuracy_rate=1.0,
        avg_compression_ratio=0.18,
        tokens_saved=15,
        metric_name="tool_schema_integrity",
        passed=True,
    )

    data = result.to_dict()

    assert data["metric_label"] == "Tool Schema Integrity"
    assert data["metric_value"] == 1.0


def test_report_card_markdown_renders_metric_name_and_tokens_saved() -> None:
    from cutctx.evals.reports.report_card import generate_markdown

    markdown = generate_markdown(_sample_suite_result())

    assert "| Benchmark | Category | N | Metric | Value | Secondary Metrics | Compression | Tokens Saved | Status |" in markdown
    assert "Critical Item Recall 93.3% \\| Verbatim Fidelity 93.3% \\| Tokens/s 4,245,075.5" in markdown
    assert "| Verbatim Compaction | compression | 3 | Verbatim Fidelity | 93.3% | Critical Item Recall 93.3% \\| Verbatim Fidelity 93.3% \\| Tokens/s 4,245,075.5 | 29% | 151 | PASS |" in markdown
    assert "| Benchmark | Category | N | Baseline | Cutctx | Delta | Compression | Status |" in markdown


def test_report_card_html_renders_metric_name_and_tokens_saved() -> None:
    from cutctx.evals.reports.report_card import generate_html

    html = generate_html(_sample_suite_result())

    assert "<th>Metric</th><th>Value</th><th>Secondary Metrics</th><th>Compression</th><th>Tokens Saved</th><th>Status</th>" in html
    assert "Verbatim Fidelity" in html
    assert ">151<" in html
    assert "Critical Item Recall 93.3% | Verbatim Fidelity 93.3% | Tokens/s 4,245,075.5" in html


def test_report_card_json_includes_metric_name_and_value() -> None:
    from cutctx.evals.reports.report_card import generate_json

    payload = json.loads(generate_json(_sample_suite_result()))
    compression_benchmark = next(
        row for row in payload["benchmarks"] if row["name"] == "Verbatim Compaction"
    )

    assert compression_benchmark["metric"] == "verbatim_fidelity"
    assert compression_benchmark["metric_label"] == "Verbatim Fidelity"
    assert compression_benchmark["metric_value"] == 0.9333
    assert compression_benchmark["tokens_saved"] == 151
    assert compression_benchmark["tokens_per_second"] == 4245075.52
    assert compression_benchmark["critical_item_recall"] == 0.9333
    assert compression_benchmark["verbatim_fidelity"] == 0.9333

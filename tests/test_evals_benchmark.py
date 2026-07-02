"""Tests benchmark CLI and runner."""

from __future__ import annotations

import json


class TestBenchmarkRunner:
    """Verify BenchmarkRunner adapter registry and execution."""

    def test_benchmark_runner_registers_all_compressors(self) -> None:
        """All expected adapters should be present."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner

        runner = BenchmarkRunner()
        adapters = runner.list_compressors()
        names = {adapter.name for adapter in adapters}

        expected = {
            "smart_crusher",
            "log",
            "search",
            "diff",
            "code",
            "kompress",
            "llmlingua",
            "drain3",
            "html",
            "content_router",
        }

        assert expected <= names
        assert "content_router" in names
        assert any(adapter.name == "content_router" and adapter.available for adapter in adapters)

    def test_benchmark_runner_runs_tool_outputs(self) -> None:
        """Running the tool_outputs dataset should produce result rows."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.datasets import load_tool_output_samples

        dataset = load_tool_output_samples()
        runner = BenchmarkRunner()
        result = runner.run(
            dataset=dataset,
            compressors=["content_router", "smart_crusher", "log", "search"],
            n=1,
            parallel=1,
            seed=42,
        )

        assert result.seed == 42
        assert len(result.compressors) == 4
        assert result.datasets
        assert len(result.results) == 4
        assert {row.compressor for row in result.results} == {
            "content_router",
            "smart_crusher",
            "log",
            "search",
        }

        content_router_row = next(
            row for row in result.results if row.compressor == "content_router"
        )
        assert content_router_row.avg_ms >= 0
        assert content_router_row.tokens_saved >= 0


class TestBenchmarkReport:
    """Verify report dataclasses stay JSON-serializable and readable."""

    def test_benchmark_report_to_dict(self) -> None:
        """Suite and result dicts should serialize to JSON."""
        from cutctx.evals.benchmark_report import (
            BenchmarkSuiteResult,
            CompressorBenchmarkResult,
        )

        single = CompressorBenchmarkResult(
            dataset="ToolOutputSamples",
            compressor="content_router",
            n=5,
            ratio=0.35,
            tokens_saved=1200,
            avg_ms=12.34,
            p50_ms=10.5,
            f1=0.78,
            rouge_l=0.82,
            information_recall=0.90,
            exact_match=0.0,
            errors=0,
            skipped=False,
        )

        row_dict = single.to_dict()
        assert row_dict["dataset"] == "ToolOutputSamples"
        assert row_dict["compressor"] == "content_router"
        assert row_dict["ratio"] == 0.35
        assert row_dict["tokens_saved"] == 1200
        assert row_dict["skipped"] is False
        json.dumps(row_dict)

        suite = BenchmarkSuiteResult(
            seed=42,
            compressors=["content_router"],
            datasets=["ToolOutputSamples"],
            results=[single],
        )

        suite_dict = suite.to_dict()
        assert suite_dict["seed"] == 42
        assert len(suite_dict["results"]) == 1
        assert suite_dict["totals"]["datasets"] == 1
        assert suite_dict["totals"]["compressors"] == 1
        assert suite_dict["totals"]["cells"] == 1
        json.dumps(suite_dict)

    def test_markdown_output(self) -> None:
        """Markdown output should contain the expected headers and values."""
        from cutctx.evals.benchmark_report import (
            BenchmarkSuiteResult,
            CompressorBenchmarkResult,
        )

        r1 = CompressorBenchmarkResult(
            dataset="ToolOutputSamples",
            compressor="content_router",
            n=5,
            ratio=0.35,
            tokens_saved=1200,
            avg_ms=10.0,
            p50_ms=8.0,
            f1=0.78,
            errors=0,
        )
        r2 = CompressorBenchmarkResult(
            dataset="ToolOutputSamples",
            compressor="smart_crusher",
            n=5,
            ratio=0.42,
            tokens_saved=1000,
            avg_ms=5.0,
            p50_ms=4.0,
            f1=0.85,
            errors=0,
        )

        suite = BenchmarkSuiteResult(
            seed=42,
            compressors=["content_router", "smart_crusher"],
            datasets=["ToolOutputSamples"],
            results=[r1, r2],
        )

        markdown = suite.to_markdown("ratio")
        assert "Compression Ratio" in markdown
        assert "Dataset" in markdown
        assert "ContentRouter" in markdown
        assert "SmartCrusher" in markdown
        assert "ToolOutputSamples" in markdown
        assert "35.0%" in markdown
        assert "42.0%" in markdown


class TestBenchmarkCLI:
    """Verify benchmark CLI command wiring."""

    def test_benchmark_cli_help(self) -> None:
        """Running ``cutctx evals benchmark --help`` must exit 0."""
        from click.testing import CliRunner

        from cutctx.cli.evals import evals

        runner = CliRunner()
        result = runner.invoke(evals, ["benchmark", "--help"])
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"
        assert "benchmark" in result.output.lower()


class TestBenchmarkEdgeCases:
    """Edge case handling."""

    def test_unknown_compressor_skipped(self) -> None:
        """Unknown compressors are skipped instead of crashing the run."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.datasets import load_tool_output_samples

        dataset = load_tool_output_samples()
        runner = BenchmarkRunner()
        result = runner.run(
            dataset=dataset,
            compressors=["nonexistent_compressor"],
            n=1,
            parallel=1,
            seed=42,
        )

        assert len(result.results) == 0

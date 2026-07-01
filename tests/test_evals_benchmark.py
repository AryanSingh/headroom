"""Tests for the benchmark CLI and runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ======================================================================
# BenchmarkRunner
# ======================================================================


class TestBenchmarkRunner:
    """Verify the BenchmarkRunner adapter registry and basic execution."""

    def test_benchmark_runner_registers_all_compressors(self) -> None:
        """All 10 adapters must be registered; some may be unavailable."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner

        runner = BenchmarkRunner()
        adapters = runner.list_compressors()

        names = {a.name for a in adapters}
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
        missing = expected - names
        extra = names - expected

        assert not missing, f"Missing adapters: {missing}"
        assert not extra, f"Unexpected adapters: {extra}"
        assert len(adapters) >= 10, f"Expected >=10 adapters, got {len(adapters)}"

        # The content_router must always be available (no external deps)
        cr = [a for a in adapters if a.name == "content_router"]
        assert cr, "content_router adapter not found"
        assert all(a.available for a in cr), "content_router should always be available"

    def test_benchmark_runner_runs_tool_outputs(self) -> None:
        """Running against tool_outputs dataset with n=1 must not crash."""
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

        # Basic structure verification
        assert result.seed == 42
        assert len(result.compressors) == 4
        assert len(result.datasets) >= 1
        assert len(result.results) == 4

        for r in result.results:
            assert r.dataset == "ToolOutputSamples"
            assert r.compressor in ("content_router", "smart_crusher", "log", "search")
            assert r.n >= 1
            assert isinstance(r.ratio, float)
            assert 0.0 <= r.ratio <= 1.0
            assert isinstance(r.tokens_saved, int)
            assert isinstance(r.avg_ms, float)
            assert isinstance(r.p50_ms, float)
            assert r.skipped is False

        # Verify content_router produced a reasonable result
        cr_result = next(r for r in result.results if r.compressor == "content_router")
        assert cr_result.avg_ms >= 0
        assert cr_result.tokens_saved >= 0


# ======================================================================
# BenchmarkReport
# ======================================================================


class TestBenchmarkReport:
    """Verify the report dataclasses are JSON-serializable."""

    def test_benchmark_report_to_dict(self) -> None:
        """CompressorBenchmarkResult and BenchmarkSuiteResult must
        produce JSON-serializable dicts."""
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
        d = single.to_dict()
        assert d["dataset"] == "ToolOutputSamples"
        assert d["compressor"] == "content_router"
        assert d["ratio"] == 0.35
        assert d["tokens_saved"] == 1200
        assert d["skipped"] is False

        # Verify JSON-serializable
        json.dumps(d)

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

        # Verify JSON-serializable
        json.dumps(suite_dict)

    def test_markdown_output(self) -> None:
        """to_markdown() must produce a table with headers."""
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

        md = suite.to_markdown("ratio")
        assert "Compression Ratio" in md
        assert "Dataset" in md
        assert "ContentRouter" in md
        assert "SmartCrusher" in md
        assert "ToolOutputSamples" in md
        assert "35.0%" in md
        assert "42.0%" in md


# ======================================================================
# CLI
# ======================================================================


class TestBenchmarkCLI:
    """Verify the benchmark CLI command wiring."""

    def test_benchmark_cli_help(self) -> None:
        """Running ``cutctx evals benchmark --help`` must exit 0."""
        from click.testing import CliRunner

        from cutctx.cli.evals import evals

        runner = CliRunner()
        result = runner.invoke(evals, ["benchmark", "--help"])
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"
        assert "benchmark" in result.output.lower()


# ======================================================================
# BenchmarkRunner — edge cases
# ======================================================================


class TestBenchmarkEdgeCases:
    """Edge case handling."""

    def test_unknown_compressor_skipped(self) -> None:
        """Unknown compressors are silently skipped (logged as warning)."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.datasets import load_tool_output_samples

        dataset = load_tool_output_samples()
        runner = BenchmarkRunner()

        # Should not crash if the compressor key doesn't exist
        # (it's a no-op but won't blow up)
        result = runner.run(
            dataset=dataset,
            compressors=["nonexistent_compressor"],
            n=1,
            parallel=1,
            seed=42,
        )
        # Unknown compressors are silently skipped, so results will be empty
        assert len(result.results) == 0

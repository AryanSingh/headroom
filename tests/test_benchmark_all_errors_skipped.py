from __future__ import annotations

from cutctx.evals.benchmark_runner import BenchmarkRunner, CompressorAdapter, CompressorResult
from cutctx.evals.datasets import load_rag_samples


def test_compressor_with_only_errors_is_reported_as_skipped() -> None:
    runner = BenchmarkRunner()

    def fail(_: str) -> CompressorResult:
        return CompressorResult(compressed="", tokens_saved=0, duration_ms=0, error="unavailable")

    runner._adapters["broken"] = CompressorAdapter(
        name="broken",
        available=True,
        compress_fn=fail,
    )
    result = runner.run(
        dataset=load_rag_samples(),
        compressors=["broken"],
        metrics=["ratio"],
        parallel=1,
    )

    row = result.results[0]
    assert row.skipped is True
    assert row.errors == 6
    assert row.ratio == 1.0

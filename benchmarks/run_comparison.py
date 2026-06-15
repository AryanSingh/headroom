"""CutCtx vs competitors — reproducible benchmark suite.

Usage:
    python benchmarks/run_comparison.py [--output results/latest.json]
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class BenchmarkResult:
    method: str
    dataset: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float  # compressed / original
    latency_ms: float
    quality_score: float | None = None


class Compressor(Protocol):
    name: str
    def compress(self, text: str) -> tuple[str, float]: ...


class HeadroomCompressor:
    name = "cutctx"

    def compress(self, text: str) -> tuple[str, float]:
        from headroom.compress import compress as _compress

        t0 = time.perf_counter()
        result = _compress(text)
        elapsed = (time.perf_counter() - t0) * 1000
        return result.compressed, elapsed


def count_tokens(text: str) -> int:
    """Approximate token count (4 chars = 1 token)."""
    return len(text) // 4


def run_benchmark(
    compressor: Compressor, texts: list[str], dataset: str
) -> list[BenchmarkResult]:
    results = []
    for text in texts:
        orig_tokens = count_tokens(text)
        if orig_tokens == 0:
            continue
        try:
            compressed, latency = compressor.compress(text)
            comp_tokens = count_tokens(compressed)
            ratio = comp_tokens / orig_tokens
        except Exception as exc:
            print(f"  WARN [{compressor.name}]: {exc}")
            continue
        results.append(
            BenchmarkResult(
                method=compressor.name,
                dataset=dataset,
                original_tokens=orig_tokens,
                compressed_tokens=comp_tokens,
                compression_ratio=ratio,
                latency_ms=latency,
            )
        )
    return results


def print_summary_table(all_results: list[BenchmarkResult]) -> None:
    by_method: dict[str, list[BenchmarkResult]] = defaultdict(list)
    for r in all_results:
        by_method[r.method].append(r)

    print("\n| Method | Avg Compression | p50 Latency | p95 Latency | Samples |")
    print("|--------|----------------|-------------|-------------|---------|")
    for method, results in sorted(by_method.items()):
        avg_ratio = statistics.mean(r.compression_ratio for r in results)
        latencies = sorted(r.latency_ms for r in results)
        p50_lat = statistics.median(latencies)
        p95_lat = latencies[int(len(latencies) * 0.95)] if latencies else 0
        print(
            f"| {method} | {(1 - avg_ratio) * 100:.1f}% reduction "
            f"| {p50_lat:.1f}ms | {p95_lat:.1f}ms | {len(results)} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="CutCtx benchmark suite")
    parser.add_argument(
        "--output",
        default="benchmarks/results/latest.json",
        help="Output JSON file path",
    )
    parser.add_argument(
        "--dataset",
        default="internal",
        help="Dataset to benchmark against",
    )
    args = parser.parse_args()

    fixture_dir = Path("benchmarks/fixtures")
    texts = []
    for f in sorted(fixture_dir.glob("*.txt"))[:20]:
        texts.append(f.read_text(encoding="utf-8", errors="replace"))

    if not texts:
        print("ERROR: No benchmark fixtures found in benchmarks/fixtures/")
        print("Run: python benchmarks/generate_fixtures.py to create them")
        raise SystemExit(1)

    compressors: list[Compressor] = [HeadroomCompressor()]

    # Try optional competitors
    try:
        from benchmarks.llmlingua_compressor import LLMLinguaCompressor

        compressors.append(LLMLinguaCompressor())
    except ImportError:
        pass

    all_results: list[BenchmarkResult] = []
    for compressor in compressors:
        print(f"Running [{compressor.name}] on {len(texts)} texts...")
        results = run_benchmark(compressor, texts, args.dataset)
        all_results.extend(results)

    print_summary_table(all_results)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([asdict(r) for r in all_results], indent=2))
    print(f"\nResults -> {out}")


if __name__ == "__main__":
    main()

"""Cutctx vs competitors reproducible fixture benchmark.

Usage:
    python benchmarks/run_comparison.py [--output results/latest.json]
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from benchmarks._cutctx_adapter import compress_text_with_cutctx


@dataclass
class BenchmarkResult:
    method: str
    dataset: str
    sample: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    latency_ms: float
    quality_score: float | None = None


class Compressor(Protocol):
    name: str

    def compress(self, text: str) -> tuple[str, float]: ...


class CutctxCompressor:
    name = "cutctx"

    def compress(self, text: str) -> tuple[str, float]:
        return compress_text_with_cutctx(text)


def count_tokens(text: str) -> int:
    """Approximate token count."""
    return max(1, len(text) // 4)


def load_fixture_texts(fixtures_dir: Path) -> list[tuple[str, str]]:
    patterns = ("*.txt", "*.md", "*.json", "*.jsonl", "*.py")
    texts: list[tuple[str, str]] = []
    for pattern in patterns:
        for path in sorted(fixtures_dir.glob(pattern)):
            texts.append((path.name, path.read_text(encoding="utf-8")))
    return texts


def run_benchmark(
    compressor: Compressor,
    samples: list[tuple[str, str]],
    dataset: str,
) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []
    for sample_name, text in samples:
        orig_tokens = count_tokens(text)
        try:
            compressed, latency = compressor.compress(text)
            comp_tokens = count_tokens(compressed)
            ratio = comp_tokens / orig_tokens
        except Exception as exc:
            print(f"WARN [{compressor.name}/{sample_name}]: {exc}")
            continue
        results.append(
            BenchmarkResult(
                method=compressor.name,
                dataset=dataset,
                sample=sample_name,
                original_tokens=orig_tokens,
                compressed_tokens=comp_tokens,
                compression_ratio=ratio,
                latency_ms=latency,
            )
        )
    return results


def print_summary_table(all_results: list[BenchmarkResult]) -> None:
    by_method: dict[str, list[BenchmarkResult]] = defaultdict(list)
    for result in all_results:
        by_method[result.method].append(result)

    print("| Method | Samples | Avg Reduction | p50 Latency | p95 Latency |")
    print("|--------|---------|---------------|-------------|-------------|")
    for method, rows in sorted(by_method.items()):
        reductions = [1.0 - row.compression_ratio for row in rows]
        latencies = sorted(row.latency_ms for row in rows)
        avg_reduction = statistics.mean(reductions)
        p50_latency = statistics.median(latencies)
        p95_index = max(0, min(len(latencies) - 1, round((len(latencies) - 1) * 0.95)))
        p95_latency = latencies[p95_index]
        print(
            f"| {method} | {len(rows)} | {avg_reduction:.1%} | "
            f"{p50_latency:.1f}ms | {p95_latency:.1f}ms |"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="internal")
    parser.add_argument("--fixtures-dir", default="benchmarks/fixtures")
    parser.add_argument("--output", default="results/latest.json")
    args = parser.parse_args()

    fixtures_dir = Path(args.fixtures_dir)
    if not fixtures_dir.exists():
        print(f"ERROR: No benchmark fixtures found in {fixtures_dir}")
        print("Run: python benchmarks/generate_fixtures.py to create them")
        raise SystemExit(1)

    samples = load_fixture_texts(fixtures_dir)
    if not samples:
        print(f"ERROR: No benchmark samples found in {fixtures_dir}")
        raise SystemExit(1)

    compressors: list[Compressor] = [CutctxCompressor()]

    try:
        from benchmarks.llmlingua_compressor import LLMLinguaCompressor

        compressors.append(LLMLinguaCompressor())
    except ImportError:
        pass

    all_results: list[BenchmarkResult] = []
    for compressor in compressors:
        print(f"Running [{compressor.name}] on {len(samples)} texts...")
        all_results.extend(run_benchmark(compressor, samples, args.dataset))

    print_summary_table(all_results)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([asdict(result) for result in all_results], indent=2))
    print(f"\nResults -> {out}")


if __name__ == "__main__":
    main()

"""Cutctx vs competitors reproducible fixture benchmark.

Usage:
    python benchmarks/run_comparison.py [--output results/latest.json]
    python -m benchmarks.run_comparison [--output results/latest.json]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import random
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

# Permit both documented invocations.  When a file is executed directly Python
# only puts ``benchmarks/`` on sys.path, so the package import below otherwise
# fails before the benchmark can report useful evidence.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._cutctx_adapter import compress_text_with_cutctx
from cutctx.evals.metrics import compute_f1, compute_rouge_l


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
    f1_score: float | None = None
    rouge_l_score: float | None = None
    runs: int = 1


class Compressor(Protocol):
    name: str

    def compress(self, text: str) -> tuple[str, float]: ...


class CutctxCompressor:
    name = "cutctx"

    def compress(self, text: str) -> tuple[str, float]:
        return compress_text_with_cutctx(text)


def _package_version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _git_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_worktree_dirty() -> bool | None:
    try:
        return (
            subprocess.run(
                ["git", "diff", "--quiet"], check=False, stdout=subprocess.DEVNULL
            ).returncode
            != 0
        )
    except OSError:
        return None


def fixture_hashes(samples: list[tuple[str, str]]) -> dict[str, str]:
    """Return content hashes so a published result names its exact inputs."""
    return {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in samples}


def _percentile(values: list[float], percentile: float) -> float:
    """Return an interpolated percentile without a NumPy dependency."""
    if not values:
        raise ValueError("cannot calculate a percentile of no values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def bootstrap_interval(
    values: list[float],
    *,
    statistic: str = "mean",
    resamples: int = 2_000,
    seed: int = 20260713,
) -> dict[str, float | int | str] | None:
    """Return a deterministic non-parametric 95% bootstrap interval.

    Fixture-level measurements are the independent observations.  This does
    not make a five-fixture smoke test publishable, but it prevents a report
    from hiding the uncertainty of a small or heterogeneous fixture set.
    """
    if not values:
        return None
    if statistic == "mean":
        aggregate = statistics.mean
    elif statistic == "median":
        aggregate = statistics.median
    else:
        raise ValueError(f"unsupported bootstrap statistic: {statistic}")

    rng = random.Random(seed)
    n = len(values)
    draws = [aggregate([values[rng.randrange(n)] for _ in range(n)]) for _ in range(resamples)]
    return {
        "estimate": aggregate(values),
        "lower_95": _percentile(draws, 0.025),
        "upper_95": _percentile(draws, 0.975),
        "samples": n,
        "resamples": resamples,
        "method": f"nonparametric bootstrap ({statistic}, fixture-level)",
    }


def summarize_with_intervals(
    results: list[BenchmarkResult],
) -> dict[str, dict[str, dict[str, float | int | str] | None]]:
    """Summarize each compressor with reportable uncertainty metadata."""
    by_method: dict[str, list[BenchmarkResult]] = defaultdict(list)
    for result in results:
        by_method[result.method].append(result)

    summaries: dict[str, dict[str, dict[str, float | int | str] | None]] = {}
    for method, rows in sorted(by_method.items()):
        summaries[method] = {
            "reduction": bootstrap_interval([1.0 - row.compression_ratio for row in rows]),
            "quality_proxy": bootstrap_interval(
                [float(row.quality_score) for row in rows if row.quality_score is not None]
            ),
            "latency_ms": bootstrap_interval([row.latency_ms for row in rows], statistic="median"),
        }
    return summaries


def paired_comparator_deltas(
    results: list[BenchmarkResult],
    *,
    baseline: str = "llmlingua-2",
    candidate: str = "cutctx",
) -> dict[str, dict[str, float | int | str] | None]:
    """Return paired fixture deltas only when both methods completed a sample."""
    rows = {(row.method, row.sample): row for row in results}
    shared_samples = sorted(
        sample for method, sample in rows if method == candidate and (baseline, sample) in rows
    )
    if not shared_samples:
        return {}

    candidate_rows = [rows[(candidate, sample)] for sample in shared_samples]
    baseline_rows = [rows[(baseline, sample)] for sample in shared_samples]
    return {
        "candidate_minus_baseline_reduction": bootstrap_interval(
            [
                (1.0 - candidate_row.compression_ratio) - (1.0 - baseline_row.compression_ratio)
                for candidate_row, baseline_row in zip(candidate_rows, baseline_rows, strict=True)
            ]
        ),
        "candidate_minus_baseline_quality_proxy": bootstrap_interval(
            [
                float(candidate_row.quality_score or 0.0) - float(baseline_row.quality_score or 0.0)
                for candidate_row, baseline_row in zip(candidate_rows, baseline_rows, strict=True)
            ]
        ),
        "candidate_minus_baseline_latency_ms": bootstrap_interval(
            [
                candidate_row.latency_ms - baseline_row.latency_ms
                for candidate_row, baseline_row in zip(candidate_rows, baseline_rows, strict=True)
            ],
            statistic="median",
        ),
    }


def count_tokens(text: str, *, encoding_name: str = "cl100k_base") -> int:
    """Count tokens with a pinned tokenizer, falling back explicitly.

    The old character/4 estimate can materially change a winner on JSON and
    source files.  ``tiktoken`` is a benchmark dependency for publishable
    reports; the fallback exists only to keep local smoke runs usable and is
    recorded in the output metadata.
    """
    try:
        import tiktoken

        return max(1, len(tiktoken.get_encoding(encoding_name).encode(text)))
    except Exception:
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
    *,
    runs: int,
    warmup_runs: int,
    encoding_name: str,
) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []
    for sample_name, text in samples:
        orig_tokens = count_tokens(text, encoding_name=encoding_name)
        try:
            for _ in range(warmup_runs):
                compressor.compress(text)
            outputs: list[str] = []
            latencies: list[float] = []
            for _ in range(runs):
                compressed, latency = compressor.compress(text)
                outputs.append(compressed)
                latencies.append(latency)
            # Compression must be deterministic to make a single published
            # token count meaningful.  Keep the output associated with the
            # median observed latency, rather than an arbitrary iteration.
            median_latency = statistics.median(latencies)
            median_index = min(
                range(len(latencies)), key=lambda index: abs(latencies[index] - median_latency)
            )
            compressed = outputs[median_index]
            comp_tokens = count_tokens(compressed, encoding_name=encoding_name)
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
                latency_ms=statistics.median(latencies),
                f1_score=compute_f1(text, compressed),
                rouge_l_score=compute_rouge_l(text, compressed),
                quality_score=(compute_f1(text, compressed) + compute_rouge_l(text, compressed))
                / 2,
                runs=runs,
            )
        )
    return results


def print_summary_table(all_results: list[BenchmarkResult]) -> None:
    by_method: dict[str, list[BenchmarkResult]] = defaultdict(list)
    for result in all_results:
        by_method[result.method].append(result)

    print("| Method | Samples | Avg Reduction | Quality | p50 Latency | p95 Latency |")
    print("|--------|---------|---------------|---------|-------------|-------------|")
    for method, rows in sorted(by_method.items()):
        reductions = [1.0 - row.compression_ratio for row in rows]
        latencies = sorted(row.latency_ms for row in rows)
        avg_reduction = statistics.mean(reductions)
        p50_latency = statistics.median(latencies)
        p95_index = max(0, min(len(latencies) - 1, round((len(latencies) - 1) * 0.95)))
        p95_latency = latencies[p95_index]
        quality = statistics.mean(row.quality_score or 0.0 for row in rows)
        print(
            f"| {method} | {len(rows)} | {avg_reduction:.1%} | {quality:.3f} | "
            f"{p50_latency:.1f}ms | {p95_latency:.1f}ms |"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="internal")
    parser.add_argument("--fixtures-dir", default="benchmarks/fixtures")
    parser.add_argument("--output", default="results/latest.json")
    parser.add_argument(
        "--runs", type=int, default=3, help="Measured runs per fixture (default: 3)"
    )
    parser.add_argument(
        "--warmup-runs", type=int, default=1, help="Unrecorded warm-ups per fixture"
    )
    parser.add_argument(
        "--tokenizer", default="cl100k_base", help="tiktoken encoding for token counts"
    )
    args = parser.parse_args()
    if args.runs < 1 or args.warmup_runs < 0:
        parser.error("--runs must be positive and --warmup-runs cannot be negative")

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
        all_results.extend(
            run_benchmark(
                compressor,
                samples,
                args.dataset,
                runs=args.runs,
                warmup_runs=args.warmup_runs,
                encoding_name=args.tokenizer,
            )
        )

    print_summary_table(all_results)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 4,
        "benchmark_kind": "compression_regression_smoke",
        "quality_metric": "mean token-F1 and ROUGE-L lexical-retention proxy; not downstream task quality",
        "dataset": args.dataset,
        "fixtures_dir": str(fixtures_dir),
        "fixture_sha256": fixture_hashes(samples),
        "tokenizer": args.tokenizer,
        "tokenizer_library_version": _package_version("tiktoken"),
        "comparator_versions": {
            "cutctx": _git_revision(),
            "llmlingua": _package_version("llmlingua"),
        },
        "git_worktree_dirty": _git_worktree_dirty(),
        "runs": args.runs,
        "warmup_runs": args.warmup_runs,
        "uncertainty": {
            "unit": "fixture",
            "confidence_level": 0.95,
            "warning": (
                "Intervals quantify variation in this fixture set only; they do not "
                "generalize to customer workloads or establish downstream task quality."
            ),
            "by_method": summarize_with_intervals(all_results),
            "paired_cutctx_vs_llmlingua_2": paired_comparator_deltas(all_results),
        },
        "python": sys.version,
        "platform": platform.platform(),
        "results": [asdict(result) for result in all_results],
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"\nResults -> {out}")


if __name__ == "__main__":
    main()

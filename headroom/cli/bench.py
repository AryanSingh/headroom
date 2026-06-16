"""CLI benchmark command for CutCtx compression performance."""

from __future__ import annotations

import time
from typing import Any

import click

# Sample texts for benchmarking
_SAMPLE_SMALL = (
    "The quick brown fox jumps over the lazy dog. "
    "This is a sample text for benchmarking compression performance. "
    "It contains repeated patterns and common English words that compressors "
    "should handle efficiently. The fox was quick and brown."
) * 3  # ~300 chars

_SAMPLE_MEDIUM = (
    "def fibonacci(n: int) -> int:\n"
    "    if n <= 1:\n"
    "        return n\n"
    "    a, b = 0, 1\n"
    "    for _ in range(2, n + 1):\n"
    "        a, b = b, a + b\n"
    "    return b\n\n"
    "def fibonacci_memo(n: int, memo: dict = None) -> int:\n"
    "    if memo is None:\n"
    "        memo = {}\n"
    "    if n in memo:\n"
    "        return memo[n]\n"
    "    if n <= 1:\n"
        "        return n\n"
    "    memo[n] = fibonacci_memo(n - 1, memo) + fibonacci_memo(n - 2, memo)\n"
    "    return memo[n]\n\n"
    "class BinarySearchTree:\n"
    "    def __init__(self, value):\n"
    "        self.value = value\n"
    "        self.left = None\n"
    "        self.right = None\n\n"
    "    def insert(self, value):\n"
    "        if value < self.value:\n"
    "            if self.left is None:\n"
    "                self.left = BinarySearchTree(value)\n"
    "            else:\n"
    "                self.left.insert(value)\n"
    "        else:\n"
    "            if self.right is None:\n"
    "                self.right = BinarySearchTree(value)\n"
    "            else:\n"
    "                self.right.insert(value)\n\n"
    "    def search(self, value):\n"
    "        if value == self.value:\n"
    "            return True\n"
    "        elif value < self.value:\n"
    "            return self.left.search(value) if self.left else False\n"
    "        else:\n"
    "            return self.right.search(value) if self.right else False\n"
) * 3  # ~2KB

_SAMPLE_LARGE = _SAMPLE_MEDIUM * 15  # ~30KB

_SAMPLES = {"small": _SAMPLE_SMALL, "medium": _SAMPLE_MEDIUM, "large": _SAMPLE_LARGE}


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token for English)."""
    return len(text) // 4


@click.command("bench")
@click.option(
    "--size",
    type=click.Choice(["small", "medium", "large"]),
    default="medium",
    help="Sample data size.",
)
@click.option("--iterations", "-n", default=10, help="Number of iterations.")
@click.option(
    "--algorithm",
    "-a",
    type=click.Choice(["smart-crusher", "diff", "log", "search", "all"]),
    default="all",
    help="Compression algorithm to benchmark.",
)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON.")
def bench(size: str, iterations: int, algorithm: str, output_json: bool) -> None:
    """Benchmark CutCtx compression performance.

    Runs compression on sample data and reports timing, token savings,
    and compression ratios for each algorithm.

    \b
    Examples:
        cutctx bench                     Medium-sized benchmark, all algorithms
        cutctx bench --size large -n 20  Large data, 20 iterations
        cutctx bench -a smart-crusher    SmartCrusher only
        cutctx bench --json              JSON output for CI
    """
    sample = _SAMPLES[size]
    token_count = _estimate_tokens(sample)

    click.echo(f"Benchmarking {size} sample ({token_count} estimated tokens, {len(sample)} bytes)")
    click.echo(f"Iterations: {iterations}\n")

    results: list[dict[str, Any]] = []

    algorithms = _get_algorithms(algorithm)
    for name, compress_fn in algorithms:
        times_ms = []
        last_ratio = 0.0
        last_saved = 0

        for _ in range(iterations):
            t0 = time.perf_counter()
            try:
                result = compress_fn(sample)
                t1 = time.perf_counter()
                times_ms.append((t1 - t0) * 1000)
                if isinstance(result, dict):
                    compressed = result.get("compressed", result.get("text", sample))
                elif isinstance(result, str):
                    compressed = result
                else:
                    compressed = sample
                after_tokens = _estimate_tokens(compressed)
                last_saved = max(0, token_count - after_tokens)
                last_ratio = last_saved / token_count if token_count > 0 else 0.0
            except Exception:
                t1 = time.perf_counter()
                times_ms.append((t1 - t0) * 1000)

        if times_ms:
            avg_ms = sum(times_ms) / len(times_ms)
            p50 = sorted(times_ms)[len(times_ms) // 2]
            results.append({
                "algorithm": name,
                "avg_ms": round(avg_ms, 2),
                "p50_ms": round(p50, 2),
                "tokens_before": token_count,
                "tokens_saved": last_saved,
                "compression_pct": round(last_ratio * 100, 1),
                "iterations": len(times_ms),
            })

    if output_json:
        click.echo(json.dumps(results, indent=2))
        return

    # Pretty table
    if not results:
        click.echo("No results. Check that compression functions are available.")
        return

    header = f"{'Algorithm':<20} {'Avg ms':>8} {'P50 ms':>8} {'Tokens':>8} {'Saved':>8} {'Ratio':>7}"
    click.echo(header)
    click.echo("─" * len(header))
    for r in results:
        click.echo(
            f"{r['algorithm']:<20} {r['avg_ms']:>8.1f} {r['p50_ms']:>8.1f} "
            f"{r['tokens_before']:>8} {r['tokens_saved']:>8} {r['compression_pct']:>6.1f}%"
        )
    click.echo()
    click.echo(f"Completed {iterations} iterations × {len(results)} algorithms")


def _get_algorithms(algorithm: str) -> list[tuple[str, Any]]:
    """Get the list of algorithms to benchmark."""

    algos = []

    def _try_import(name: str, import_path: str, attr: str):
        try:
            mod = __import__(import_path, fromlist=[attr])
            fn = getattr(mod, attr)
            algos.append((name, fn))
        except (ImportError, AttributeError):
            pass

    if algorithm in ("all", "smart-crusher"):
        _try_import(
            "smart-crusher",
            "headroom.transforms.smart_crusher_compressor",
            "compress",
        )

    if algorithm in ("all", "diff"):
        _try_import(
            "diff",
            "headroom.transforms.diff_compressor",
            "compress",
        )

    if algorithm in ("all", "log"):
        _try_import(
            "log",
            "headroom.transforms.log_compressor",
            "compress",
        )

    if algorithm in ("all", "search"):
        _try_import(
            "search",
            "headroom.transforms.search_compressor",
            "compress",
        )

    if not algos:
        # Fallback: use the universal compress() if individual ones aren't available
        try:
            from headroom.compress import compress as universal_compress

            def _wrap(text: str) -> str:
                msgs = [{"role": "user", "content": text}]
                result = universal_compress(msgs, model="claude-sonnet-4-5")
                return result

            algos.append(("universal", _wrap))
        except ImportError:
            pass

    return algos


# Need json import at module level for --json output
import json  # noqa: E402

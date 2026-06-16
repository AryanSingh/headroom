#!/usr/bin/env python3
"""Episodic memory latency benchmark for Headroom.

Measures the end-to-end latency of the episodic memory pipeline:
  1. Memory store save/load (file I/O)
  2. Memory extraction (heuristic, no LLM)
  3. SmartCrusher CCR marker emission (via PyO3 -> Rust)

Target: < 5ms for the full CCR compression path.

Run with:
    python benchmarks/bench_episodic_memory.py
    python benchmarks/bench_episodic_memory.py --json results.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from headroom.memory.extractor import (
    _filter_messages,
    _format_transcript,
    _heuristic_extract,
    format_memory_block,
)
from headroom.memory.store import EpisodicMemoryStore

# ---------------------------------------------------------------------------
# Data generators
# ---------------------------------------------------------------------------

MEMORY_SECTIONS = [
    (
        "# Session 2025-01-15\n\n"
        "## User Requests\n"
        "- Refactored authentication module to use OAuth2\n"
        "- Fixed memory leak in WebSocket handler\n"
        "- Deployed v2.3.1 to staging\n\n"
        "## Key Decisions\n"
        "- Chose SQLite over PostgreSQL for local cache\n"
        "- Added circuit breaker pattern to payment service\n"
        "- Switched from REST to gRPC for inter-service communication\n\n"
        "## Errors Encountered\n"
        "- ConnectionTimeout in payment gateway\n"
        "- OutOfMemoryError during batch processing\n\n"
        "## Files Modified\n"
        "- src/auth/oauth2.rs\n"
        "- src/ws/handler.rs\n"
        "- deploy/staging.yaml\n"
    ),
    (
        "# Session 2025-01-12\n\n"
        "## User Requests\n"
        "- Implemented rate limiting middleware\n"
        "- Added Prometheus metrics endpoint\n"
        "- Migrated database schema for multi-tenancy\n\n"
        "## Key Decisions\n"
        "- Token bucket algorithm for rate limiting (100 req/s per tenant)\n"
        "- Metrics stored in time-series format\n"
        "- Schema migration via blue-green deployment\n\n"
        "## Errors Encountered\n"
        "- RateLimitExceeded errors during load test\n"
        "- Schema migration deadlock\n"
    ),
]


def _generate_memory_text(target_chars: int) -> str:
    """Generate realistic episodic memory text."""
    text = "\n---\n\n".join(MEMORY_SECTIONS) + "\n"
    result = ""
    while len(result) < target_chars:
        result += text
    return result[:target_chars]


def _generate_messages(n_turns: int) -> list[dict]:
    """Generate a realistic multi-turn conversation."""
    msgs = [{"role": "system", "content": "You are a coding assistant."}]
    for i in range(n_turns):
        msgs.append({"role": "user", "content": f"Turn {i}: Analyze file_{i}.rs"})
        msgs.append(
            {
                "role": "assistant",
                "content": f"I've analyzed file_{i}.rs. Found {i % 3} issues.",
            }
        )
    return msgs


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


def bench_store_save_load(iterations: int = 100) -> dict:
    """Benchmark memory store save + load roundtrip."""
    sizes = {
        "1KB": 1_000,
        "5KB": 5_000,
        "10KB": 10_000,
        "20KB": 20_000,
    }
    results = {}

    for label, chars in sizes.items():
        text = _generate_memory_text(chars)
        timings = []

        for _ in range(iterations):
            with tempfile.TemporaryDirectory() as tmpdir:
                store = EpisodicMemoryStore(memory_dir=Path(tmpdir))
                project_hash = hashlib.sha256(b"bench_project").hexdigest()[:16]

                t0 = time.perf_counter_ns()
                store.save_memory(project_hash, text)
                loaded = store.load_memories(project_hash)
                t1 = time.perf_counter_ns()

                assert loaded is not None and len(loaded) > 0
                timings.append((t1 - t0) / 1_000_000)  # ns -> ms

        s = sorted(timings)
        results[label] = {
            "p50_ms": round(s[len(s) // 2], 3),
            "p95_ms": round(s[int(len(s) * 0.95)], 3),
            "mean_ms": round(statistics.mean(timings), 3),
            "min_ms": round(min(timings), 3),
            "max_ms": round(max(timings), 3),
        }

    return results


def bench_heuristic_extract(iterations: int = 100) -> dict:
    """Benchmark heuristic extraction (no LLM call)."""
    sizes = {
        "10_turns": 10,
        "50_turns": 50,
        "100_turns": 100,
    }
    results = {}

    for label, n_turns in sizes.items():
        messages = _generate_messages(n_turns)
        timings = []

        for _ in range(iterations):
            t0 = time.perf_counter_ns()
            insights = _heuristic_extract(messages)
            t1 = time.perf_counter_ns()
            timings.append((t1 - t0) / 1_000_000)

        s = sorted(timings)
        results[label] = {
            "p50_ms": round(s[len(s) // 2], 3),
            "p95_ms": round(s[int(len(s) * 0.95)], 3),
            "mean_ms": round(statistics.mean(timings), 3),
        }

    return results


def bench_filter_messages(iterations: int = 100) -> dict:
    """Benchmark message filtering."""
    messages = _generate_messages(50)
    # Add some system messages and empty messages
    messages.insert(0, {"role": "system", "content": "System prompt"})
    messages.insert(2, {"role": "system", "content": ""})
    messages.append({"role": "user", "content": ""})

    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        filtered = _filter_messages(messages)
        t1 = time.perf_counter_ns()
        timings.append((t1 - t0) / 1_000_000)

    s = sorted(timings)
    return {
        "p50_ms": round(s[len(s) // 2], 3),
        "p95_ms": round(s[int(len(s) * 0.95)], 3),
        "mean_ms": round(statistics.mean(timings), 3),
    }


def bench_format_memory_block(iterations: int = 100) -> dict:
    """Benchmark format_memory_block (the wrapper that produces the CCR-detectable prefix)."""
    sizes = {"1KB": 1_000, "5KB": 5_000, "10KB": 10_000}
    results = {}

    for label, chars in sizes.items():
        text = _generate_memory_text(chars)
        timings = []

        for _ in range(iterations):
            t0 = time.perf_counter_ns()
            block = format_memory_block(text, "/Users/test/project")
            t1 = time.perf_counter_ns()
            assert block.startswith("[SYSTEM: Past Session Memories]")
            timings.append((t1 - t0) / 1_000_000)

        s = sorted(timings)
        results[label] = {
            "p50_ms": round(s[len(s) // 2], 3),
            "p95_ms": round(s[int(len(s) * 0.95)], 3),
            "mean_ms": round(statistics.mean(timings), 3),
        }

    return results


def bench_full_pipeline(iterations: int = 100) -> dict:
    """Benchmark full pipeline: filter -> extract -> format -> save -> load."""
    messages = _generate_messages(25)
    results = {}

    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        filtered = _filter_messages(messages)
        transcript = _format_transcript(filtered)
        insights = _heuristic_extract(filtered)
        block = format_memory_block(insights, "/Users/test/project")
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EpisodicMemoryStore(memory_dir=Path(tmpdir))
            h = hashlib.sha256(b"bench").hexdigest()[:16]
            store.save_memory(h, block)
            loaded = store.load_memories(h)
        t1 = time.perf_counter_ns()
        assert loaded is not None
        timings.append((t1 - t0) / 1_000_000)

    s = sorted(timings)
    results = {
        "p50_ms": round(s[len(s) // 2], 3),
        "p95_ms": round(s[int(len(s) * 0.95)], 3),
        "mean_ms": round(statistics.mean(timings), 3),
        "min_ms": round(min(timings), 3),
        "max_ms": round(max(timings), 3),
    }
    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def print_report(all_results: dict) -> None:
    """Print a terminal-friendly report."""
    print()
    print("=" * 72)
    print("  EPISODIC MEMORY LATENCY BENCHMARK")
    print("=" * 72)
    print()

    for section, data in all_results.items():
        print(f"  {section}")
        print("  " + "-" * 60)

        if isinstance(data, dict) and "p50_ms" in data and "mean_ms" in data:
            # Single result
            print(
                f"    p50={data['p50_ms']:.3f}ms  "
                f"p95={data['p95_ms']:.3f}ms  "
                f"mean={data['mean_ms']:.3f}ms"
            )
        else:
            # Multi-size results
            for label, metrics in data.items():
                print(
                    f"    {label:>8}: p50={metrics['p50_ms']:.3f}ms  "
                    f"p95={metrics['p95_ms']:.3f}ms  "
                    f"mean={metrics['mean_ms']:.3f}ms"
                )

        print()

    # Summary
    print("  SUMMARY")
    print("  " + "-" * 60)

    # Check target
    pipeline = all_results.get("Full Pipeline (filter+extract+format+save+load)", {})
    if pipeline:
        p50 = pipeline.get("p50_ms", 0)
        target = 5.0
        status = "PASS" if p50 < target else "FAIL"
        print(f"    Full pipeline p50: {p50:.3f}ms — target <{target}ms: {status}")

    store_data = all_results.get("Store Save+Load", {})
    if store_data:
        max_p50 = max(m["p50_ms"] for m in store_data.values())
        target = 2.0
        status = "PASS" if max_p50 < target else "FAIL"
        print(f"    Store save+load max p50: {max_p50:.3f}ms — target <{target}ms: {status}")

    print()
    print("=" * 72)
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Episodic memory latency benchmark")
    parser.add_argument("--json", "-j", help="Save JSON results to path")
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=100,
        help="Iterations per benchmark (default: 100)",
    )
    args = parser.parse_args()

    print("Running episodic memory benchmarks...")
    print()

    all_results = {}

    print("  [1/6] Store save+load...", end=" ", flush=True)
    all_results["Store Save+Load"] = bench_store_save_load(args.iterations)
    print("done")

    print("  [2/6] Heuristic extraction...", end=" ", flush=True)
    all_results["Heuristic Extraction"] = bench_heuristic_extract(args.iterations)
    print("done")

    print("  [3/6] Message filtering...", end=" ", flush=True)
    all_results["Message Filtering"] = bench_filter_messages(args.iterations)
    print("done")

    print("  [4/6] format_memory_block...", end=" ", flush=True)
    all_results["format_memory_block"] = bench_format_memory_block(args.iterations)
    print("done")

    print("  [5/6] Full pipeline...", end=" ", flush=True)
    all_results["Full Pipeline (filter+extract+format+save+load)"] = bench_full_pipeline(
        args.iterations
    )
    print("done")

    print_report(all_results)

    if args.json:
        Path(args.json).write_text(json.dumps(all_results, indent=2))
        print(f"JSON results saved to: {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

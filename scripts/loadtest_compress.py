#!/usr/bin/env python3
"""Load test for the proxy's `/v1/compress` endpoint.

Written because no load or performance test had ever been run against this
product. The internal tokbench recorded "+0.9s per request (32% overhead)" but
nothing measured concurrent throughput or tail latency, so the audit scored
Performance 4/10 with the note "never load-tested by anyone".

This drives the compression path directly, which is the expensive part of a
request, and needs no LLM provider credentials.

Usage
-----
    # start a proxy first (loopback; /v1/compress is open on loopback by design)
    CUTCTX_SKIP_UPSTREAM_CHECK=1 python -m cutctx.cli.main proxy --port 18899 &

    python scripts/loadtest_compress.py --port 18899 --concurrency 8 --requests 200

Reports throughput and p50/p90/p99 latency. Interpret tail latency with care if
the machine is doing anything else — contention shows up in p99 first.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time

import httpx

LEVELS = ("INFO", "WARN", "ERROR", "DEBUG")


def build_log_payload(lines: int, seed: int) -> str:
    """A realistic log payload — the workload the LogCompressor targets."""
    rng = random.Random(seed)
    out = []
    for i in range(lines):
        level = rng.choices(LEVELS, [0.6, 0.2, 0.18, 0.02])[0]
        out.append(
            f"2026-07-26T10:{i // 60:02d}:{i % 60:02d}Z {level} svc.worker "
            f"handled request id={i} latency={rng.randint(3, 400)}ms"
        )
    # One genuine fatal, so fidelity can be asserted under load.
    out[lines // 2] = "2026-07-26T10:10:00Z FATAL svc.worker LOADTEST_CANARY disk failure"
    return "\n".join(out)


async def one_request(client: httpx.AsyncClient, url: str, payload: str) -> tuple[float, int, bool]:
    """Return (elapsed_seconds, status_code, canary_preserved)."""
    # `model` is required by the endpoint even though no upstream call is made.
    body = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "loadtest-1",
                        "content": payload,
                    }
                ],
            }
        ],
    }
    start = time.perf_counter()
    try:
        resp = await client.post(url, json=body, timeout=60.0)
        elapsed = time.perf_counter() - start
    except Exception:
        return time.perf_counter() - start, 0, False

    preserved = False
    if resp.status_code == 200:
        # Fidelity under load matters as much as speed: a FATAL line must
        # survive, or be disclosed. Accept either.
        text = resp.text
        preserved = "LOADTEST_CANARY" in text or "FATAL" in text
    return elapsed, resp.status_code, preserved


async def run(port: int, concurrency: int, total: int, lines: int) -> int:
    url = f"http://127.0.0.1:{port}/v1/compress"
    payload = build_log_payload(lines, seed=7)
    payload_kb = len(payload) / 1024

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    sem = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    statuses: dict[int, int] = {}
    canary_ok = 0

    async with httpx.AsyncClient(limits=limits) as client:
        # Warm up so first-request model/tokenizer load does not skew the run.
        await one_request(client, url, payload)

        async def worker() -> None:
            nonlocal canary_ok
            async with sem:
                elapsed, status, preserved = await one_request(client, url, payload)
                latencies.append(elapsed)
                statuses[status] = statuses.get(status, 0) + 1
                if preserved:
                    canary_ok += 1

        wall_start = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(total)))
        wall = time.perf_counter() - wall_start

    ok = statuses.get(200, 0)
    latencies.sort()

    def pct(p: float) -> float:
        if not latencies:
            return 0.0
        idx = min(len(latencies) - 1, int(len(latencies) * p))
        return latencies[idx]

    print("=" * 62)
    print("cutctx /v1/compress load test")
    print("=" * 62)
    print(f"payload            : {lines} log lines, {payload_kb:.1f} kB")
    print(f"requests           : {total} at concurrency {concurrency}")
    print(f"wall clock         : {wall:.2f}s")
    print(f"throughput         : {total / wall:.1f} req/s")
    print(f"status codes       : {json.dumps(statuses)}")
    print(f"succeeded          : {ok}/{total}")
    if latencies:
        print(f"latency mean       : {statistics.mean(latencies) * 1000:.0f} ms")
        print(f"latency p50        : {pct(0.50) * 1000:.0f} ms")
        print(f"latency p90        : {pct(0.90) * 1000:.0f} ms")
        print(f"latency p99        : {pct(0.99) * 1000:.0f} ms")
        print(f"latency max        : {latencies[-1] * 1000:.0f} ms")
    print(f"FATAL preserved    : {canary_ok}/{ok} successful responses")
    if ok and canary_ok < ok:
        print("  WARNING: a FATAL line was lost under load — fidelity regression")
    print("=" * 62)

    # Non-zero exit if the endpoint was not actually usable, so this can gate.
    return 0 if ok == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=18899)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--requests", type=int, default=200)
    ap.add_argument("--lines", type=int, default=1200, help="log lines per payload")
    args = ap.parse_args()
    return asyncio.run(run(args.port, args.concurrency, args.requests, args.lines))


if __name__ == "__main__":
    raise SystemExit(main())

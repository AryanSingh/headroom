#!/usr/bin/env python3
"""Measure Cutctx proxy overhead on a real protocol request path.

This benchmark runs the OpenAI-compatible ``/v1/chat/completions`` handler
in-process.  The upstream provider call is replaced with a fixed successful
response, so the results isolate Cutctx request handling rather than network
or model-inference latency.  It is intended for reproducible regression
tracking, not comparisons with an external provider's end-to-end latency.

Usage::

    python benchmarks/proxy_request_benchmark.py --requests 200 --concurrency 20
    python benchmarks/proxy_request_benchmark.py --json artifacts/proxy-benchmark.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


@dataclass(frozen=True)
class RequestBenchmarkResult:
    """Aggregate latency and status metrics for an ASGI request benchmark."""

    path: str
    requests: int
    concurrency: int
    successes: int
    failures: int
    elapsed_seconds: float
    latencies_ms: tuple[float, ...]
    status_codes: dict[int, int]

    def _percentile(self, fraction: float) -> float:
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        index = max(0, math.ceil(fraction * len(ordered)) - 1)
        return ordered[index]

    @property
    def p50_ms(self) -> float:
        return self._percentile(0.50)

    @property
    def p95_ms(self) -> float:
        return self._percentile(0.95)

    @property
    def p99_ms(self) -> float:
        return self._percentile(0.99)

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def requests_per_second(self) -> float:
        return self.requests / self.elapsed_seconds if self.elapsed_seconds else 0.0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.pop("latencies_ms")
        result.update(
            {
                "p50_ms": round(self.p50_ms, 3),
                "p95_ms": round(self.p95_ms, 3),
                "p99_ms": round(self.p99_ms, 3),
                "mean_ms": round(self.mean_ms, 3),
                "requests_per_second": round(self.requests_per_second, 3),
            }
        )
        return result


async def run_request_benchmark(
    app: FastAPI,
    *,
    path: str,
    payload: dict[str, Any],
    requests: int,
    concurrency: int,
    headers: dict[str, str] | None = None,
) -> RequestBenchmarkResult:
    """Exercise an ASGI request path with bounded concurrency.

    Every response, including unsuccessful ones, contributes to latency. This
    keeps failures visible in the result instead of making a fast failure look
    like a performance win.
    """
    if requests < 1:
        raise ValueError("requests must be at least 1")
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")

    latencies_ms: list[float] = []
    statuses: Counter[int] = Counter()
    semaphore = asyncio.Semaphore(concurrency)
    # A benchmark must report application failures as HTTP 500s instead of
    # terminating early and hiding the incomplete run.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(transport=transport, base_url="http://cutctx-benchmark") as client:

        async def send_one() -> None:
            async with semaphore:
                started = time.perf_counter()
                response = await client.post(path, json=payload, headers=headers)
                latencies_ms.append((time.perf_counter() - started) * 1000)
                statuses[response.status_code] += 1

        started = time.perf_counter()
        await asyncio.gather(*(send_one() for _ in range(requests)))
        elapsed_seconds = time.perf_counter() - started

    successes = sum(count for status, count in statuses.items() if 200 <= status < 300)
    return RequestBenchmarkResult(
        path=path,
        requests=requests,
        concurrency=concurrency,
        successes=successes,
        failures=requests - successes,
        elapsed_seconds=elapsed_seconds,
        latencies_ms=tuple(latencies_ms),
        status_codes=dict(sorted(statuses.items())),
    )


async def run_http_request_benchmark(
    *,
    base_url: str,
    path: str,
    payload: dict[str, Any],
    requests: int,
    concurrency: int,
    headers: dict[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> RequestBenchmarkResult:
    """Exercise an already-running proxy over HTTP/TCP.

    ``transport`` is only for deterministic tests; omit it for a real network
    connection. The proxy and any compared gateway must be run separately on
    the same host with the same upstream fixture for a fair comparison.
    """
    if requests < 1:
        raise ValueError("requests must be at least 1")
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")

    latencies_ms: list[float] = []
    statuses: Counter[int] = Counter()
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"), transport=transport, timeout=30
    ) as client:

        async def send_one() -> None:
            async with semaphore:
                started = time.perf_counter()
                response = await client.post(path, json=payload, headers=headers)
                latencies_ms.append((time.perf_counter() - started) * 1000)
                statuses[response.status_code] += 1

        started = time.perf_counter()
        await asyncio.gather(*(send_one() for _ in range(requests)))
        elapsed_seconds = time.perf_counter() - started

    successes = sum(count for status, count in statuses.items() if 200 <= status < 300)
    return RequestBenchmarkResult(
        path=path,
        requests=requests,
        concurrency=concurrency,
        successes=successes,
        failures=requests - successes,
        elapsed_seconds=elapsed_seconds,
        latencies_ms=tuple(latencies_ms),
        status_codes=dict(sorted(statuses.items())),
    )


def build_proxy_app() -> FastAPI:
    """Build a real Cutctx proxy with a deterministic local upstream."""
    from cutctx.proxy.server import ProxyConfig, create_app

    app = create_app(
        ProxyConfig(
            backend="mock",
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            log_requests=False,
            ccr_inject_tool=False,
            ccr_handle_responses=False,
            ccr_context_tracking=False,
        )
    )

    async def fixed_upstream_response(*_args: Any, **_kwargs: Any) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_benchmark",
                "object": "chat.completion",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
            },
        )

    app.state.proxy._retry_request = fixed_upstream_response
    # ``backend=mock`` installs LiteLLM's mock backend, which is useful for
    # functional tests but bypasses the direct OpenAI handler transport we
    # want to measure here.  Keeping the app configuration otherwise intact
    # and disabling that backend makes the handler call the deterministic
    # ``_retry_request`` replacement above.
    app.state.proxy.anthropic_backend = None
    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requests", type=int, default=100, help="Measured requests (default: 100)"
    )
    parser.add_argument(
        "--concurrency", type=int, default=10, help="In-flight requests (default: 10)"
    )
    parser.add_argument(
        "--warmup", type=int, default=10, help="Unreported warm-up requests (default: 10)"
    )
    parser.add_argument(
        "--base-url",
        help="Measure an already-running proxy over HTTP instead of the in-process fixture",
    )
    parser.add_argument(
        "--json", type=Path, help="Write the result and environment metadata as JSON"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = {
        "model": "gpt-5.4-mini",
        "messages": [{"role": "user", "content": "return a concise benchmark response"}],
    }
    headers = {"Authorization": "Bearer benchmark-key"}
    if args.base_url:

        def run(count: int, concurrency: int):
            return run_http_request_benchmark(
                base_url=args.base_url,
                path="/v1/chat/completions",
                payload=payload,
                requests=count,
                concurrency=concurrency,
                headers=headers,
            )

        measurement = (
            "HTTP/TCP to an existing proxy; excludes provider inference only when upstream is fixed"
        )
    else:
        app = build_proxy_app()

        def run(count: int, concurrency: int):
            return run_request_benchmark(
                app,
                path="/v1/chat/completions",
                payload=payload,
                requests=count,
                concurrency=concurrency,
                headers=headers,
            )

        measurement = (
            "in-process ASGI; fixed upstream response; excludes network and model inference"
        )
    if args.warmup:
        asyncio.run(run(args.warmup, min(args.concurrency, args.warmup)))
    result = asyncio.run(run(args.requests, args.concurrency))
    metadata = {
        "benchmark": "cutctx_proxy_request_path",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "measurement": measurement,
        "result": result.to_dict(),
    }
    print(json.dumps(metadata, indent=2, sort_keys=True))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0 if result.failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

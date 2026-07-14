from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from benchmarks.proxy_request_benchmark import build_proxy_app, run_request_benchmark


def test_request_benchmark_reports_percentiles_throughput_and_failures() -> None:
    app = FastAPI()

    @app.post("/benchmark")
    async def benchmark_endpoint():
        return {"ok": True}

    result = asyncio.run(
        run_request_benchmark(
            app,
            path="/benchmark",
            payload={"request": "value"},
            requests=6,
            concurrency=2,
        )
    )

    assert result.requests == 6
    assert result.successes == 6
    assert result.failures == 0
    assert result.requests_per_second > 0
    assert result.p50_ms >= 0
    assert result.p95_ms >= result.p50_ms
    assert result.p99_ms >= result.p95_ms
    assert result.to_dict()["path"] == "/benchmark"


def test_request_benchmark_counts_non_successful_responses() -> None:
    app = FastAPI()

    @app.post("/benchmark")
    async def benchmark_endpoint():
        return JSONResponse({"detail": "unavailable"}, status_code=503)

    result = asyncio.run(
        run_request_benchmark(
            app,
            path="/benchmark",
            payload={},
            requests=1,
            concurrency=1,
        )
    )

    assert result.successes == 0
    assert result.failures == 1
    assert result.status_codes == {503: 1}


def test_request_benchmark_records_unhandled_server_errors() -> None:
    app = FastAPI()

    @app.post("/benchmark")
    async def benchmark_endpoint():
        raise RuntimeError("benchmark failure")

    result = asyncio.run(
        run_request_benchmark(
            app,
            path="/benchmark",
            payload={},
            requests=1,
            concurrency=1,
        )
    )

    assert result.failures == 1
    assert result.status_codes == {500: 1}


def test_proxy_benchmark_exercises_the_openai_compatible_handler() -> None:
    result = asyncio.run(
        run_request_benchmark(
            build_proxy_app(),
            path="/v1/chat/completions",
            payload={
                "model": "gpt-5.4-mini",
                "messages": [{"role": "user", "content": "benchmark"}],
            },
            requests=1,
            concurrency=1,
            headers={"Authorization": "Bearer benchmark-key"},
        )
    )

    assert result.successes == 1
    assert result.status_codes == {200: 1}

#!/usr/bin/env python3
"""Isolated direct-vs-Cutctx Responses benchmark with semantic capture."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

FAKE_PORT = 8794
PROXY_PORT = 8795
SAMPLES = 12
WARMUPS = 2
RESULT_PATH = ROOT / "output/performance/wrapped_sessions_2026_07_16.json"

os.environ.setdefault("CUTCTX_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CUTCTX_REQUIRE_RUST_CORE", "false")
os.environ.setdefault("CUTCTX_DISABLE_MEMORY", "true")


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil((pct / 100.0) * len(ordered)))
    return ordered[rank - 1]


def summary(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(statistics.median(values), 3),
        "p95_ms": round(percentile(values, 95), 3),
        "max_ms": round(max(values), 3),
        "mean_ms": round(statistics.mean(values), 3),
    }


def make_body(text_bytes: int) -> dict[str, Any]:
    seed = "wrapped-session deterministic user context 0123456789 abcdef\n"
    text = (seed * ((text_bytes // len(seed)) + 1))[:text_bytes]
    assert len(text.encode("utf-8")) == text_bytes
    return {
        "model": "gpt-4o-mini",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            }
        ],
        "stream": False,
        "max_output_tokens": 8,
    }


async def wait_ready(url: str) -> None:
    async with httpx.AsyncClient(timeout=1.0) as client:
        for _ in range(200):
            try:
                if (await client.get(url)).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.05)
    raise RuntimeError(f"server not ready: {url}")


async def main() -> None:
    captures: list[dict[str, Any]] = []
    fake = FastAPI()

    @fake.get("/livez")
    async def fake_livez() -> dict[str, bool]:
        return {"ok": True}

    @fake.post("/v1/responses")
    async def fake_responses(request: Request) -> JSONResponse:
        raw = await request.body()
        body = json.loads(raw)
        text = body["input"][0]["content"][0]["text"]
        captures.append(
            {
                "raw_bytes": len(raw),
                "text_bytes": len(text.encode("utf-8")),
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "input_sha256": hashlib.sha256(
                    json.dumps(body["input"], sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
            }
        )
        return JSONResponse(
            {
                "id": "resp_fake",
                "object": "response",
                "status": "completed",
                "model": body.get("model", "gpt-4o-mini"),
                "output": [],
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }
        )

    @fake.websocket("/v1/responses")
    async def fake_responses_ws(ws: WebSocket) -> None:
        await ws.accept()
        await ws.receive_text()
        await ws.send_json({"type": "response.completed", "response": {"id": "resp_fake_ws"}})

    @fake.post("/v1/messages")
    async def fake_messages(request: Request) -> JSONResponse:
        await request.body()
        return JSONResponse(
            {
                "id": "msg_fake",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "ok"}],
                "model": "claude-fake",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )

    from cutctx.proxy.models import ProxyConfig
    from cutctx.proxy.server import create_app

    proxy_config = ProxyConfig(
        host="127.0.0.1",
        port=PROXY_PORT,
        openai_api_url=f"http://127.0.0.1:{FAKE_PORT}",
        anthropic_api_url=f"http://127.0.0.1:{FAKE_PORT}",
        cache_enabled=False,
        rate_limit_enabled=False,
        retry_enabled=False,
    )
    proxy = create_app(proxy_config)
    fake_server = uvicorn.Server(
        uvicorn.Config(fake, host="127.0.0.1", port=FAKE_PORT, log_level="error")
    )
    proxy_server = uvicorn.Server(
        uvicorn.Config(proxy, host="127.0.0.1", port=PROXY_PORT, log_level="error")
    )
    tasks = [
        asyncio.create_task(fake_server.serve()),
        asyncio.create_task(proxy_server.serve()),
    ]
    try:
        await wait_ready(f"http://127.0.0.1:{FAKE_PORT}/livez")
        await wait_ready(f"http://127.0.0.1:{PROXY_PORT}/livez")
        result: dict[str, Any] = {
            "environment": {
                "fake_upstream": f"http://127.0.0.1:{FAKE_PORT}",
                "cutctx_proxy": f"http://127.0.0.1:{PROXY_PORT}",
                "samples": SAMPLES,
                "warmups": WARMUPS,
                "python": sys.version.split()[0],
            },
            "sizes": {},
        }
        headers = {"Authorization": "Bearer deterministic-test-key"}
        timeout = httpx.Timeout(30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for size_label, text_bytes in (("36kb", 36 * 1024), ("250kb", 250 * 1024)):
                body = make_body(text_bytes)
                canonical_input_hash = hashlib.sha256(
                    json.dumps(body["input"], sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                text_hash = hashlib.sha256(
                    body["input"][0]["content"][0]["text"].encode()
                ).hexdigest()
                direct: list[float] = []
                wrapped: list[float] = []
                capture_start = len(captures)
                for index in range(WARMUPS + SAMPLES):
                    for bucket, url in (
                        (direct, f"http://127.0.0.1:{FAKE_PORT}/v1/responses"),
                        (wrapped, f"http://127.0.0.1:{PROXY_PORT}/v1/responses"),
                    ):
                        started = time.perf_counter()
                        response = await client.post(url, headers=headers, json=body)
                        elapsed = (time.perf_counter() - started) * 1000.0
                        response.raise_for_status()
                        if index >= WARMUPS:
                            bucket.append(elapsed)
                observed = captures[capture_start:]
                semantic_ok = all(
                    item["text_bytes"] == text_bytes
                    and item["text_sha256"] == text_hash
                    and item["input_sha256"] == canonical_input_hash
                    for item in observed
                )
                direct_summary = summary(direct)
                wrapped_summary = summary(wrapped)
                overhead_p50 = wrapped_summary["p50_ms"] - direct_summary["p50_ms"]
                result["sizes"][size_label] = {
                    "user_text_bytes": text_bytes,
                    "direct_ms": [round(v, 3) for v in direct],
                    "wrapped_ms": [round(v, 3) for v in wrapped],
                    "direct": direct_summary,
                    "wrapped": wrapped_summary,
                    "overhead": {
                        "p50_ms": round(overhead_p50, 3),
                        "p50_percent_of_direct": round(
                            100.0 * overhead_p50 / direct_summary["p50_ms"], 2
                        ),
                        "p95_ms": round(
                            wrapped_summary["p95_ms"] - direct_summary["p95_ms"], 3
                        ),
                    },
                    "semantic_input_unchanged": semantic_ok,
                    "expected_input_sha256": canonical_input_hash,
                    "expected_text_sha256": text_hash,
                    "upstream_captures": observed,
                }

        # Exercise the project's existing mixed WS/HTTP reconnect-storm harness.
        from scripts.repro_codex_replay import build_parser, run_harness

        replay_args = build_parser().parse_args(
            [
                "--url",
                f"http://127.0.0.1:{PROXY_PORT}",
                "--ws-clients",
                "8",
                "--anthropic-clients",
                "4",
                "--duration",
                "10",
                "--livez-threshold-ms",
                "500",
            ]
        )
        result["reconnect_storm"] = await run_harness(replay_args)
        RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        fake_server.should_exit = True
        proxy_server.should_exit = True
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())

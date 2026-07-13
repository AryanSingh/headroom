"""Run the hosted compression smoke against a configured remote endpoint."""

from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

from cutctx.hosted import HostedCompressionClient

PAYLOAD_SIZES = {"small": 12, "medium": 120, "large": 720}


class RemoteHostedNotConfigured(RuntimeError):
    """Raised when the remote-hosted smoke cannot be run safely."""


def _payload(rows: int) -> str:
    return json.dumps(
        [
            {
                "id": index,
                "status": "error" if index % 11 == 0 else "ok",
                "message": f"remote hosted smoke payload {index % 4}",
                "component": "remote-hosted-smoke",
            }
            for index in range(rows)
        ],
        indent=2,
    )


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def remote_hosted_config_from_env() -> tuple[str, str]:
    base_url = os.environ.get("CUTCTX_HOSTED_BASE_URL", "").strip()
    api_key = os.environ.get("CUTCTX_HOSTED_API_KEY", "").strip()
    if not base_url or not api_key:
        raise RemoteHostedNotConfigured(
            "CUTCTX_HOSTED_BASE_URL and CUTCTX_HOSTED_API_KEY are required"
        )
    return base_url, api_key


def run_remote_hosted_smoke(
    *,
    base_url: str,
    api_key: str,
    samples_per_size: int = 3,
    markdown_output: Path,
    json_output: Path,
) -> dict[str, Any]:
    """Run three representative payload sizes and write redacted evidence."""
    if samples_per_size < 1:
        raise ValueError("samples_per_size must be at least 1")

    # Free hosted instances can take more than a minute to wake. Give the
    # first request enough time to initialize, and retry a transient transport
    # failure once without hiding authentication or API contract errors.
    import httpx

    client = HostedCompressionClient(base_url, api_key=api_key, timeout=180.0)
    cases: list[dict[str, Any]] = []

    for size, rows in PAYLOAD_SIZES.items():
        latencies_ms: list[float] = []
        tokens_saved: list[int] = []
        for _ in range(samples_per_size):
            started = time.perf_counter()
            result = None
            last_error: Exception | None = None
            for attempt in range(2):
                try:
                    result = client.compress_text(
                        _payload(rows),
                        model="gpt-4o",
                        compatibility_mode="tool_output",
                        min_tokens_to_compress=10,
                        protect_recent=0,
                    )
                    break
                except httpx.HTTPError as exc:
                    last_error = exc
                    if attempt == 1:
                        raise
            if result is None:
                raise RuntimeError(f"remote hosted request failed: {last_error}")
            latencies_ms.append((time.perf_counter() - started) * 1000.0)
            tokens_saved.append(result.tokens_saved)

        cases.append(
            {
                "size": size,
                "samples": samples_per_size,
                "latency_ms": {
                    "p50": round(statistics.median(latencies_ms), 2),
                    "p95": round(_percentile(latencies_ms, 0.95), 2),
                },
                "tokens_saved": {
                    "min": min(tokens_saved),
                    "max": max(tokens_saved),
                    "mean": round(statistics.mean(tokens_saved), 2),
                },
            }
        )

    payload: dict[str, Any] = {
        "status": "passed",
        "base_url": base_url.rstrip("/"),
        "samples_per_size": samples_per_size,
        "cases": cases,
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = ["# Remote Hosted Compression Smoke", "", f"- Base URL: `{payload['base_url']}`"]
    lines.extend(
        ["", "| Payload | Samples | P50 | P95 | Mean Tokens Saved |", "|---|---:|---:|---:|---:|"]
    )
    for case in cases:
        lines.append(
            "| {size} | {samples} | {p50:.2f} ms | {p95:.2f} ms | {mean:.2f} |".format(
                size=case["size"],
                samples=case["samples"],
                p50=case["latency_ms"]["p50"],
                p95=case["latency_ms"]["p95"],
                mean=case["tokens_saved"]["mean"],
            )
        )
    lines.extend(["", "API keys and payload bodies are intentionally excluded from this artifact."])
    markdown_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    try:
        base_url, api_key = remote_hosted_config_from_env()
    except RemoteHostedNotConfigured as exc:
        print(json.dumps({"status": "not_configured", "reason": str(exc)}, indent=2))
        return

    payload = run_remote_hosted_smoke(
        base_url=base_url,
        api_key=api_key,
        markdown_output=Path("artifacts/remote-hosted-compression-smoke.md"),
        json_output=Path("artifacts/remote-hosted-compression-smoke.json"),
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

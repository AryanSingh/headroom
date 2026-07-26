#!/usr/bin/env python3
"""Process-level client-matrix verification (no provider keys required).

Expands scripts/verify_model_routing_live.py across Messages / Chat /
Responses HTTP wire formats, health endpoints, orchestrator mode toggles,
and wrap dry-run CLI checks.

Usage:
  .venv/bin/python scripts/verify_client_matrix_live.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app

ADMIN = "client-matrix-live-admin"
FAST = {"gpt-5.4-mini", "claude-haiku-4-5", "gemini-2.5-flash"}
STRONG = {"gpt-5.5", "gpt-5.6-terra", "gpt-5.6-sol", "claude-opus-4-5", "gemini-2.5-pro"}
ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CaseResult:
    name: str
    ok: bool
    expected: str
    actual: str
    detail: str = ""


class UpstreamCapture:
    def __init__(self) -> None:
        self.models: list[str] = []
        self.bodies: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []

    async def __call__(self, method, url, headers, body, stream=False, **kwargs):  # noqa: ANN001
        payload = body if isinstance(body, dict) else {}
        model = str(payload.get("model", ""))
        self.models.append(model)
        self.bodies.append(payload)
        self.headers.append({str(k).lower(): str(v) for k, v in dict(headers or {}).items()})
        url_s = str(url)
        if "messages" in url_s and "chat" not in url_s:
            return httpx.Response(
                200,
                json={
                    "id": "msg_live",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "ok"}],
                    "model": model,
                    "usage": {"input_tokens": 8, "output_tokens": 2},
                },
            )
        if "/responses" in url_s:
            return httpx.Response(
                200,
                json={
                    "id": "resp_live",
                    "object": "response",
                    "model": model,
                    "output": [],
                    "usage": {"input_tokens": 8, "output_tokens": 2},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_live",
                "object": "chat.completion",
                "model": model,
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10},
            },
        )


def _chat(client: TestClient, model: str, content: str, **extra: Any) -> httpx.Response:
    return client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer sk-test", "x-cutctx-admin-key": ADMIN},
        json={"model": model, "messages": [{"role": "user", "content": content}], **extra},
    )


def _messages(client: TestClient, model: str, content: str) -> httpx.Response:
    return client.post(
        "/v1/messages",
        headers={
            "x-api-key": "sk-ant-test",
            "anthropic-version": "2023-06-01",
            "x-cutctx-admin-key": ADMIN,
            "User-Agent": "claude-code/1.0",
        },
        json={"model": model, "max_tokens": 64, "messages": [{"role": "user", "content": content}]},
    )


def _responses(client: TestClient, model: str, content: str) -> httpx.Response:
    return client.post(
        "/v1/responses",
        headers={"Authorization": "Bearer sk-test", "x-cutctx-admin-key": ADMIN},
        json={"model": model, "input": content},
    )


def _cli_dry_run(results: list[CaseResult]) -> None:
    """Exercise wrap --help / routing status without mutating user home."""
    cutctx_bin = ROOT / ".venv" / "bin" / "cutctx"
    if cutctx_bin.exists():
        base = [str(cutctx_bin)]
    else:
        base = ["cutctx"]
    env = os.environ.copy()
    env["CUTCTX_SKIP_UPSTREAM_CHECK"] = "1"
    checks = [
        ("cli.wrap.claude.help", [*base, "wrap", "claude", "--help"]),
        ("cli.wrap.codex.help", [*base, "wrap", "codex", "--help"]),
        ("cli.wrap.cursor.help", [*base, "wrap", "cursor", "--help"]),
        ("cli.routing.status", [*base, "routing", "status"]),
    ]
    for name, cmd in checks:
        try:
            completed = subprocess.run(
                cmd,
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
            ok = completed.returncode == 0
            results.append(
                CaseResult(
                    name,
                    ok,
                    "rc=0",
                    f"rc={completed.returncode}",
                    detail=(completed.stderr or completed.stdout)[:300] if not ok else "",
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(CaseResult(name, False, "rc=0", "exception", detail=str(exc)[:300]))


def main() -> int:
    tracker_dir = tempfile.mkdtemp(prefix="cutctx-client-matrix-")
    tracker_db = str(Path(tracker_dir) / "prefix_tracker.db")
    orch_dir = str(Path(tracker_dir) / "orchestration")
    Path(orch_dir).mkdir(parents=True, exist_ok=True)
    os.environ["CUTCTX_PREFIX_TRACKER_DB_PATH"] = tracker_db
    os.environ["CUTCTX_ORCHESTRATION_DIR"] = orch_dir
    os.environ["CUTCTX_SAVINGS_PATH"] = str(Path(tracker_dir) / "proxy_savings.json")
    os.environ["CUTCTX_SKIP_UPSTREAM_CHECK"] = "1"

    config = ProxyConfig(
        backend="anthropic",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        log_requests=False,
        ccr_inject_tool=False,
        ccr_handle_responses=False,
        ccr_context_tracking=False,
        image_optimize=False,
        discover_pipeline_extensions=False,
        admin_api_key=ADMIN,
        model_routing_preset="auto",
        prefix_freeze_db_path=tracker_db,
    )
    app = create_app(config)
    capture = UpstreamCapture()
    results: list[CaseResult] = []

    with TestClient(app) as client:
        proxy = client.app.state.proxy
        assert proxy.anthropic_backend is None
        assert proxy._model_router is not None
        proxy._retry_request = capture

        for path in ("/livez", "/readyz"):
            resp = client.get(path)
            results.append(
                CaseResult(f"health.{path.strip('/')}", resp.status_code == 200, "200", str(resp.status_code))
            )

        stats = client.get("/stats", headers={"x-cutctx-admin-key": ADMIN})
        mode = (stats.json() or {}).get("model_routing", {}).get("mode")
        results.append(CaseResult("stats.mode", mode in {"auto", "off", "aggressive"}, "auto|off|aggressive", str(mode)))

        flipped = client.post(
            "/config/flags",
            headers={"x-cutctx-admin-key": ADMIN},
            json={"orchestrator_mode": "auto"},
        )
        applied = flipped.json().get("applied_live", {}).get("orchestrator_mode", {}).get("mode")
        results.append(CaseResult("config.auto", applied == "auto", "auto", str(applied)))

        cases: list[tuple[str, str, str, set[str], str, str]] = [
            ("chat.auto.low", "chat", "auto", FAST, "Rename this variable.", "fast"),
            ("chat.auto.high", "chat", "auto", STRONG, "Implement durable workflow cancellation.", "strong"),
            ("chat.adv.security", "chat", "gpt-5.5", {"gpt-5.5"}, "Audit the authentication flow for vulnerabilities.", "stay"),
            ("messages.auto.low", "messages", "auto", FAST, "Rename this variable.", "fast"),
            ("messages.auto.high", "messages", "auto", STRONG, "Implement model routing end to end.", "strong"),
            ("responses.auto.low", "responses", "auto", FAST, "Rename this variable.", "fast"),
            ("responses.strong.high", "responses", "gpt-5.5", {"gpt-5.5"}, "Implement durable workflow cancellation.", "stay"),
        ]
        for name, wire, model, expect, prompt, label in cases:
            before = len(capture.models)
            if wire == "chat":
                resp = _chat(client, model, prompt)
            elif wire == "messages":
                resp = _messages(client, model, prompt)
            else:
                resp = _responses(client, model, prompt)
            actual = capture.models[-1] if len(capture.models) > before else ""
            ok = resp.status_code == 200 and actual in expect
            results.append(
                CaseResult(
                    name,
                    ok,
                    label + ":" + "|".join(sorted(expect)),
                    actual or f"http={resp.status_code}",
                    detail=resp.text[:200] if not ok else "",
                )
            )

        # Failure injection: mid-session mode flip must ack without stuck optimistic mode.
        off = client.post(
            "/config/flags",
            headers={"x-cutctx-admin-key": ADMIN},
            json={"orchestrator_mode": "off"},
        )
        stats_off = client.get("/stats", headers={"x-cutctx-admin-key": ADMIN})
        ok_off = (
            off.status_code == 200
            and stats_off.json().get("model_routing", {}).get("mode") == "off"
        )
        results.append(
            CaseResult(
                "config.toggle.off_ack",
                ok_off,
                "off",
                str(stats_off.json().get("model_routing", {}).get("mode")),
            )
        )

    _cli_dry_run(results)

    failed = [r for r in results if not r.ok]
    report = {
        "passed": len(failed) == 0,
        "passed_count": len(results) - len(failed),
        "failed_count": len(failed),
        "results": [asdict(r) for r in results],
    }
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

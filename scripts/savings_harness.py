#!/usr/bin/env python3
"""Measure what each savings engine actually saves, on real traffic.

The unit tests for these engines run against fixtures with mocked upstreams.
That proves the code paths execute; it does not prove an engine reduces the
tokens a provider would bill for. Those are different claims, and only the
second one is the product's promise.

This harness makes the second claim measurable. For each scenario it:

  1. starts a capture upstream that records the exact bytes the proxy forwards,
  2. starts a real proxy subprocess configured for one engine,
  3. sends a representative payload for that engine's content type,
  4. reports client tokens vs upstream tokens, and the proxy's own
     savings-by-source attribution.

Tokens are counted with tiktoken over the serialized request, so "before" and
"after" are measured the same way and the delta is meaningful even though the
upstream is synthetic.

Usage::

    python scripts/savings_harness.py --list
    python scripts/savings_harness.py --scenario batch_routing
    python scripts/savings_harness.py --all --json artifacts/savings-harness.json

Exit code is non-zero when a scenario marked ``expect_savings`` returns none,
so this can gate a release.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent

# Haiku everywhere: these payloads never reach a real provider, but keeping the
# corpus on the cheapest tier means an operator who points the harness at a
# live endpoint does not get a surprise bill.
MODEL = "claude-haiku-4-5"
ROUTING_SOURCE_MODEL = "claude-sonnet-4-5"  # routes down to haiku


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------


def count_tokens(payload: Any) -> int:
    """Token count of a serialized request body."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Capture upstream
# ---------------------------------------------------------------------------


class _Capture(BaseHTTPRequestHandler):
    records: list[dict[str, Any]] = []

    def log_message(self, *_a: object) -> None:  # silence
        pass

    def _respond(self, body: bytes, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # health probes / model lists
        self._respond(b'{"data":[]}')

    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            body = json.loads(raw)
        except Exception:
            body = {}
        type(self).records.append(
            {
                "path": self.path,
                "model": body.get("model"),
                "bytes": len(raw),
                "tokens": count_tokens(body),
                "n_messages": len(body.get("messages") or []),
                "n_tools": len(body.get("tools") or []),
            }
        )
        # Anthropic-shaped reply; the OpenAI paths tolerate the extra keys.
        self._respond(
            json.dumps(
                {
                    "id": "msg_harness",
                    "type": "message",
                    "role": "assistant",
                    "model": body.get("model", MODEL),
                    "content": [{"type": "text", "text": "ok"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 2},
                }
            ).encode()
        )


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ---------------------------------------------------------------------------
# Payload corpus — one shape per compressor route
# ---------------------------------------------------------------------------


def _tool_result(text: str, tool_id: str = "t1") -> dict[str, Any]:
    return {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": text}],
    }


def _tool_use(tool_id: str = "t1", name: str = "Bash") -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": {"cmd": "x"}}],
    }


def corpus(kind: str, n: int = 400) -> str:
    if kind == "logs":
        return "\n".join(
            f"2026-07-27T10:{i % 60:02d}:00Z INFO  worker-{i % 8} handled request id=req_{i} "
            f"path=/v1/items status=200 duration_ms={20 + i % 90}"
            for i in range(n)
        )
    if kind == "code":
        return "\n".join(
            f"def handler_{i}(request, context):\n"
            f"    payload = request.get('data', {{}})\n"
            f"    return {{'id': {i}, 'ok': True, 'payload': payload}}\n"
            for i in range(n // 3)
        )
    if kind == "prose":
        return " ".join(
            f"The subsystem performs step {i} of the documented workflow and records the outcome "
            f"for later auditing purposes."
            for i in range(n // 2)
        )
    if kind == "table":
        rows = "\n".join(
            f"| item-{i} | {i * 3} | {'active' if i % 2 else 'idle'} | region-{i % 5} |"
            for i in range(n)
        )
        return "| name | count | state | region |\n|---|---|---|---|\n" + rows
    if kind == "json":
        return json.dumps(
            [{"id": i, "name": f"row-{i}", "state": "active", "tags": ["a", "b"]} for i in range(n)]
        )
    if kind == "html":
        body = "".join(
            f"<div class='row'><span>item {i}</span><em>{i * 2}</em></div>" for i in range(n)
        )
        return f"<html><head><style>.row{{color:red}}</style></head><body>{body}</body></html>"
    if kind == "mixed_logs":
        # Several templates interleaved. Uniform logs already compress ~99%
        # via the standard path, so they cannot show whether drain3 adds
        # anything; template variety is what drain3 is for.
        return "\n".join(
            (
                f"2026-07-27T10:{i % 60:02d}:00Z ERROR db timeout after {i}ms on shard-{i % 4}"
                if i % 5 == 0
                else (
                    f"2026-07-27T10:{i % 60:02d}:00Z WARN  cache miss key=k_{i} tier={i % 3}"
                    if i % 3 == 0
                    else f"2026-07-27T10:{i % 60:02d}:00Z INFO  worker-{i % 8} "
                    f"handled request id=req_{i} status=200"
                )
            )
            for i in range(n)
        )
    if kind == "diff":
        # A unified diff dominated by reformatting with one semantic change —
        # difftastic's whole reason to exist. It only ever sees Bash output.
        old = "\n".join(f"def fn_{i}(a,b):\n    return a+b+{i}" for i in range(n // 6))
        new = "\n".join(
            f"def fn_{i}(\n    a,\n    b,\n):\n    return a + b + {i if i != 3 else 999}"
            for i in range(n // 6)
        )
        return _unified_diff(old, new)
    raise ValueError(kind)


def _unified_diff(old: str, new: str) -> str:
    """Render a real `git diff` so the difftastic matcher recognises it."""
    tmp = Path(tempfile.mkdtemp(prefix="cutctx-harness-diff-"))
    (tmp / "a.py").write_text(old)
    (tmp / "b.py").write_text(new)
    return subprocess.run(
        ["git", "diff", "--no-index", "--", str(tmp / "a.py"), str(tmp / "b.py")],
        capture_output=True,
        text=True,
    ).stdout


def deep_history(kind: str, turns: int = 6, tool_name: str = "Bash") -> list[dict[str, Any]]:
    """Multi-turn history so content sits outside the protected live zone.

    Compression deliberately leaves the most recent turn alone; a single-turn
    payload therefore measures nothing. This was the first thing that misled
    me when checking the compressor by hand.

    ``tool_name`` matters for any engine that gates on it. The memoizer only
    caches read-only tools, so a corpus built from "Bash" calls could never
    exercise it — the scenario measured the semantic cache and credited the
    memoizer.
    """
    msgs: list[dict[str, Any]] = []
    for t in range(turns):
        msgs.append({"role": "user", "content": f"step {t}: inspect the system"})
        msgs.append(_tool_use(f"t{t}", name=tool_name))
        msgs.append(_tool_result(corpus(kind), f"t{t}"))
        msgs.append({"role": "assistant", "content": f"Observed step {t}."})
    msgs.append({"role": "user", "content": "Summarise briefly."})
    return msgs


def fat_tools(n: int = 40) -> list[dict[str, Any]]:
    """A tool surface wide enough for schema compaction to matter."""
    return [
        {
            "name": f"tool_{i}",
            "description": (
                f"Tool number {i}. "
                + "It performs a well documented operation on the workspace. " * 6
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    f"arg_{j}": {
                        "type": "string",
                        "description": f"Argument {j} " + "described at length. " * 4,
                    }
                    for j in range(6)
                },
                "required": ["arg_0"],
            },
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    name: str
    why: str
    env: dict[str, str] = field(default_factory=dict)
    args: list[str] = field(default_factory=list)
    #: Use `python -m cutctx.proxy.server` instead of the `cutctx proxy` CLI.
    #: Needed for engines the supported CLI exposes no flag for.
    raw_server: bool = False
    body: dict[str, Any] = field(default_factory=dict)
    repeat: int = 1
    expect_savings: bool = True
    default_on: bool = False
    #: When set, the scenario passes only if upstream received this model.
    expect_upstream_model: str | None = None
    #: Client User-Agent. Drives auth-mode classification, which decides
    #: whether lossy compressors are allowed at all — see SUBSCRIPTION vs
    #: PAYG in cutctx/proxy/auth_mode.py.
    ua: str = "claude-cli/2.1.214 (external, cli)"


def scenarios() -> list[Scenario]:
    base = {"model": MODEL, "max_tokens": 64}
    out: list[Scenario] = []

    # --- on by default -----------------------------------------------------
    for kind in ("logs", "code", "prose", "table", "json", "html"):
        out.append(
            Scenario(
                name=f"compression:{kind}",
                why=f"aggregate compressor on {kind} content",
                body={**base, "messages": deep_history(kind)},
                default_on=True,
            )
        )
    PAYG_UA = "python-httpx/0.27"
    for kind in ("code", "prose", "table", "json", "html"):
        out.append(
            Scenario(
                name=f"compression:{kind}:payg",
                why=f"same {kind} payload as a PAYG client (lossy compressors permitted)",
                body={**base, "messages": deep_history(kind)},
                ua=PAYG_UA,
                default_on=True,
            )
        )
    for kind in ("code", "json", "html"):
        out.append(
            Scenario(
                name=f"compression:{kind}:aggressive",
                why=f"{kind} with --compression-mode aggressive",
                args=["--compression-mode", "aggressive"],
                body={**base, "messages": deep_history(kind)},
                default_on=False,
            )
        )
    out.append(
        Scenario(
            name="tool_schema_compaction",
            why="wide tool surface should be slimmed before it is billed",
            body={**base, "tools": fat_tools(), "messages": deep_history("prose", turns=2)},
            default_on=True,
        )
    )
    out.append(
        Scenario(
            name="semantic_cache",
            why="identical repeat request should not reach upstream twice",
            body={**base, "messages": deep_history("logs", turns=3)},
            repeat=2,
            default_on=True,
        )
    )

    # --- opt-in ------------------------------------------------------------
    # Routing is judged on the model that leaves, not on tokens: a one-line
    # prompt is far too small for byte savings to mean anything.
    out.append(
        Scenario(
            name="model_routing",
            why="sonnet request should leave as haiku (codex-gpt54mini-high)",
            env={"CUTCTX_MODEL_ROUTING_PRESET": "codex-gpt54mini-high"},
            body={
                "model": ROUTING_SOURCE_MODEL,
                "max_tokens": 64,
                "messages": [{"role": "user", "content": "hello"}],
            },
            expect_savings=False,
            expect_upstream_model=MODEL,
        )
    )
    # The Anthropic-named preset sets require_calibrated_scorer=True, so with
    # no scorer artifact configured it routes *nothing* and says nothing. An
    # operator picking it by name gets silent no-op routing; pinned here so
    # that stays a known property rather than a surprise.
    out.append(
        Scenario(
            name="model_routing:uncalibrated_preset_is_noop",
            why="claude-three-tier-eval needs a calibrated scorer; without one it must not route",
            env={"CUTCTX_MODEL_ROUTING_PRESET": "claude-three-tier-eval"},
            body={
                "model": ROUTING_SOURCE_MODEL,
                "max_tokens": 64,
                "messages": [{"role": "user", "content": "hello"}],
            },
            expect_savings=False,
            expect_upstream_model=ROUTING_SOURCE_MODEL,
        )
    )
    out.append(
        Scenario(
            name="drain3",
            why="log-template mining across MIXED templates (uniform logs "
            "already compress ~99% without it, so they prove nothing)",
            args=["--drain3"],
            body={**base, "messages": deep_history("mixed_logs")},
        )
    )
    out.append(
        Scenario(
            name="knowledge_graph_graphify",
            why="Graphify knowledge-graph compression on code",
            args=["--knowledge-graph"],
            body={**base, "messages": deep_history("code")},
        )
    )
    out.append(
        Scenario(
            name="difftastic",
            why="structural diff compression; only matches Bash output that is a real unified diff",
            args=["--difftastic"],
            body={**base, "messages": deep_history("diff")},
        )
    )
    out.append(
        Scenario(
            name="dedup",
            why="repeated identical tool_result blocks should collapse",
            args=["--enable-semantic-dedup"],
            body={**base, "messages": deep_history("json")},
        )
    )
    out.append(
        Scenario(
            name="context_budget",
            why="hard token ceiling — needs a payload that exceeds it",
            args=["--enable-context-budget", "--context-budget-max-tokens", "4000"],
            body={**base, "messages": deep_history("json")},
        )
    )
    out.append(
        Scenario(
            name="memoization",
            why="identical tool results served from the memoizer (--memoize); "
            "must use a read-only tool name or the memoizer never engages",
            args=["--memoize"],
            body={**base, "messages": deep_history("json", turns=3, tool_name="Read")},
            repeat=2,
        )
    )
    return out


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_scenario(sc: Scenario, *, verbose: bool = False) -> dict[str, Any]:
    _Capture.records = []
    up_port, proxy_port = _free_port(), _free_port()
    httpd = HTTPServer(("127.0.0.1", up_port), _Capture)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    # Outside the repo on purpose. Engines that fetch helper binaries (the
    # difftastic scenario pulls a ~108MB `difft`) would otherwise drop them
    # into the working tree, where `git add -A` happily commits them and the
    # push is rejected for exceeding GitHub's 100MB file limit.
    home = Path(tempfile.gettempdir()) / "cutctx-savings-harness-home"
    home.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "HOME": str(home),  # keep the operator's licence out of the measurement
        "CUTCTX_TELEMETRY": "off",
        "PYTHONPATH": str(REPO),
        **sc.env,
    }
    env.pop("CUTCTX_LICENSE_KEY", None)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "cutctx.proxy.server" if sc.raw_server else "cutctx.cli.main",
            *([] if sc.raw_server else ["proxy"]),
            "--host",
            "127.0.0.1",
            "--port",
            str(proxy_port),
            "--anthropic-api-url",
            f"http://127.0.0.1:{up_port}",
            *sc.args,
        ],
        cwd=REPO,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        import httpx

        base = f"http://127.0.0.1:{proxy_port}"
        for _ in range(120):
            time.sleep(1)
            if proc.poll() is not None:
                return {
                    "scenario": sc.name,
                    "error": "proxy exited",
                    "log": (proc.stdout.read() or "")[-800:],
                }
            try:
                # Any HTTP answer means the server is accepting connections.
                # Deliberately not gating on /readyz being *ready*: against a
                # synthetic upstream the upstream health probe never goes
                # green, yet the proxy serves /v1/messages perfectly well.
                httpx.get(f"{base}/livez", timeout=2)
                break
            except Exception:
                continue
        else:
            return {"scenario": sc.name, "error": "proxy never became ready"}

        sent = count_tokens(sc.body)
        for _ in range(sc.repeat):
            httpx.post(
                f"{base}/v1/messages",
                json=sc.body,
                headers={
                    "x-api-key": "sk-harness",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                    "user-agent": sc.ua,
                },
                timeout=120,
            )

        recs = list(_Capture.records)
        upstream = sum(r["tokens"] for r in recs)
        billed_client = sent * sc.repeat
        saved = billed_client - upstream
        try:
            stats = httpx.get(f"{base}/stats", timeout=10).json()
            by_source = stats.get("summary", {})
            funnel = stats.get("opportunity_funnel", {})
        except Exception:
            by_source, funnel = {}, {}
        return {
            "scenario": sc.name,
            "why": sc.why,
            "default_on": sc.default_on,
            "client_tokens": billed_client,
            "upstream_tokens": upstream,
            "saved_tokens": saved,
            "saved_pct": round(saved / billed_client * 100, 1) if billed_client else 0.0,
            "upstream_calls": len(recs),
            "requests_sent": sc.repeat,
            "models_upstream": sorted({r["model"] for r in recs if r["model"]}),
            "proxy_reported_pct": by_source.get("savings_percent"),
            "expect_savings": sc.expect_savings,
            "auth_mode_ua": sc.ua,
            "decline_reasons": (funnel or {}).get("decline_reasons"),
            "funnel": {k: v for k, v in (funnel or {}).items() if k != "decline_reasons"},
            "expect_upstream_model": sc.expect_upstream_model,
            "model_ok": (
                None
                if sc.expect_upstream_model is None
                else all(
                    m == sc.expect_upstream_model for m in {r["model"] for r in recs if r["model"]}
                )
            ),
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()
        httpd.shutdown()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()

    all_sc = scenarios()
    if a.list:
        for s in all_sc:
            print(f"  {'default' if s.default_on else 'opt-in ':<8} {s.name:<32} {s.why}")
        return 0

    chosen = (
        [s for s in all_sc if s.name in a.scenario] if a.scenario else (all_sc if a.all else [])
    )
    if not chosen:
        ap.error("pass --all, --scenario NAME, or --list")

    results = []
    for s in chosen:
        r = run_scenario(s)
        results.append(r)
        if "error" in r:
            print(f"  ERROR    {s.name}: {r['error']}")
        else:
            ok = (r["saved_tokens"] > 0) if s.expect_savings else True
            if r.get("model_ok") is False:
                ok = False
            flag = "OK  " if ok else "NONE"
            print(
                f"  {flag}  {s.name:<32} {r['client_tokens']:>7} -> {r['upstream_tokens']:<7}"
                f" saved {r['saved_pct']:>5}%  calls={r['upstream_calls']}/{r['requests_sent']}"
                f"  models={','.join(r['models_upstream']) or '-'}"
            )

    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(results, indent=2) + "\n")
        print(f"\nwrote {a.json}")

    return 0 if all("error" not in r for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

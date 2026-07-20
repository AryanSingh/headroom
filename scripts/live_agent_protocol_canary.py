#!/usr/bin/env python3
"""Live Codex/Claude restart-resume canary with sanitized summary artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from cutctx.capture.fixture_safety import assert_fixture_safe, sanitize_capture_record


def is_retryable_status(status: int) -> bool:
    return status == 429 or 500 <= status <= 599


def _walk_ids(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"thread_id", "session_id"} and isinstance(child, str):
                yield child
            yield from _walk_ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_ids(child)


def extract_session_id(output: str) -> str | None:
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for candidate in _walk_ids(event):
            if re.fullmatch(r"[0-9a-fA-F-]{32,36}", candidate):
                return candidate
    return None


def _event_summary(output: str) -> dict[str, Any]:
    event_types: list[str] = []
    terminal = False
    semantic_parts: list[str] = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        if isinstance(event_type, str):
            event_types.append(event_type)
            terminal = terminal or event_type in {
                "turn.completed",
                "result",
                "message_stop",
                "response.completed",
            }
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            semantic_parts.append(str(item.get("text") or ""))
        if event_type == "result":
            semantic_parts.append(str(event.get("result") or ""))
    semantic = "\n".join(semantic_parts)
    return {
        "event_types": event_types,
        "terminal": terminal,
        "semantic_sha256": hashlib.sha256(semantic.encode()).hexdigest() if semantic else None,
    }


def _detected_status(output: str) -> int | None:
    for pattern in (r'"status(?:_code)?"\s*:\s*(\d{3})', r"\bHTTP\s+(\d{3})\b"):
        match = re.search(pattern, output, re.I)
        if match:
            return int(match.group(1))
    return None


def _run_with_retry(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    last: subprocess.CompletedProcess[str] | None = None
    for attempt in range(3):
        last = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        if last.returncode == 0:
            return last
        status = _detected_status(last.stdout)
        if attempt == 2 or status is None or not is_retryable_status(status):
            break
        time.sleep(2**attempt)
    assert last is not None
    raise RuntimeError(
        f"client command failed rc={last.returncode} status={_detected_status(last.stdout)}"
    )


class ProxyProcess:
    def __init__(self, *, port: int, budget: float, cwd: Path) -> None:
        self.port = port
        self.budget = budget
        self.cwd = cwd
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        env = dict(os.environ)
        env.update(
            {
                "CUTCTX_TELEMETRY": "off",
                "CUTCTX_LOG_MESSAGES": "0",
                "CUTCTX_NO_SUBSCRIPTION_TRACKING": "1",
            }
        )
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "cutctx.cli",
                "proxy",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--budget",
                str(self.budget),
                "--no-cache",
                "--no-rate-limit",
                "--no-subscription-tracking",
            ],
            cwd=self.cwd,
            env=env,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("Cutctx proxy exited before becoming ready")
            try:
                with urlopen(f"http://127.0.0.1:{self.port}/readyz", timeout=1) as response:
                    if response.status == 200:
                        return
            except OSError:
                time.sleep(0.2)
        raise RuntimeError("Cutctx proxy did not become ready")

    def stop(self) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.process = None

    def restart(self) -> None:
        self.stop()
        self.start()


def _client_version(binary: str) -> str:
    result = subprocess.run(
        [binary, "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=True,
    )
    return result.stdout.strip()


def _run_codex(
    binary: str,
    *,
    repo: Path,
    proxy_url: str,
    timeout: int,
    proxy: ProxyProcess,
) -> dict[str, Any]:
    env = dict(os.environ)
    env["OPENAI_BASE_URL"] = f"{proxy_url}/v1"
    prompt = (
        "Use one read-only shell command to count bytes in fixture.txt, "
        "then answer with only that integer."
    )
    first = _run_with_retry(
        [
            binary,
            "exec",
            "--json",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "-C",
            str(repo),
            prompt,
        ],
        cwd=repo,
        env=env,
        timeout=timeout,
    )
    session_id = extract_session_id(first.stdout)
    if not session_id:
        raise RuntimeError("Codex did not emit a session ID")
    proxy.restart()
    resumed = _run_with_retry(
        [
            binary,
            "exec",
            "resume",
            "--json",
            "--skip-git-repo-check",
            session_id,
            "Reply with the same integer again and no other text.",
        ],
        cwd=repo,
        env=env,
        timeout=timeout,
    )
    return {
        "session_id": session_id,
        "first": _event_summary(first.stdout),
        "resumed": _event_summary(resumed.stdout),
    }


def _run_claude(
    binary: str,
    *,
    repo: Path,
    proxy_url: str,
    timeout: int,
    proxy: ProxyProcess,
) -> dict[str, Any]:
    env = dict(os.environ)
    env["ANTHROPIC_BASE_URL"] = proxy_url
    session_id = str(uuid.uuid4())
    common = [
        binary,
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        "3",
        "--allowedTools",
        "Read",
    ]
    first = _run_with_retry(
        common
        + [
            "--session-id",
            session_id,
            "-p",
            "Use the Read tool once on fixture.txt, then answer with only its byte count.",
        ],
        cwd=repo,
        env=env,
        timeout=timeout,
    )
    proxy.restart()
    resumed = _run_with_retry(
        common
        + [
            "--resume",
            session_id,
            "-p",
            "Reply with the same byte count again and no other text.",
        ],
        cwd=repo,
        env=env,
        timeout=timeout,
    )
    return {
        "session_id": session_id,
        "first": _event_summary(first.stdout),
        "resumed": _event_summary(resumed.stdout),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=("codex", "claude"), required=True)
    parser.add_argument("--binary")
    parser.add_argument("--port", type=int, default=18787)
    parser.add_argument("--budget-usd", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    if args.budget_usd <= 0 or args.budget_usd > 5:
        parser.error("--budget-usd must be greater than 0 and no more than 5")

    binary = args.binary or shutil.which(args.client)
    if not binary:
        parser.error(f"{args.client} CLI is not installed")
    required_secret = "OPENAI_API_KEY" if args.client == "codex" else "ANTHROPIC_API_KEY"
    has_codex_auth = bool(
        os.environ.get("CODEX_HOME") and (Path(os.environ["CODEX_HOME"]) / "auth.json").is_file()
    )
    if not os.environ.get(required_secret) and not (args.client == "codex" and has_codex_auth):
        parser.error(f"{required_secret} is required for the live canary")

    with tempfile.TemporaryDirectory(prefix=f"cutctx-{args.client}-canary-") as temp:
        repo = Path(temp)
        (repo / "fixture.txt").write_text("fixture-data\n" * 64, encoding="utf-8")
        (repo / "fixture.txt").chmod(0o444)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        proxy = ProxyProcess(port=args.port, budget=args.budget_usd, cwd=repo)
        try:
            proxy.start()
            runner = _run_codex if args.client == "codex" else _run_claude
            result = runner(
                binary,
                repo=repo,
                proxy_url=f"http://127.0.0.1:{args.port}",
                timeout=args.timeout_seconds,
                proxy=proxy,
            )
        finally:
            proxy.stop()

    summary = sanitize_capture_record(
        {
            "schema_version": 1,
            "client": args.client,
            "client_version": _client_version(binary),
            "proxy_restarted": True,
            "budget_usd": args.budget_usd,
            **result,
        }
    )
    assert_fixture_safe(summary)
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.artifact.chmod(0o600)
    if not summary["first"]["terminal"] or not summary["resumed"]["terminal"]:
        raise RuntimeError("live canary did not observe terminal events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

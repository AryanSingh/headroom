"""Live Cursor IDE app session verification against a running Cutctx proxy."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import httpx
import pytest

from cutctx.providers.cursor.config import apply_proxy_config
from cutctx.providers.cursor.hooks import ensure_project_hooks

pytest.importorskip("fastapi")


class _UpstreamHandler(BaseHTTPRequestHandler):
    calls: list[tuple[str, str]] = []

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def do_POST(self) -> None:
        self.__class__.calls.append((self.path, self.headers.get("User-Agent", "")))
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if self.path.endswith("/messages"):
            payload = {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "ok"}],
                "model": "claude-3-5-sonnet-20241022",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 5, "output_tokens": 2},
            }
        else:
            payload = {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "choices": [{"message": {"role": "assistant", "content": "ok"}, "index": 0}],
            }
        self.wfile.write(json.dumps(payload).encode("utf-8"))


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def upstream_server() -> str:
    _UpstreamHandler.calls = []
    server = HTTPServer(("127.0.0.1", 0), _UpstreamHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_cursor_ide_app_session_routes_openai_and_anthropic_byok(
    tmp_path: Path,
    upstream_server: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulate a Cursor IDE BYOK session using project config written by wrap."""
    monkeypatch.chdir(tmp_path)
    proxy_port = _free_port()
    repo_root = Path(__file__).resolve().parents[1]

    apply_proxy_config(port=proxy_port, project="cursor-ide-live")
    hooks_path = ensure_project_hooks()
    config = json.loads((tmp_path / ".cursor" / "config.json").read_text(encoding="utf-8"))
    assert hooks_path.exists()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)
    env["CUTCTX_SAVINGS_PATH"] = str(tmp_path / "savings.json")
    env["OPENAI_TARGET_API_URL"] = f"{upstream_server}/v1"
    env["ANTHROPIC_TARGET_API_URL"] = upstream_server

    proxy = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "cutctx.cli",
            "proxy",
            "--port",
            str(proxy_port),
            "--no-telemetry",
        ],
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            if proxy.poll() is not None:
                output = proxy.stdout.read() if proxy.stdout is not None else ""
                pytest.fail(f"proxy exited early:\n{output}")
            try:
                if (
                    httpx.get(f"http://127.0.0.1:{proxy_port}/livez", timeout=1.0).status_code
                    == 200
                ):
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            output = proxy.stdout.read() if proxy.stdout is not None else ""
            pytest.fail(f"proxy did not become ready:\n{output}")

        openai_url = config["openai"]["baseUrl"].rstrip("/") + "/chat/completions"
        anthropic_url = config["anthropic"]["baseUrl"].rstrip("/") + "/v1/messages"

        openai_response = httpx.post(
            openai_url,
            headers={
                "User-Agent": "cursor/1.2.3",
                "Authorization": "Bearer sk-test",
                "Content-Type": "application/json",
            },
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "ping"}]},
            timeout=10.0,
        )
        assert openai_response.status_code == 200, openai_response.text

        anthropic_response = httpx.post(
            anthropic_url,
            headers={
                "User-Agent": "cursor/1.2.3",
                "x-api-key": "sk-ant-test",
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 16,
                "messages": [{"role": "user", "content": "ping"}],
            },
            timeout=10.0,
        )
        assert anthropic_response.status_code == 200, anthropic_response.text

        user_agents = {ua for _, ua in _UpstreamHandler.calls}
        assert len(_UpstreamHandler.calls) >= 2
        assert any("cursor" in (ua or "").lower() for ua in user_agents)
        assert any(path.endswith("/chat/completions") for path, _ in _UpstreamHandler.calls)
        assert any(path.endswith("/v1/messages") for path, _ in _UpstreamHandler.calls)

        stats = httpx.get(f"http://127.0.0.1:{proxy_port}/stats", timeout=5.0).json()
        recent = stats.get("recent_requests") or []
        if recent:
            session_entries = [
                entry
                for entry in recent
                if (entry.get("tags") or {}).get("project") == "cursor-ide-live"
            ]
            assert session_entries
            assert all(
                (entry.get("tags") or {}).get("client") == "cursor" for entry in session_entries
            )
    finally:
        proxy.kill()
        proxy.wait(timeout=5)

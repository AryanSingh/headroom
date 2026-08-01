"""Live integration checks for Cursor Agent CLI + Cutctx proxy wiring."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
import pytest

from cutctx.providers.cursor.cli import build_agent_launch_args, find_agent_cli

_AGENT_BIN = find_agent_cli()

pytestmark = pytest.mark.skipif(
    _AGENT_BIN is None,
    reason="Cursor Agent CLI is not installed",
)


class _AuthExchangeHandler(BaseHTTPRequestHandler):
    hits: list[str] = []

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def do_POST(self) -> None:
        self.__class__.hits.append(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"accessToken": "test-token"}).encode("utf-8"))


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def upstream_server() -> str:
    _AuthExchangeHandler.hits = []
    server = HTTPServer(("127.0.0.1", 0), _AuthExchangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_cursor_agent_routes_auth_through_cutctx_proxy(
    tmp_path: Path,
    upstream_server: str,
) -> None:
    """Cursor CLI should POST auth traffic to the configured Cutctx endpoint."""
    # Use the same discovery result that decided whether this module should
    # run. Earlier tests may temporarily alter PATH or discovery state; doing
    # a second lookup here made this live test order-dependent.
    agent_bin = _AGENT_BIN
    assert agent_bin is not None

    proxy_port = _free_port()
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)
    env["CUTCTX_SAVINGS_PATH"] = str(tmp_path / "savings.json")
    env["CURSOR_TARGET_API_URL"] = upstream_server
    # The proxy runs as a child process, so the conftest fixture that keeps
    # the suite off the operator's activated licence cannot reach it. Without
    # a private HOME the child resolves ~/.cutctx, entitlements rise above
    # builder, the paid seat gate engages, and these unauthenticated requests
    # come back 401 on a developer machine while passing in CI.
    env["HOME"] = str(tmp_path / "home")
    env.pop("CUTCTX_LICENSE_KEY", None)
    env.pop("CUTCTX_USER_TOKEN_HMAC_SECRET", None)
    (tmp_path / "home").mkdir(exist_ok=True)

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
            try:
                response = httpx.get(f"http://127.0.0.1:{proxy_port}/livez", timeout=1.0)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if proxy.poll() is not None:
                output = proxy.stdout.read() if proxy.stdout is not None else ""
                pytest.fail(f"Cutctx proxy exited early:\n{output}")
            time.sleep(0.5)
        else:
            output = proxy.stdout.read() if proxy.stdout is not None else ""
            pytest.fail(f"Cutctx proxy did not become ready:\n{output}")

        passthrough = httpx.post(
            f"http://127.0.0.1:{proxy_port}/p/cursor-live/auth/exchange_user_api_key",
            headers={"X-Client": "cursor", "Content-Type": "application/json"},
            json={},
            timeout=10.0,
        )
        assert passthrough.status_code == 200, passthrough.text
        assert _AuthExchangeHandler.hits, "expected Cursor subscription passthrough"
        assert any("/auth/exchange_user_api_key" in path for path in _AuthExchangeHandler.hits)

        launch_args = build_agent_launch_args(
            port=proxy_port,
            project="cursor-live",
            extra_args=("--api-key", "sk-test-cursor-proxy", "noop"),
        )
        agent_result = subprocess.run(
            [str(agent_bin), *launch_args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={
                **env,
                "CURSOR_API_ENDPOINT": f"http://127.0.0.1:{proxy_port}/p/cursor-live",
            },
        )
        assert (
            agent_result.returncode == 0
            or "invalid" in (agent_result.stdout + agent_result.stderr).lower()
        )
    finally:
        proxy.kill()
        proxy.wait(timeout=5)

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO_ROOT / "plugins" / "openclaw"
SDK_DIR = REPO_ROOT / "sdk" / "typescript"
RTK_MARKER = "<!-- cutctx:rtk-instructions -->"
PROXY_PORT = 28887
CODEX_PORT = 28888
AIDER_PORT = 28889
CURSOR_PORT = 28890
OPENCLAW_PROXY_PORT = 28891
# Phase G PR-G1: new wrap subcommands. Smoke-tested via --prepare-only since
# their CLIs may not exist on the e2e image and the wrap commands without
# --prepare-only block on the proxy. The wiring is otherwise covered by the
# unit tests in tests/test_cli/test_wrap_{cline,continue,goose,openhands}.py.
CLINE_PORT = 28892
CONTINUE_PORT = 28893
GOOSE_PORT = 28894
OPENHANDS_PORT = 28895
WINDSURF_PORT = 28896
ZED_PORT = 28897
OPENCODE_PORT = 28898


def log(message: str) -> None:
    print(f"[wrap-e2e] {message}", flush=True)


def run(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    log(f"$ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        env=env,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.stdout.strip():
        print(result.stdout.rstrip(), flush=True)
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr, flush=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(cmd)}")
    return result


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class MockOpenAIServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, MockOpenAIHandler)
        self.requests: list[dict[str, Any]] = []


class MockOpenAIHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _record(self, body: dict[str, Any] | None = None) -> None:
        server = self.server
        assert isinstance(server, MockOpenAIServer)
        server.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": body,
            }
        )

    def do_GET(self) -> None:  # noqa: N802
        self._record()
        if self.path == "/v1/models":
            self._write_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": "gpt-4o-mini",
                            "object": "model",
                            "owned_by": "openai",
                        }
                    ],
                },
            )
            return
        self._write_json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b""
        payload = json.loads(raw_body.decode("utf-8") or "{}")
        self._record(body=payload)
        if self.path == "/v1/chat/completions":
            self._write_json(
                200,
                {
                    "id": "chatcmpl-e2e",
                    "object": "chat.completion",
                    "created": 0,
                    "model": payload.get("model", "gpt-4o-mini"),
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": "mock completion from upstream",
                            },
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 5,
                        "total_tokens": 17,
                    },
                },
            )
            return
        self._write_json(404, {"error": {"message": "not found"}})


def wait_for_http(url: str, *, timeout: int = 30) -> httpx.Response:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code < 500:
                return response
        except Exception as exc:  # pragma: no cover - best effort retry surface
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def wait_for_output(proc: subprocess.Popen[str], text: str, *, timeout: int = 30) -> str:
    deadline = time.time() + timeout
    chunks: list[str] = []
    while time.time() < deadline:
        if proc.stdout is None:
            break
        line = proc.stdout.readline()
        if line:
            chunks.append(line)
            if text in "".join(chunks):
                return "".join(chunks)
        elif proc.poll() is not None:
            break
    output = "".join(chunks)
    raise RuntimeError(f"Timed out waiting for process output '{text}'. Output so far:\n{output}")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def create_shims(shim_dir: Path) -> None:
    generic_shim = textwrap.dedent(
        """\
        #!/usr/bin/env python3
        from __future__ import annotations

        import json
        import os
        import sys
        import urllib.request
        from pathlib import Path

        tool = Path(sys.argv[0]).name
        log_dir = Path(os.environ["CUTCTX_E2E_LOG_DIR"])
        log_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "tool": tool,
            "argv": sys.argv[1:],
            "cwd": os.getcwd(),
            "env": {
                key: os.environ.get(key)
                for key in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "ANTHROPIC_BASE_URL")
                if os.environ.get(key) is not None
            },
        }

        probes = []

        def fetch(url: str, *, headers: dict[str, str] | None = None) -> None:
            request = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(request, timeout=10) as response:
                probes.append({"url": url, "status": response.status})

        openai_base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
        if openai_base:
            admin_key = os.environ.get("CUTCTX_ADMIN_API_KEY")
            headers = {"X-Cutctx-Admin-Key": admin_key} if admin_key else None
            fetch(f"{openai_base.rstrip('/')}/models", headers=headers)

        anthropic_base = os.environ.get("ANTHROPIC_BASE_URL")
        if anthropic_base:
            fetch(f"{anthropic_base.rstrip('/')}/health")

        record["probes"] = probes

        with (log_dir / f"{tool}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\\n")
        print(f"{tool} shim executed")
        raise SystemExit(0)
        """
    )
    codex_shim = textwrap.dedent(
        """\
        #!/usr/bin/env python3
        from __future__ import annotations

        import json
        import os
        import sys
        import urllib.request
        from pathlib import Path

        tool = Path(sys.argv[0]).name
        log_dir = Path(os.environ["CUTCTX_E2E_LOG_DIR"])
        log_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "tool": tool,
            "argv": sys.argv[1:],
            "cwd": os.getcwd(),
            "env": {
                key: os.environ.get(key)
                for key in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "ANTHROPIC_BASE_URL")
                if os.environ.get(key) is not None
            },
        }

        probes = []

        def request_json(
            url: str,
            *,
            payload: dict[str, object] | None = None,
            headers: dict[str, str] | None = None,
        ) -> tuple[int, dict[str, object]]:
            data = None if payload is None else json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(url, data=data, headers=headers or {})
            if payload is not None:
                request.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read()
                body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
                return response.status, body

        openai_base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
        if openai_base:
            auth_headers = {"Authorization": "Bearer test-key"}
            models_status, _models_body = request_json(
                f"{openai_base.rstrip('/')}/models",
                headers=auth_headers,
            )
            probes.append({"url": f"{openai_base.rstrip('/')}/models", "status": models_status})

            model_name = "cutctx-wrap-e2e"
            chat_status, chat_body = request_json(
                f"{openai_base.rstrip('/')}/chat/completions",
                payload={
                    "model": model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Confirm Cutctx received this wrapped Codex message.",
                        }
                    ],
                },
                headers=auth_headers,
            )
            probes.append(
                {"url": f"{openai_base.rstrip('/')}/chat/completions", "status": chat_status}
            )
            record["chat_completion"] = (
                chat_body.get("choices", [{}])[0].get("message", {}).get("content")
            )

            stats_url = openai_base.rstrip("/").removesuffix("/v1") + "/stats"
            stats_status, stats_body = request_json(stats_url, headers=auth_headers)
            probes.append({"url": stats_url, "status": stats_status})
            requests = stats_body.get("requests", {})
            by_model = requests.get("by_model", {}) if isinstance(requests, dict) else {}
            record["cutctx_request_total"] = (
                requests.get("total") if isinstance(requests, dict) else None
            )
            record["cutctx_model_count"] = (
                by_model.get(model_name) if isinstance(by_model, dict) else None
            )

        record["probes"] = probes

        with (log_dir / f"{tool}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\\n")
        print(f"{tool} shim executed")
        raise SystemExit(0)
        """
    )
    rtk_shim = textwrap.dedent(
        """\
        #!/usr/bin/env python3
        from __future__ import annotations

        import sys

        if "--version" in sys.argv:
            print("rtk e2e-shim")
        else:
            print("rtk shim")
        raise SystemExit(0)
        """
    )
    write_executable(shim_dir / "claude", generic_shim)
    write_executable(shim_dir / "codex", codex_shim)
    write_executable(shim_dir / "aider", generic_shim)
    write_executable(shim_dir / "rtk", rtk_shim)


def start_mock_server(port: int) -> tuple[MockOpenAIServer, threading.Thread]:
    server = MockOpenAIServer(("127.0.0.1", port))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def start_proxy(port: int, env: dict[str, str]) -> subprocess.Popen[str]:
    log(f"Starting cutctx proxy on port {port}")
    proc = subprocess.Popen(
        ["cutctx", "proxy", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    wait_for_http(f"http://127.0.0.1:{port}/health", timeout=30)
    return proc


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGINT)
    try:
        proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate(timeout=5)


def wait_for_command_success(
    cmd: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    deadline = time.time() + timeout
    last_output = ""
    while time.time() < deadline:
        remaining = deadline - time.time()
        per_call_timeout = max(1.0, min(5.0, remaining))
        try:
            result = subprocess.run(
                cmd,
                env=env,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=per_call_timeout,
            )
        except subprocess.TimeoutExpired:
            last_output = f"Command timed out after {per_call_timeout:.1f}s"
            time.sleep(1)
            continue
        if result.returncode == 0:
            if result.stdout.strip():
                print(result.stdout.rstrip(), flush=True)
            if result.stderr.strip():
                print(result.stderr.rstrip(), file=sys.stderr, flush=True)
            return result
        last_output = "\n".join(
            part for part in (result.stdout.strip(), result.stderr.strip()) if part
        )
        time.sleep(1)
    raise RuntimeError(
        f"Timed out waiting for command to succeed: {' '.join(cmd)}\nLast output:\n{last_output}"
    )


def start_openclaw_gateway(env: dict[str, str], cwd: Path) -> subprocess.Popen[str]:
    log("Starting OpenClaw gateway for e2e verification")
    return subprocess.Popen(
        ["openclaw", "gateway"],
        env=env,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def stop_openclaw_gateway(env: dict[str, str], cwd: Path) -> None:
    log("Stopping OpenClaw gateway after e2e verification")
    run(["openclaw", "gateway", "stop"], env=env, cwd=cwd, timeout=60)


def find_aider_python() -> str | None:
    """Locate a Python interpreter for the installed aider environment."""
    explicit = os.environ.get("CUTCTX_E2E_AIDER_PYTHON")
    if explicit:
        return explicit

    docker_default = Path("/opt/aider-venv/bin/python")
    if docker_default.exists():
        return str(docker_default)

    aider_bin = shutil.which("aider")
    if not aider_bin:
        return None

    resolved = Path(aider_bin).resolve()
    candidate = resolved.parent / "python"
    if candidate.exists():
        return str(candidate)

    return None


def verify_installs() -> None:
    log("Verifying installed packages and binaries")
    for tool in ("cutctx", "codex", "aider", "openclaw"):
        assert_true(shutil.which(tool) is not None, f"Expected '{tool}' on PATH")
    run(["cutctx", "--help"], timeout=30)
    run(["codex", "--version"], timeout=30)
    run(["openclaw", "--version"], timeout=30)
    aider_python = find_aider_python()
    assert_true(aider_python is not None, "Expected a discoverable Python runtime for aider")
    run(
        [aider_python, "-c", "import aider; print(getattr(aider, '__file__', 'missing'))"],
        timeout=60,
    )


def prepare_local_openclaw_plugin(base_env: dict[str, str], tmp_dir: Path) -> Path:
    log("Preparing local TypeScript package for OpenClaw plugin build")
    sdk_dir = SDK_DIR

    run(["npm", "install"], env=base_env, cwd=sdk_dir, timeout=600)
    run(["npm", "run", "build"], env=base_env, cwd=sdk_dir, timeout=600)
    pack_result = run(["npm", "pack"], env=base_env, cwd=sdk_dir, timeout=600)

    tarball_name = pack_result.stdout.strip().splitlines()[-1].strip()
    tarball_path = sdk_dir / tarball_name
    assert_true(tarball_path.exists(), "Expected npm pack to produce a local SDK tarball")

    # The SDK is intentionally packed from the checkout for this hermetic
    # smoke test. The public `cutctx-ai` package is not guaranteed to exist in
    # the registry used by CI, so point the temporary plugin copy at the
    # freshly packed local artifact instead of resolving the registry name.
    plugin_copy = tmp_dir / "openclaw-plugin"
    shutil.copytree(PLUGIN_DIR, plugin_copy)
    package_path = plugin_copy / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    dependencies = package.setdefault("dependencies", {})
    dependencies["cutctx-ai"] = f"file:{tarball_path}"
    package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    return plugin_copy


def verify_proxy_round_trip(base_env: dict[str, str], mock_server: MockOpenAIServer) -> None:
    proxy_port = PROXY_PORT
    proc = start_proxy(proxy_port, base_env)
    try:
        health = wait_for_http(f"http://127.0.0.1:{proxy_port}/health")
        assert_true(health.status_code == 200, "Proxy health check should return 200")

        models = httpx.get(
            f"http://127.0.0.1:{proxy_port}/v1/models",
            headers={"Authorization": "Bearer test-key"},
            timeout=10.0,
        )
        assert_true(models.status_code == 200, "Proxy should pass through /v1/models")
        assert_true(models.json()["data"][0]["id"] == "gpt-4o-mini", "Unexpected models payload")

        chat = httpx.post(
            f"http://127.0.0.1:{proxy_port}/v1/chat/completions",
            headers={"Authorization": "Bearer test-key"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Say hello."}],
            },
            timeout=10.0,
        )
        assert_true(chat.status_code == 200, "Proxy should pass through chat completions")
        assert_true(
            chat.json()["choices"][0]["message"]["content"] == "mock completion from upstream",
            "Unexpected chat completion payload",
        )
        assert_true(
            any(item["path"] == "/v1/models" for item in mock_server.requests),
            "Mock upstream should receive /v1/models",
        )
        assert_true(
            any(item["path"] == "/v1/chat/completions" for item in mock_server.requests),
            "Mock upstream should receive /v1/chat/completions",
        )
    finally:
        stop_process(proc)


def verify_codex_wrap(
    base_env: dict[str, str], project_dir: Path, log_dir: Path, mock_server: MockOpenAIServer
) -> None:
    port = CODEX_PORT
    run(
        ["cutctx", "wrap", "codex", "--port", str(port), "--", "--help"],
        env=base_env,
        cwd=project_dir,
        timeout=120,
    )
    project_agents = project_dir / "AGENTS.md"
    global_agents = Path(base_env["HOME"]) / ".codex" / "AGENTS.md"
    assert_true(project_agents.exists(), "Codex wrap should create project AGENTS.md")
    assert_true(global_agents.exists(), "Codex wrap should create ~/.codex/AGENTS.md")
    assert_true(RTK_MARKER in project_agents.read_text(encoding="utf-8"), "Missing RTK marker")
    assert_true(
        RTK_MARKER in global_agents.read_text(encoding="utf-8"), "Missing global RTK marker"
    )

    config_path = Path(base_env["HOME"]) / ".codex" / "config.toml"
    assert_true(config_path.exists(), "Codex wrap should create ~/.codex/config.toml")
    config = config_path.read_text(encoding="utf-8")
    assert_true(
        f'openai_base_url = "http://127.0.0.1:{port}/v1"' in config,
        "Codex wrap should inject openai_base_url for subscription routing",
    )
    assert_true(
        f'base_url = "http://127.0.0.1:{port}/v1"' in config,
        "Codex wrap should inject the cutctx provider base_url",
    )
    assert_true(
        'env_key = "OPENAI_API_KEY"' not in config,
        "Codex wrap should preserve OAuth and never inject env_key",
    )
    # Bug 3 (#406): requires_openai_auth must be absent from cutctx provider blocks.
    assert_true(
        "requires_openai_auth" not in config,
        "Codex wrap must NOT inject requires_openai_auth into the cutctx provider block",
    )
    assert_true(
        "supports_websockets = true" in config, "Codex wrap missing 'supports_websockets = true'"
    )

    entries = read_jsonl(log_dir / "codex.jsonl")
    assert_true(len(entries) > 0, "Codex shim should have been invoked")
    env_vars = entries[-1]["env"]
    assert_true(
        env_vars.get("OPENAI_BASE_URL") == f"http://127.0.0.1:{port}/v1",
        "Codex wrap should set OPENAI_BASE_URL",
    )
    assert_true(
        entries[-1]["probes"]
        == [
            {"url": f"http://127.0.0.1:{port}/v1/models", "status": 200},
            {"url": f"http://127.0.0.1:{port}/v1/chat/completions", "status": 200},
            {"url": f"http://127.0.0.1:{port}/stats", "status": 200},
        ],
        "Codex shim should prove OPENAI_BASE_URL points at a live proxy and that Cutctx logged the wrapped message",
    )
    assert_true(
        entries[-1].get("chat_completion") == "mock completion from upstream",
        "Codex wrap should receive the mock upstream completion through Cutctx",
    )
    assert_true(
        entries[-1].get("cutctx_model_count", 0) >= 1,
        "Codex wrap should appear in Cutctx request stats",
    )
    assert_true(
        any(
            item["path"] == "/v1/chat/completions"
            and isinstance(item.get("body"), dict)
            and item["body"].get("model") == "cutctx-wrap-e2e"
            for item in mock_server.requests
        ),
        "Codex wrap should forward the wrapped message upstream through Cutctx",
    )


def verify_claude_wrap(base_env: dict[str, str], project_dir: Path, log_dir: Path) -> None:
    port = PROXY_PORT + 10
    run(
        ["cutctx", "wrap", "claude", "--port", str(port), "--", "--help"],
        env=base_env,
        cwd=project_dir,
        timeout=120,
    )
    entries = read_jsonl(log_dir / "claude.jsonl")
    assert_true(len(entries) > 0, "Claude shim should have been invoked")
    env_vars = entries[-1]["env"]
    assert_true(
        env_vars.get("ANTHROPIC_BASE_URL") == f"http://127.0.0.1:{port}",
        "Claude wrap should set ANTHROPIC_BASE_URL",
    )
    assert_true(
        entries[-1]["probes"] == [{"url": f"http://127.0.0.1:{port}/health", "status": 200}],
        "Claude shim should prove ANTHROPIC_BASE_URL points at a live proxy",
    )


def verify_aider_wrap(base_env: dict[str, str], project_dir: Path, log_dir: Path) -> None:
    port = AIDER_PORT
    run(
        ["cutctx", "wrap", "aider", "--port", str(port), "--", "--help"],
        env=base_env,
        cwd=project_dir,
        timeout=120,
    )
    conventions = project_dir / "CONVENTIONS.md"
    assert_true(conventions.exists(), "Aider wrap should create CONVENTIONS.md")
    assert_true(
        RTK_MARKER in conventions.read_text(encoding="utf-8"),
        "Aider wrap should inject RTK instructions",
    )

    entries = read_jsonl(log_dir / "aider.jsonl")
    assert_true(len(entries) > 0, "Aider shim should have been invoked")
    env_vars = entries[-1]["env"]
    # Aider cannot send custom headers, so its wrap embeds the launch
    # directory as a /p/<name> base-URL prefix for per-project savings;
    # the proxy strips it before routing, so the probes still succeed.
    project_prefix = f"/p/{quote(project_dir.name, safe='')}"
    assert_true(
        env_vars.get("OPENAI_API_BASE") == f"http://127.0.0.1:{port}{project_prefix}/v1",
        "Aider wrap should set OPENAI_API_BASE",
    )
    assert_true(
        env_vars.get("ANTHROPIC_BASE_URL") == f"http://127.0.0.1:{port}{project_prefix}",
        "Aider wrap should set ANTHROPIC_BASE_URL",
    )
    assert_true(
        entries[-1]["probes"]
        == [
            {"url": f"http://127.0.0.1:{port}{project_prefix}/v1/models", "status": 200},
            {"url": f"http://127.0.0.1:{port}{project_prefix}/health", "status": 200},
        ],
        "Aider shim should prove both configured base URLs point at a live proxy",
    )


def verify_cursor_wrap(base_env: dict[str, str], project_dir: Path) -> None:
    port = CURSOR_PORT
    proc = subprocess.Popen(
        ["cutctx", "wrap", "cursor", "--port", str(port)],
        env=base_env,
        cwd=str(project_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        output = wait_for_output(proc, "Press Ctrl+C to stop the proxy.", timeout=30)
        # Cursor setup lines embed the /p/<name> per-project prefix.
        cursor_prefix = f"/p/{quote(project_dir.name, safe='')}"
        assert_true(
            f"http://127.0.0.1:{port}{cursor_prefix}/v1" in output,
            "Cursor wrap should print the OpenAI base URL override",
        )
        assert_true(
            f"http://127.0.0.1:{port}" in output,
            "Cursor wrap should print the Anthropic base URL override",
        )
        wait_for_http(f"http://127.0.0.1:{port}/health", timeout=15)
        cursorrules = project_dir / ".cursorrules"
        assert_true(cursorrules.exists(), "Cursor wrap should create .cursorrules")
        assert_true(
            RTK_MARKER in cursorrules.read_text(encoding="utf-8"),
            "Cursor wrap should inject RTK instructions",
        )
    finally:
        stop_process(proc)


def verify_cline_wrap(base_env: dict[str, str], project_dir: Path) -> None:
    """Smoke test: `wrap cline --prepare-only` writes RTK guidance to .clinerules."""
    run(
        ["cutctx", "wrap", "cline", "--prepare-only", "--port", str(CLINE_PORT)],
        env=base_env,
        cwd=project_dir,
        timeout=60,
    )
    clinerules = project_dir / ".clinerules"
    assert_true(clinerules.exists(), "Cline wrap should create .clinerules")
    assert_true(
        RTK_MARKER in clinerules.read_text(encoding="utf-8"),
        "Cline wrap should inject RTK instructions",
    )


def verify_continue_wrap(base_env: dict[str, str], project_dir: Path) -> None:
    """Smoke test: `wrap continue --prepare-only` injects RTK into .continue/config.json."""
    run(
        ["cutctx", "wrap", "continue", "--prepare-only", "--port", str(CONTINUE_PORT)],
        env=base_env,
        cwd=project_dir,
        timeout=60,
    )
    config_file = project_dir / ".continue" / "config.json"
    assert_true(
        config_file.exists(),
        "Continue wrap should create .continue/config.json",
    )
    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert_true(
        RTK_MARKER in data.get("systemMessage", ""),
        "Continue wrap should inject RTK instructions into systemMessage",
    )


def verify_goose_wrap(base_env: dict[str, str], project_dir: Path) -> None:
    """Smoke test: `wrap goose --prepare-only` writes RTK guidance to .goosehints."""
    run(
        ["cutctx", "wrap", "goose", "--prepare-only", "--port", str(GOOSE_PORT)],
        env=base_env,
        cwd=project_dir,
        timeout=60,
    )
    goosehints = project_dir / ".goosehints"
    assert_true(goosehints.exists(), "Goose wrap should create .goosehints")
    assert_true(
        RTK_MARKER in goosehints.read_text(encoding="utf-8"),
        "Goose wrap should inject RTK instructions",
    )


def verify_openhands_wrap(base_env: dict[str, str], project_dir: Path) -> None:
    """Smoke test: `wrap openhands --prepare-only` exits clean after setup."""
    run(
        ["cutctx", "wrap", "openhands", "--prepare-only", "--port", str(OPENHANDS_PORT)],
        env=base_env,
        cwd=project_dir,
        timeout=60,
    )


def verify_windsurf_wrap(base_env: dict[str, str], project_dir: Path) -> None:
    """Smoke test: `wrap windsurf --prepare-only` writes RTK guidance to .windsurfrules."""
    run(
        ["cutctx", "wrap", "windsurf", "--prepare-only", "--port", str(WINDSURF_PORT)],
        env=base_env,
        cwd=project_dir,
        timeout=60,
    )
    windsurfrules = project_dir / ".windsurfrules"
    assert_true(
        windsurfrules.exists(),
        "Windsurf wrap should create .windsurfrules",
    )
    assert_true(
        RTK_MARKER in windsurfrules.read_text(encoding="utf-8"),
        "Windsurf wrap should inject RTK instructions",
    )


def verify_zed_wrap(base_env: dict[str, str], project_dir: Path) -> None:
    """Smoke test: `wrap zed --prepare-only` exits clean without proxy startup."""
    run(
        ["cutctx", "wrap", "zed", "--prepare-only", "--port", str(ZED_PORT)],
        env=base_env,
        cwd=project_dir,
        timeout=60,
    )


def verify_opencode_wrap(base_env: dict[str, str], project_dir: Path) -> None:
    """Smoke test: `wrap opencode -- --help` launches through Cutctx and injects AGENTS.md."""
    if shutil.which("opencode", path=base_env.get("PATH")) is None:
        log("Skipping opencode wrap smoke: opencode CLI is not installed in this image.")
        return
    run(
        ["cutctx", "wrap", "opencode", "--port", str(OPENCODE_PORT), "--", "--help"],
        env=base_env,
        cwd=project_dir,
        timeout=120,
    )
    agents_md = project_dir / "AGENTS.md"
    assert_true(agents_md.exists(), "opencode wrap should create AGENTS.md")
    assert_true(
        RTK_MARKER in agents_md.read_text(encoding="utf-8"),
        "opencode wrap should inject RTK instructions",
    )


def verify_openclaw_wrap(
    base_env: dict[str, str],
    project_dir: Path,
    plugin_dir: Path,
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    openclaw_env = base_env.copy()
    openclaw_env.pop("CUTCTX_ADMIN_API_KEY", None)
    run(
        [
            "cutctx",
            "wrap",
            "openclaw",
            "--plugin-path",
            str(plugin_dir),
            "--copy",
            "--proxy-port",
            str(port),
            "--startup-timeout-ms",
            "30000",
            "--verbose",
        ],
        env=openclaw_env,
        cwd=project_dir,
        timeout=600,
    )
    dist_index = plugin_dir / "dist" / "index.js"
    assert_true(
        dist_index.exists(),
        "OpenClaw plugin build should produce dist/index.js",
    )

    config_file = run(
        ["openclaw", "config", "file"],
        env=openclaw_env,
        cwd=project_dir,
        timeout=60,
    )
    config_path_str = config_file.stdout.strip().splitlines()[-1].strip()
    if config_path_str.startswith("~/"):
        config_path = Path(base_env["HOME"]) / config_path_str[2:]
    else:
        config_path = Path(config_path_str)
    assert_true(config_path.exists(), "OpenClaw should create config file")

    state = json.loads(config_path.read_text(encoding="utf-8"))
    if state.get("gateway", {}).get("mode") != "local":
        run(
            [
                "openclaw",
                "config",
                "set",
                "gateway.mode",
                json.dumps("local"),
                "--strict-json",
            ],
            env=openclaw_env,
            cwd=project_dir,
            timeout=60,
        )
        state = json.loads(config_path.read_text(encoding="utf-8"))

    entry = state["plugins"]["entries"]["cutctx"]
    assert_true(entry["enabled"] is True, "OpenClaw wrap should enable plugin")
    assert_true(
        entry["config"]["proxyPort"] == port,
        "OpenClaw wrap should set proxy port",
    )
    assert_true(
        entry["config"].get("autoStart", True) is True,
        "OpenClaw wrap should leave autoStart enabled",
    )
    assert_true(
        state["gateway"]["mode"] == "local",
        "OpenClaw e2e bootstrap should set gateway.mode=local",
    )
    assert_true(
        state["plugins"]["slots"]["contextEngine"] == "cutctx",
        "OpenClaw wrap should set context engine slot",
    )

    run(
        ["cutctx", "unwrap", "openclaw", "--proxy-port", str(port)],
        env=openclaw_env,
        cwd=project_dir,
        timeout=120,
    )
    state = json.loads(config_path.read_text(encoding="utf-8"))
    assert_true(
        state["plugins"]["slots"]["contextEngine"] == "legacy",
        "OpenClaw unwrap should restore context engine slot",
    )


def main() -> None:
    verify_installs()
    with tempfile.TemporaryDirectory(
        prefix="cutctx-wrap-e2e-",
        ignore_cleanup_errors=True,
    ) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        home_dir = tmp_dir / "home"
        project_dir = tmp_dir / "project"
        shim_dir = tmp_dir / "shim-bin"
        log_dir = tmp_dir / "logs"

        for path_item in (home_dir, project_dir, shim_dir, log_dir):
            path_item.mkdir(parents=True, exist_ok=True)

        create_shims(shim_dir)
        mock_server, mock_thread = start_mock_server(19001)

        base_env = os.environ.copy()
        for key in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "ANTHROPIC_BASE_URL"):
            base_env.pop(key, None)
        base_env.update(
            {
                "HOME": str(home_dir),
                "PATH": f"{shim_dir}{os.pathsep}{base_env['PATH']}",
                "CUTCTX_E2E_LOG_DIR": str(log_dir),
                "CUTCTX_ADMIN_API_KEY": "test-key",
                "OPENAI_TARGET_API_URL": "http://127.0.0.1:19001/v1",
            }
        )

        try:
            verify_proxy_round_trip(base_env, mock_server)
            verify_claude_wrap(base_env, project_dir, log_dir)
            verify_codex_wrap(base_env, project_dir, log_dir, mock_server)
            verify_aider_wrap(base_env, project_dir, log_dir)
            verify_cursor_wrap(base_env, project_dir)
            verify_cline_wrap(base_env, project_dir)
            verify_continue_wrap(base_env, project_dir)
            verify_goose_wrap(base_env, project_dir)
            verify_openhands_wrap(base_env, project_dir)
            verify_windsurf_wrap(base_env, project_dir)
            verify_zed_wrap(base_env, project_dir)
            verify_opencode_wrap(base_env, project_dir)
            local_plugin_dir = prepare_local_openclaw_plugin(base_env, tmp_dir)
            verify_openclaw_wrap(base_env, project_dir, local_plugin_dir)
        finally:
            mock_server.shutdown()
            mock_thread.join(timeout=5)

    log("All wrap e2e checks passed.")


if __name__ == "__main__":
    main()

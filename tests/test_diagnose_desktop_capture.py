from __future__ import annotations

import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "diagnose_desktop_capture.sh"


class _DiagnosticHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return
        if self.path == "/stats":
            if self.headers.get("x-cutctx-admin-key") != "test-admin-key":
                self.send_response(401)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"detail":{"message":"Invalid or missing admin credentials."}}')
                return
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            stats_body = getattr(self.server, "stats_body", None)
            if stats_body is not None:
                self.wfile.write(stats_body)
                return
            log_requests = getattr(self.server, "include_log_requests", True)
            prefix = b'{"log_requests":true,' if log_requests else b"{"
            self.wfile.write(
                prefix + b'"recent_requests":'
                b'[{"timestamp":"now","provider":"anthropic","model":"claude"}]}'
            )
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _run_diagnostic(
    monkeypatch,
    tmp_path: Path,
    *,
    admin_key: str | None,
    fake_cutctx: bool = False,
    include_log_requests: bool = True,
    stats_body: bytes | None = None,
) -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DiagnosticHandler)
    server.include_log_requests = include_log_requests  # type: ignore[attr-defined]
    server.stats_body = stats_body  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        launchctl = fake_bin / "launchctl"
        launchctl.write_text("#!/bin/sh\nexit 0\n")
        launchctl.chmod(0o755)
        if fake_cutctx:
            cutctx = fake_bin / "cutctx"
            cutctx.write_text(
                "#!/bin/sh\n"
                'if [ "${CUTCTX_EXPERIMENTAL:-}" = 1 ]; then\n'
                "  echo 'intercept status available'\n"
                "  exit 0\n"
                "fi\n"
                "echo 'experimental gate missing'\n"
                "exit 1\n"
            )
            cutctx.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}:{env['PATH']}"
        env["CUTCTX_PROXY_PORT"] = str(server.server_port)
        env.pop("ANTHROPIC_API_KEY", None)
        if admin_key is None:
            env.pop("CUTCTX_ADMIN_API_KEY", None)
        else:
            env["CUTCTX_ADMIN_API_KEY"] = admin_key

        completed = subprocess.run(
            ["bash", str(SCRIPT)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        return completed.stdout
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_diagnostic_explains_stats_auth_failure(monkeypatch, tmp_path: Path) -> None:
    output = _run_diagnostic(monkeypatch, tmp_path, admin_key=None)

    assert "/stats returned HTTP 401" in output
    assert "CUTCTX_ADMIN_API_KEY" in output


def test_diagnostic_uses_admin_key_for_stats(monkeypatch, tmp_path: Path) -> None:
    output = _run_diagnostic(monkeypatch, tmp_path, admin_key="test-admin-key")

    assert "/stats shows 1 recent request(s)." in output


def test_diagnostic_distinguishes_missing_log_field_from_unavailable_stats(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output = _run_diagnostic(
        monkeypatch,
        tmp_path,
        admin_key="test-admin-key",
        include_log_requests=False,
    )

    assert "/stats does not expose log_requests in this build" in output
    assert "because /stats was unavailable" not in output


@pytest.mark.parametrize(
    "stats_body",
    [b"{", b'{"log_requests":true}', b'{"recent_requests":{}}'],
)
def test_diagnostic_rejects_invalid_stats_payloads(
    monkeypatch,
    tmp_path: Path,
    stats_body: bytes,
) -> None:
    output = _run_diagnostic(
        monkeypatch,
        tmp_path,
        admin_key="test-admin-key",
        stats_body=stats_body,
    )

    assert "/stats response is not valid stats JSON" in output
    assert "/stats shows" not in output
    assert "request history is reachable" not in output


def test_diagnostic_enables_read_only_intercept_status(monkeypatch, tmp_path: Path) -> None:
    output = _run_diagnostic(
        monkeypatch,
        tmp_path,
        admin_key="test-admin-key",
        fake_cutctx=True,
    )

    assert "intercept status available" in output
    assert "experimental gate missing" not in output

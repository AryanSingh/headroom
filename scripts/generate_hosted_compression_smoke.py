from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from typing import Any

from cutctx.hosted import HostedCompressionClient


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, *, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise TimeoutError(f"hosted smoke server on port {port} did not become ready")


def _compressible_text(rows: int = 120) -> str:
    return json.dumps(
        [
            {
                "id": i,
                "status": "error" if i % 11 == 0 else "ok",
                "message": f"repeated hosted smoke payload {i % 4}",
                "component": "hosted-smoke",
            }
            for i in range(rows)
        ],
        indent=2,
    )


def _hosted_server_python() -> str:
    """Prefer the project runtime so the spawned server matches the test deps."""
    active_venv = os.environ.get("VIRTUAL_ENV")
    candidates = [
        Path(active_venv) / "bin" / "python" if active_venv else None,
        Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable


def _launch_hosted_server(port: int, workspace_dir: Path) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["CUTCTX_WORKSPACE_DIR"] = str(workspace_dir)

    bootstrap = """
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app
import uvicorn
import sys

port = int(sys.argv[1])
app = create_app(
    ProxyConfig(
        hosted_compression_enabled=True,
        hosted_compression_api_key="hosted-smoke-key",
        cache_enabled=False,
        rate_limit_enabled=False,
        log_requests=True,
        disable_kompress=True,
    )
)
uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")
""".strip()

    return subprocess.Popen(
        [_hosted_server_python(), "-c", bootstrap, str(port)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def generate_hosted_compression_smoke(
    *,
    workspace_dir: Path,
    markdown_output: Path,
    json_output: Path,
) -> dict[str, Any]:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "logs").mkdir(parents=True, exist_ok=True)

    previous_workspace = os.environ.get("CUTCTX_WORKSPACE_DIR")
    os.environ["CUTCTX_WORKSPACE_DIR"] = str(workspace_dir)

    process: subprocess.Popen[str] | None = None
    try:
        port = _find_free_port()
        process = _launch_hosted_server(port, workspace_dir)
        try:
            _wait_for_port(port)
        except TimeoutError as exc:
            stderr = ""
            if process.poll() is not None and process.stderr is not None:
                stderr = process.stderr.read().strip()
            detail = f"{exc}"
            if stderr:
                detail = f"{detail}: {stderr}"
            raise TimeoutError(detail) from exc

        client = HostedCompressionClient(
            f"http://127.0.0.1:{port}",
            api_key="hosted-smoke-key",
            timeout=30.0,
        )
        result = client.compress_text(
            _compressible_text(),
            model="gpt-4o",
            compatibility_mode="tool_output",
            min_tokens_to_compress=10,
            protect_recent=0,
        )

        payload: dict[str, Any] = {
            "base_url": f"http://127.0.0.1:{port}",
            "model": result.model,
            "input_kind": result.input_kind,
            "compatibility_mode": result.compatibility_mode,
            "tokens_before": result.tokens_before,
            "tokens_after": result.tokens_after,
            "tokens_saved": result.tokens_saved,
            "compression_ratio": result.compression_ratio,
            "transforms_applied": result.transforms_applied,
            "message_count": len(result.messages),
        }

        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(
            "\n".join(
                [
                    "# Hosted Compression Smoke",
                    "",
                    f"- Base URL: `{payload['base_url']}`",
                    f"- Model: `{payload['model']}`",
                    f"- Input kind: `{payload['input_kind']}`",
                    f"- Compatibility mode: `{payload['compatibility_mode']}`",
                    f"- Tokens before: {payload['tokens_before']:,}",
                    f"- Tokens after: {payload['tokens_after']:,}",
                    f"- Tokens saved: {payload['tokens_saved']:,}",
                    f"- Compression ratio: {payload['compression_ratio']:.4f}",
                    (
                        "- Transforms applied: "
                        + (
                            ", ".join(payload["transforms_applied"])
                            if payload["transforms_applied"]
                            else "none"
                        )
                    ),
                    f"- Message count: {payload['message_count']}",
                    "",
                    "Generated via `HostedCompressionClient` against a live localhost `uvicorn` server.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        return payload
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        if previous_workspace is None:
            os.environ.pop("CUTCTX_WORKSPACE_DIR", None)
        else:
            os.environ["CUTCTX_WORKSPACE_DIR"] = previous_workspace


def main() -> None:
    payload = generate_hosted_compression_smoke(
        workspace_dir=Path("artifacts/hosted-smoke-workspace"),
        markdown_output=Path("artifacts/hosted-compression-smoke.md"),
        json_output=Path("artifacts/hosted-compression-smoke.json"),
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

"""End-to-end verification that Cursor-configured BYOK traffic is proxied."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from cutctx.providers.cursor.config import apply_proxy_config  # noqa: E402
from cutctx.proxy.models import ProxyConfig  # noqa: E402
from cutctx.proxy.server import create_app  # noqa: E402


class _UpstreamHandler(BaseHTTPRequestHandler):
    calls: list[tuple[str, dict[str, str]]] = []

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        self.__class__.calls.append((self.path, dict(self.headers.items())))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": "ok"}, "index": 0}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }
        self.wfile.write(json.dumps(payload).encode("utf-8"))
        if body:
            del body


@pytest.fixture
def upstream_server() -> str:
    _UpstreamHandler.calls = []
    server = HTTPServer(("127.0.0.1", 0), _UpstreamHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}/v1"
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.fixture
def upstream_base(upstream_server: str) -> str:
    return upstream_server.removesuffix("/v1")


def test_cursor_byok_request_hits_proxy_with_client_and_project_tags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    upstream_server: str,
) -> None:
    """Cursor IDE BYOK should POST to the generated /p/<project>/v1 URL and be tagged."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(tmp_path / "savings.json"))
    monkeypatch.setenv("OPENAI_TARGET_API_URL", upstream_server)

    apply_proxy_config(port=8787, project="cursor-demo")
    config_payload = json.loads((tmp_path / ".cursor" / "config.json").read_text(encoding="utf-8"))
    openai_base = config_payload["openai"]["baseUrl"]
    assert openai_base.endswith("/p/cursor-demo/v1")

    proxy_config = ProxyConfig(
        cache_enabled=False,
        rate_limit_enabled=False,
        log_requests=True,
        optimize=False,
        openai_api_url=upstream_server,
    )

    with TestClient(create_app(proxy_config), base_url="http://127.0.0.1:8787") as client:
        response = client.post(
            "/p/cursor-demo/v1/chat/completions",
            headers={
                "User-Agent": "cursor/1.2.3",
                "Authorization": "Bearer sk-test",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
        assert response.status_code == 200, response.text

        stats = client.get("/stats").json()
        recent = stats.get("recent_requests") or []
        assert recent, "expected proxied request in /stats recent_requests"
        latest = recent[-1]
        tags = latest.get("tags") or {}
        assert tags.get("client") == "cursor"
        assert tags.get("project") == "cursor-demo"

    assert _UpstreamHandler.calls, "proxy should have forwarded to upstream"
    assert _UpstreamHandler.calls[-1][0].endswith("/chat/completions")


def test_cursor_ide_anthropic_byok_request_hits_proxy_with_project_tags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    upstream_server: str,
    upstream_base: str,
) -> None:
    """Cursor IDE Anthropic BYOK should POST to /p/<project>/v1/messages and be tagged."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(tmp_path / "savings.json"))
    monkeypatch.setenv("ANTHROPIC_TARGET_API_URL", upstream_base)

    apply_proxy_config(port=8787, project="cursor-ide-demo")
    config_payload = json.loads((tmp_path / ".cursor" / "config.json").read_text(encoding="utf-8"))
    anthropic_base = config_payload["anthropic"]["baseUrl"]
    assert anthropic_base.endswith("/p/cursor-ide-demo")

    proxy_config = ProxyConfig(
        cache_enabled=False,
        rate_limit_enabled=False,
        log_requests=True,
        optimize=False,
        anthropic_api_url=upstream_base,
    )

    with TestClient(create_app(proxy_config), base_url="http://127.0.0.1:8787") as client:
        response = client.post(
            "/p/cursor-ide-demo/v1/messages",
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
        )
        assert response.status_code == 200, response.text

        stats = client.get("/stats").json()
        recent = stats.get("recent_requests") or []
        assert recent, "expected proxied request in /stats recent_requests"
        latest = recent[-1]
        tags = latest.get("tags") or {}
        assert tags.get("client") == "cursor"
        assert tags.get("project") == "cursor-ide-demo"

    assert _UpstreamHandler.calls, "proxy should have forwarded to upstream"
    assert _UpstreamHandler.calls[-1][0].endswith("/v1/messages")


class _ModelCaptureHandler(BaseHTTPRequestHandler):
    model: str | None = None

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        payload = json.loads(body.decode("utf-8"))
        self.__class__.model = payload.get("model")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "choices": [{"message": {"role": "assistant", "content": "ok"}, "index": 0}],
                }
            ).encode("utf-8")
        )
        if body:
            del body


def test_openai_chat_strips_cutctx_model_prefix_for_cursor_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cursor IDE cutctx-* models should reach upstream with the real slug."""
    _ModelCaptureHandler.model = None
    server = HTTPServer(("127.0.0.1", 0), _ModelCaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        openai_upstream = f"http://{host}:{port}/v1"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(tmp_path / "savings.json"))
        monkeypatch.setenv("OPENAI_TARGET_API_URL", openai_upstream)

        proxy_config = ProxyConfig(
            cache_enabled=False,
            rate_limit_enabled=False,
            log_requests=True,
            optimize=False,
            openai_api_url=openai_upstream,
        )
        with TestClient(create_app(proxy_config), base_url="http://127.0.0.1:8787") as client:
            response = client.post(
                "/p/cursor-prefix/v1/chat/completions",
                headers={
                    "User-Agent": "cursor/1.2.3",
                    "Authorization": "Bearer sk-test",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "cutctx-gpt-4o",
                    "messages": [{"role": "user", "content": "ping"}],
                },
            )
            assert response.status_code == 200, response.text
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert _ModelCaptureHandler.model == "gpt-4o"

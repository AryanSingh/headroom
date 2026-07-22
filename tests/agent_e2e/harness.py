"""Real-network hermetic replay harness for Codex and Claude fixtures."""

from __future__ import annotations

import base64
import json
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import uvicorn
import zstandard
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, StreamingResponse
from websockets.sync.client import connect as ws_connect

from cutctx.capture.agent_fixture import validate_scenario
from cutctx.proxy.handlers.openai.responses import _set_test_chatgpt_responses_endpoints
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


class ThreadedUvicorn:
    def __init__(self, app: FastAPI, *, port: int | None = None) -> None:
        self.app = app
        self.port = port or _unused_port()
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        config = uvicorn.Config(
            self.app,
            host="127.0.0.1",
            port=self.port,
            log_level="error",
            access_log=False,
            lifespan="on",
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.server.started:
                return
            if not self.thread.is_alive():
                break
            time.sleep(0.01)
        raise RuntimeError(f"server failed to start on {self.url}")

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.thread is not None:
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                raise RuntimeError(f"server failed to stop on {self.url}")
        self.server = None
        self.thread = None


def _sse(events: list[dict[str, Any]]) -> Iterator[bytes]:
    for event in events:
        event_type = str(event.get("type") or "message")
        yield f"event: {event_type}\ndata: {json.dumps(event, separators=(',', ':'))}\n\n".encode()


@dataclass
class ScriptedUpstream:
    app: FastAPI = field(default_factory=FastAPI)
    scripts: list[dict[str, Any]] = field(default_factory=list)
    requests: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.app.add_api_route(
            "/backend-api/codex/responses",
            self._codex_subscription,
            methods=["POST"],
        )
        self.app.add_api_route("/v1/responses", self._codex_api, methods=["POST"])
        self.app.add_api_route("/v1/messages", self._claude, methods=["POST"])
        self.app.add_api_websocket_route(
            "/backend-api/codex/responses",
            self._codex_websocket,
        )

    async def _capture(self, request: Request) -> dict[str, Any]:
        body = await request.json()
        headers = {key.lower(): value for key, value in request.headers.items()}
        self.requests.append({"path": request.url.path, "headers": headers, "body": body})
        return body

    def _next_script(self) -> dict[str, Any]:
        if not self.scripts:
            raise RuntimeError("strict upstream received an unscripted request")
        return self.scripts.pop(0)

    async def _codex_subscription(self, request: Request):
        body = await self._capture(request)
        if body.get("store") is not False:
            return JSONResponse({"detail": "Store must be set to false"}, status_code=400)
        if body.get("stream") is not True:
            return JSONResponse({"detail": "Stream must be set to true"}, status_code=400)
        for field_name in ("model", "input"):
            if field_name not in body:
                return JSONResponse(
                    {"detail": f"Missing required field: {field_name}"}, status_code=400
                )
        script = self._next_script()
        return StreamingResponse(
            _sse(script["events"]),
            status_code=int(script.get("status", 200)),
            headers=script.get("headers", {}),
            media_type="text/event-stream",
        )

    async def _codex_api(self, request: Request):
        body = await self._capture(request)
        for field_name in ("model", "input"):
            if field_name not in body:
                return JSONResponse(
                    {"error": {"message": f"Missing {field_name}"}}, status_code=400
                )
        script = self._next_script()
        if "json" in script:
            return JSONResponse(
                script["json"],
                status_code=int(script.get("status", 200)),
                headers=script.get("headers", {}),
            )
        return StreamingResponse(
            _sse(script["events"]),
            status_code=int(script.get("status", 200)),
            headers=script.get("headers", {}),
            media_type="text/event-stream",
        )

    async def _claude(self, request: Request):
        body = await self._capture(request)
        headers = self.requests[-1]["headers"]
        for header in ("anthropic-version",):
            if not headers.get(header):
                return JSONResponse(
                    {"type": "error", "error": {"type": "invalid_request_error"}},
                    status_code=400,
                )
        for field_name in ("model", "messages", "max_tokens"):
            if field_name not in body:
                return JSONResponse(
                    {"type": "error", "error": {"type": "invalid_request_error"}},
                    status_code=400,
                )
        script = self._next_script()
        return StreamingResponse(
            _sse(script["events"]),
            status_code=int(script.get("status", 200)),
            headers=script.get("headers", {}),
            media_type="text/event-stream",
        )

    async def _codex_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        while self.scripts:
            frame = await websocket.receive_json()
            body = frame.get("response", frame) if isinstance(frame, dict) else {}
            headers = {key.lower(): value for key, value in websocket.headers.items()}
            self.requests.append(
                {
                    "path": websocket.url.path,
                    "headers": headers,
                    "body": body,
                    "transport": "websocket",
                }
            )
            if body.get("store") is not False or body.get("stream") is not True:
                await websocket.send_json(
                    {"type": "error", "error": {"type": "invalid_request_error"}}
                )
                await websocket.close(code=1008)
                return
            script = self._next_script()
            for event in script["events"]:
                await websocket.send_json(event)
        await websocket.close(code=1000)


def _jwt(account_id: str) -> str:
    def encode(value: dict[str, Any]) -> str:
        return (
            base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode())
            .decode()
            .rstrip("=")
        )

    return (
        f"{encode({'alg': 'none', 'typ': 'JWT'})}."
        f"{encode({'https://api.openai.com/auth': {'chatgpt_account_id': account_id}})}."
    )


def _materialize_headers(fixture: dict[str, Any]) -> dict[str, str]:
    headers = {key: str(value) for key, value in fixture.items() if key != "authorization_kind"}
    kind = fixture.get("authorization_kind")
    if kind == "chatgpt-oauth-jwt":
        account_id = headers.get("ChatGPT-Account-ID", "acct_fixture")
        headers["authorization"] = f"Bearer {_jwt(account_id)}"
    elif kind == "anthropic-api-key":
        headers["x-api-key"] = "sk-ant-hermetic-placeholder"
    elif kind == "openai-api-key":
        headers["authorization"] = "Bearer sk-hermetic-placeholder"
    return headers


def _terminal_event(response: httpx.Response, expected: str) -> str:
    if response.headers.get("content-type", "").startswith("application/json"):
        payload = response.json()
        if expected == "response.completed" and payload.get("status") == "completed":
            return expected
    seen: list[str] = []
    for line in response.text.splitlines():
        if line.startswith("data: "):
            event = json.loads(line[6:])
            if isinstance(event, dict) and isinstance(event.get("type"), str):
                seen.append(event["type"])
    if expected not in seen:
        raise AssertionError(
            f"expected terminal event {expected!r}; status={response.status_code}; events={seen}"
        )
    return expected


@dataclass
class ReplayResult:
    proxy_restarts: int = 0
    upstream_requests: list[dict[str, Any]] = field(default_factory=list)
    terminal_events: list[str] = field(default_factory=list)


class ReplayHarness:
    def __init__(self, fixture_root: str | Path, *, optimize: bool = False) -> None:
        self.fixture_root = Path(fixture_root)
        self.optimize = optimize
        self.upstream = ScriptedUpstream()
        self.upstream_server = ThreadedUvicorn(self.upstream.app)
        self.proxy_port = _unused_port()
        self.proxy_server: ThreadedUvicorn | None = None

    def __enter__(self) -> ReplayHarness:
        self.upstream_server.start()
        return self

    def __exit__(self, *_: object) -> None:
        if self.proxy_server is not None:
            self.proxy_server.stop()
        _set_test_chatgpt_responses_endpoints(http_url=None, ws_url=None)
        self.upstream_server.stop()

    def _start_proxy(self) -> None:
        config = ProxyConfig(
            host="127.0.0.1",
            port=self.proxy_port,
            optimize=self.optimize,
            image_optimize=False,
            audio_optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            subscription_tracking_enabled=False,
            anthropic_api_url=self.upstream_server.url,
            openai_api_url=self.upstream_server.url,
        )
        self.proxy_server = ThreadedUvicorn(create_app(config), port=self.proxy_port)
        self.proxy_server.start()

    def _restart_proxy(self) -> None:
        assert self.proxy_server is not None
        self.proxy_server.stop()
        self._start_proxy()

    def run(self, scenario_id: str) -> ReplayResult:
        scenario_dir = self.fixture_root / scenario_id
        scenario = json.loads((scenario_dir / "scenario.json").read_text(encoding="utf-8"))
        validate_scenario(scenario)
        _set_test_chatgpt_responses_endpoints(
            http_url=f"{self.upstream_server.url}/backend-api/codex/responses",
            ws_url=f"ws://127.0.0.1:{self.upstream_server.port}/backend-api/codex/responses",
        )
        self._start_proxy()
        result = ReplayResult()
        terminal = scenario["assertions"].get("terminal_event")
        for step in scenario["steps"]:
            action = step["action"]
            if action == "restart_proxy":
                self._restart_proxy()
                result.proxy_restarts += 1
                continue
            if action != "request":
                continue
            body_fixture_names = step.get("body_fixtures") or [step["body_fixture"]]
            bodies = [
                json.loads((scenario_dir / name).read_text(encoding="utf-8"))
                for name in body_fixture_names
            ]
            headers: dict[str, str] = {}
            if step.get("headers_fixture"):
                header_fixture = json.loads(
                    (scenario_dir / step["headers_fixture"]).read_text(encoding="utf-8")
                )
                headers = _materialize_headers(header_fixture)
            script_names = step.get("upstream_scripts") or [step["upstream_script"]]
            scripts = [
                json.loads((scenario_dir / name).read_text(encoding="utf-8"))
                for name in script_names
            ]
            self.upstream.scripts.extend(scripts)
            if step["transport"] == "websocket":
                ws_url = f"ws://127.0.0.1:{self.proxy_port}{step['path']}"
                seen: list[str] = []
                with ws_connect(
                    ws_url,
                    additional_headers=headers,
                    open_timeout=10,
                    close_timeout=5,
                ) as websocket:
                    for body in bodies:
                        websocket.send(json.dumps(body, separators=(",", ":")))
                        turn_events: list[str] = []
                        while terminal not in turn_events:
                            event = json.loads(websocket.recv(timeout=10))
                            if isinstance(event, dict) and isinstance(event.get("type"), str):
                                turn_events.append(event["type"])
                        seen.extend(turn_events)
                        result.terminal_events.append(terminal)
                continue
            body = bodies[0]
            with httpx.Client(base_url=self.proxy_server.url, timeout=15) as client:
                if step.get("content_encoding") == "zstd":
                    headers["content-encoding"] = "zstd"
                    encoded = json.dumps(body, separators=(",", ":")).encode()
                    content = zstandard.ZstdCompressor().compress(encoded)
                    response = client.request(
                        step.get("method", "POST"),
                        step["path"],
                        headers=headers,
                        content=content,
                    )
                else:
                    response = client.request(
                        step.get("method", "POST"),
                        step["path"],
                        headers=headers,
                        json=body,
                    )
            response.raise_for_status()
            if terminal:
                result.terminal_events.append(_terminal_event(response, terminal))
        result.upstream_requests = list(self.upstream.requests)
        return result

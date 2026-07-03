from __future__ import annotations

import cutctx.proxy.server as proxy_server_module
from cutctx.proxy.server import ProxyConfig


def test_run_server_uses_long_codex_websocket_keepalive(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_app(config: ProxyConfig) -> object:
        return object()

    def fake_uvicorn_run(app: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(proxy_server_module, "create_app", fake_create_app)
    monkeypatch.setattr(proxy_server_module.uvicorn, "run", fake_uvicorn_run)

    proxy_server_module.run_server(
        ProxyConfig(host="127.0.0.1", port=0),
        print_banner=False,
    )

    assert captured["ws_ping_interval"] == 600
    assert captured["ws_ping_timeout"] == 600

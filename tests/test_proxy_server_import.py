from __future__ import annotations

import importlib


def test_proxy_server_module_imports_cleanly() -> None:
    module = importlib.import_module("cutctx.proxy.server")

    assert hasattr(module, "create_app")
    assert hasattr(module, "ProxyConfig")

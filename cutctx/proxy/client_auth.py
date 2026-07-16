"""Authentication boundary for provider-facing proxy traffic."""

from __future__ import annotations

import hmac
from typing import Any
from urllib.parse import urlparse

from cutctx.proxy.deployment_security import effective_proxy_key
from cutctx.proxy.loopback_guard import is_loopback_host, is_loopback_host_header


class ProxyClientAuthError(PermissionError):
    """Raised when provider traffic lacks a trusted client identity."""


def _require_key(headers: Any, config: Any) -> None:
    expected = effective_proxy_key(config)
    if not expected:
        return
    supplied = str(headers.get("x-cutctx-proxy-key", ""))
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise ProxyClientAuthError(
            "Missing or invalid proxy client credential; pass X-Cutctx-Proxy-Key."
        )


def require_http_proxy_client(request: Any, config: Any) -> None:
    """Require the dedicated proxy key when one is configured."""

    _require_key(request.headers, config)


def require_websocket_proxy_client(websocket: Any, config: Any) -> None:
    """Authenticate a provider WebSocket and reject browser cross-origin use."""

    headers = websocket.headers
    origin = str(headers.get("origin", "")).strip()
    if origin:
        trusted = {
            value.rstrip("/")
            for value in (getattr(config, "cors_origins", None) or [])
            if value and value != "*"
        }
        normalized_origin = origin.rstrip("/")
        parsed_origin = urlparse(normalized_origin)
        local_same_origin = (
            parsed_origin.scheme in {"http", "https"}
            and is_loopback_host(parsed_origin.hostname)
            and is_loopback_host_header(headers.get("host"))
        )
        if normalized_origin not in trusted and not local_same_origin:
            raise ProxyClientAuthError("Untrusted WebSocket origin.")

    _require_key(headers, config)


__all__ = [
    "ProxyClientAuthError",
    "effective_proxy_key",
    "require_http_proxy_client",
    "require_websocket_proxy_client",
]

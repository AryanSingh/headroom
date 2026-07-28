"""Resolve a local seat token for header-incapable loopback clients.

Codex ChatGPT/desktop routes through the built-in ``openai`` provider via
``openai_base_url`` and cannot attach ``X-Cutctx-User-Token``. CutCtx Control
mints a token into ``~/.cutctx/control/seat.json`` (and may export
``CUTCTX_USER_TOKEN`` on the proxy process). The paid seat gate can then
accept that pre-provisioned token for trusted loopback traffic only.
"""

from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path

__all__ = [
    "control_seat_path",
    "is_trusted_local_seat_connection",
    "load_control_seat_token",
    "resolve_local_user_token",
]


def is_trusted_local_seat_connection(
    *,
    bind_host: str | None,
    host_header: str | None,
    client_host: str | None,
) -> bool:
    """Require loopback bind, Host header, and an explicit loopback peer.

    ``testclient`` is Starlette's exact in-process test sentinel. Every other
    non-IP or missing peer fails closed.
    """

    from cutctx.proxy.loopback_guard import is_loopback_host, is_loopback_host_header

    if not bind_host or not is_loopback_host(bind_host):
        return False
    if not is_loopback_host_header(host_header):
        return False
    if client_host == "testclient":
        return True
    if not client_host:
        return False
    try:
        address = ipaddress.ip_address(client_host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped.is_loopback
    return address.is_loopback


def control_seat_path(home: Path | None = None) -> Path:
    root = home if home is not None else Path.home()
    return root / ".cutctx" / "control" / "seat.json"


def load_control_seat_token(home: Path | None = None) -> str | None:
    """Return a ``ctu1…`` token from Control's seat file, if present."""
    path = control_seat_path(home)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    token = payload.get("token") if isinstance(payload, dict) else None
    if not isinstance(token, str):
        return None
    token = token.strip()
    if not token.startswith("ctu1."):
        return None
    return token


def resolve_local_user_token(*, home: Path | None = None) -> str | None:
    """Prefer ``CUTCTX_USER_TOKEN`` env, then Control ``seat.json``."""
    from_env = (os.environ.get("CUTCTX_USER_TOKEN") or "").strip()
    if from_env.startswith("ctu1."):
        return from_env
    return load_control_seat_token(home)

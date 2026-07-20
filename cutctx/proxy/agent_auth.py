"""Least-privilege authentication for SDK and MCP agent routes."""

from __future__ import annotations

import hmac
import logging
import os
from dataclasses import dataclass
from typing import Any, Literal

from cutctx.proxy.deployment_security import (
    effective_admin_key,
    is_loopback_host,
)

logger = logging.getLogger("cutctx.proxy.agent_auth")
_admin_compat_warning_emitted = False


class AgentClientAuthError(PermissionError):
    """Raised when an agent route lacks a valid client credential."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_or_expired_client_key",
    ) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AgentAuthIdentity:
    """Authenticated agent identity without secret material."""

    kind: Literal["client", "admin_compat", "loopback_open"]


def effective_client_key(config: Any) -> str | None:
    """Resolve the server-side verifier for agent operations."""

    return getattr(config, "client_api_key", None) or os.environ.get(
        "CUTCTX_CLIENT_API_KEY"
    )


def _bearer(headers: Any) -> str:
    auth_header = str(headers.get("authorization", ""))
    return auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""


def _matches_admin_compat(request: Any, config: Any) -> bool:
    expected = effective_admin_key(config)
    if not expected:
        return False
    supplied = (
        _bearer(request.headers)
        or str(request.headers.get("x-cutctx-admin-key", ""))
        or str(request.headers.get("x-headroom-admin-key", ""))
    )
    return bool(supplied and hmac.compare_digest(supplied, expected))


def _warn_admin_compat_once() -> None:
    global _admin_compat_warning_emitted
    if _admin_compat_warning_emitted:
        return
    _admin_compat_warning_emitted = True
    logger.warning(
        "deprecated_agent_admin_auth: an admin credential authenticated an "
        "agent route; configure CUTCTX_CLIENT_API_KEY and use CUTCTX_API_KEY "
        "from client processes"
    )


def require_agent_client(request: Any, config: Any) -> AgentAuthIdentity:
    """Authenticate compression and CCR operations without granting admin."""

    expected = effective_client_key(config)
    supplied = _bearer(request.headers) or str(
        request.headers.get("x-cutctx-api-key", "")
    )
    if expected and supplied and hmac.compare_digest(supplied, expected):
        return AgentAuthIdentity("client")

    if _matches_admin_compat(request, config):
        _warn_admin_compat_once()
        return AgentAuthIdentity("admin_compat")

    if not expected:
        if is_loopback_host(getattr(config, "host", None)):
            return AgentAuthIdentity("loopback_open")
        raise AgentClientAuthError(
            "Cutctx client authentication is required.",
            code="client_key_required",
        )

    raise AgentClientAuthError("Invalid or expired Cutctx client credential.")


__all__ = [
    "AgentAuthIdentity",
    "AgentClientAuthError",
    "effective_client_key",
    "require_agent_client",
]

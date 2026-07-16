"""Shared deployment-security validation for the proxy runtime and CLI."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


class DeploymentSecurityError(ValueError):
    """Raised when a network-facing proxy lacks required safeguards."""


@dataclass(frozen=True)
class DeploymentSecurityIssue:
    code: str
    message: str
    remediation: str


def is_loopback_host(host: str | None) -> bool:
    """Return whether ``host`` only exposes the process on the local machine."""
    normalized = (host or "").strip().strip("[]").lower()
    if normalized in {"localhost", "ip6-localhost"}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def has_configured_sso(config: Any) -> bool:
    """Return whether the proxy has enough identity configuration for admin auth.

    ``SsoConfig.from_proxy_config`` enables JWT validation from its concrete
    issuer/JWKS/audience fields. Treating a separate convenience boolean as a
    mandatory gate would leave those deployments' admin routes unauthenticated.
    """
    return bool(
        getattr(config, "sso_jwks_uri", None)
        and getattr(config, "sso_issuer", None)
        and getattr(config, "sso_audience", None)
    )


def effective_admin_key(config: Any) -> str | None:
    """Resolve the configured admin key without exposing it to diagnostics."""
    return getattr(config, "admin_api_key", None) or os.environ.get("CUTCTX_ADMIN_API_KEY")


def effective_proxy_key(config: Any) -> str | None:
    """Resolve the dedicated provider-route client key."""

    return getattr(config, "proxy_api_key", None) or os.environ.get("CUTCTX_PROXY_API_KEY")


def _is_private_literal_upstream(url: str | None) -> bool:
    """Return whether an upstream URL uses a non-public literal IP address."""
    if not url:
        return False
    try:
        host = urlparse(url).hostname
        if not host:
            return False
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def deployment_security_issues(config: Any) -> list[DeploymentSecurityIssue]:
    """Return launch-blocking issues for a network-facing proxy configuration."""
    if is_loopback_host(getattr(config, "host", None)):
        return []

    issues: list[DeploymentSecurityIssue] = []
    if not effective_admin_key(config) and not has_configured_sso(config):
        issues.append(
            DeploymentSecurityIssue(
                code="admin_auth_required",
                message="A non-loopback proxy requires admin authentication.",
                remediation=(
                    "Set CUTCTX_ADMIN_API_KEY or configure CUTCTX_SSO_ENABLED=1 with "
                    "CUTCTX_SSO_JWKS_URI, CUTCTX_SSO_ISSUER, and CUTCTX_SSO_AUDIENCE."
                ),
            )
        )

    if not effective_proxy_key(config):
        issues.append(
            DeploymentSecurityIssue(
                code="proxy_client_auth_required",
                message="A non-loopback proxy requires proxy client authentication.",
                remediation=(
                    "Set CUTCTX_PROXY_API_KEY and pass X-Cutctx-Proxy-Key on provider "
                    "HTTP and WebSocket requests. Do not reuse the admin or upstream key."
                ),
            )
        )

    cors_origins = getattr(config, "cors_origins", None) or []
    if "*" in cors_origins:
        issues.append(
            DeploymentSecurityIssue(
                code="wildcard_cors_forbidden",
                message="Wildcard CORS is not permitted for a non-loopback proxy.",
                remediation="Set CUTCTX_CORS_ORIGINS to the explicit trusted dashboard origins.",
            )
        )
    if os.environ.get("CUTCTX_ALLOW_PRIVATE_UPSTREAM", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        for field in (
            "anthropic_api_url",
            "openai_api_url",
            "gemini_api_url",
            "cloudcode_api_url",
            "vertex_api_url",
        ):
            if _is_private_literal_upstream(getattr(config, field, None)):
                issues.append(
                    DeploymentSecurityIssue(
                        code="private_upstream_forbidden",
                        message=f"{field} points to a private or loopback IP address.",
                        remediation=(
                            "Use a public provider endpoint, or set CUTCTX_ALLOW_PRIVATE_UPSTREAM=1 "
                            "only for an intentionally isolated private provider."
                        ),
                    )
                )
    return issues


def require_secure_deployment(config: Any) -> None:
    """Raise a concise launch error when network-facing safeguards are missing."""
    issues = deployment_security_issues(config)
    if not issues:
        return
    details = "; ".join(f"{issue.message} {issue.remediation}" for issue in issues)
    raise DeploymentSecurityError(details)

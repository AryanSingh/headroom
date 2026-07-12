"""Shared deployment-security validation for the proxy runtime and CLI."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from typing import Any


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
    """Return whether the proxy has enough identity configuration for admin auth."""
    return bool(
        getattr(config, "sso_enabled", False)
        and getattr(config, "sso_jwks_uri", None)
        and getattr(config, "sso_issuer", None)
        and getattr(config, "sso_audience", None)
    )


def effective_admin_key(config: Any) -> str | None:
    """Resolve the configured admin key without exposing it to diagnostics."""
    return getattr(config, "admin_api_key", None) or os.environ.get("CUTCTX_ADMIN_API_KEY")


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

    cors_origins = getattr(config, "cors_origins", None) or []
    if "*" in cors_origins:
        issues.append(
            DeploymentSecurityIssue(
                code="wildcard_cors_forbidden",
                message="Wildcard CORS is not permitted for a non-loopback proxy.",
                remediation="Set CUTCTX_CORS_ORIGINS to the explicit trusted dashboard origins.",
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

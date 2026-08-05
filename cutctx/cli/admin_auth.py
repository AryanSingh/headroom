"""Shared admin credential resolution for CLI HTTP clients."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from cutctx import paths


class CliApiError(RuntimeError):
    """An API error already translated into an operator-facing message."""


def _feature_label(feature: object) -> str:
    value = str(feature or "feature").replace("_", " ")
    return "RBAC" if value.lower() == "rbac" else value.capitalize()


def raise_for_cli_status(response: httpx.Response) -> None:
    """Preserve typed API denials instead of collapsing them to raw HTTP errors."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        try:
            payload = response.json()
        except (TypeError, ValueError):
            raise
        detail = payload.get("detail", payload) if isinstance(payload, dict) else None
        if isinstance(detail, dict) and detail.get("error") == "feature_not_available":
            required = str(detail.get("required_tier") or "a higher").capitalize()
            current = detail.get("current_tier")
            message = f"{_feature_label(detail.get('feature'))} requires the {required} tier"
            if current:
                message += f" (current tier: {str(current).capitalize()})"
            raise CliApiError(message) from error
        raise


def is_loopback_proxy(proxy_url: str) -> bool:
    """Return whether a proxy URL resolves to an explicit loopback hostname."""

    return (urlparse(proxy_url).hostname or "").lower() in {"127.0.0.1", "localhost", "::1"}


def resolve_admin_api_key(admin_key: str | None, proxy_url: str) -> str | None:
    """Resolve explicit/env credentials, then discover the local key on loopback."""

    key = (admin_key or os.environ.get("CUTCTX_ADMIN_API_KEY") or "").strip()
    if key:
        return key
    if not is_loopback_proxy(proxy_url):
        return None
    try:
        key = (paths.workspace_dir() / "admin_key.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return key or None


def admin_headers(
    admin_key: str | None,
    proxy_url: str,
    *,
    content_type_json: bool = True,
) -> dict[str, str]:
    """Build admin request headers without leaking local keys to remote URLs."""

    headers = {"Content-Type": "application/json"} if content_type_json else {}
    key = resolve_admin_api_key(admin_key, proxy_url)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers

"""Gemini install-time helpers."""

from __future__ import annotations

from .runtime import proxy_base_url


def build_install_env(*, port: int, backend: str) -> dict[str, str]:
    """Build the persistent install environment for Gemini CLI."""
    del backend
    base_url = proxy_base_url(port)
    return {
        "GOOGLE_GEMINI_BASE_URL": base_url,
        "GOOGLE_VERTEX_BASE_URL": base_url,
        "CODE_ASSIST_ENDPOINT": base_url,
    }

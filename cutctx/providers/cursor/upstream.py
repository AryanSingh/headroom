"""Cursor hosted API upstream helpers for subscription traffic."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from cutctx.proxy.auth_mode import classify_client

DEFAULT_CURSOR_API_URL = "https://api2.cursor.sh"
CURSOR_TARGET_API_URL_ENV = "CURSOR_TARGET_API_URL"
CURSOR_IDE_MODEL_PREFIX = "cutctx-"


def resolve_cursor_target_api_url(environ: Mapping[str, str] | None = None) -> str:
    """Return the upstream Cursor hosted API base URL."""
    env = environ or os.environ
    override = env.get(CURSOR_TARGET_API_URL_ENV, "").strip()
    return (override or DEFAULT_CURSOR_API_URL).rstrip("/")


def is_cursor_client(headers: Mapping[str, Any] | Any) -> bool:
    """Return True when the request originated from Cursor CLI or IDE."""
    return classify_client(headers) == "cursor"


def strip_cursor_ide_model_prefix(model: str) -> tuple[str, bool]:
    """Strip the IDE escape prefix so upstream sees the real model slug.

    Cursor hijacks known model names (``gpt-*``, ``claude-*``) to
    ``api2.cursor.sh``.     Prefixing a custom model with ``cutctx-`` forces the IDE to honor the
    BYOK base URL instead; we strip it before forwarding upstream.
    """
    if model.startswith(CURSOR_IDE_MODEL_PREFIX):
        return model[len(CURSOR_IDE_MODEL_PREFIX) :], True
    return model, False


__all__ = [
    "CURSOR_IDE_MODEL_PREFIX",
    "CURSOR_TARGET_API_URL_ENV",
    "DEFAULT_CURSOR_API_URL",
    "is_cursor_client",
    "resolve_cursor_target_api_url",
    "strip_cursor_ide_model_prefix",
]

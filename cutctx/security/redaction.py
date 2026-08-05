# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Shared credential redaction for anything the product writes to disk.

H6 (audit 2026-08-03): the admin API key was found in cleartext in
``~/.cutctx/logs/request_history.jsonl``. The header-name filter in
``cutctx/proxy/helpers.py:_should_redact_key`` closed the specific hole that
produced those rows, but it is *suffix-based on key names only* — a header
such as ``x-cutctx-credential`` or a credential embedded in a message body
still reaches the sink in cleartext.

This module is the defence-in-depth layer: it redacts by **value shape** and
by **key name**, and it can redact **known secret values** whose shape is not
guessable (the admin key is operator-chosen and has no fixed prefix, so shape
matching alone can never catch it).

Design notes
------------
* Pure functions, no I/O, no imports from ``cutctx.proxy`` — safe to call from
  any sink (JSONL writers, log handlers, crash dumps).
* ``redact_structure`` never mutates its input; it returns a new object.
* Redaction is deliberately conservative about *content*: it replaces the
  credential, not the surrounding text, so logs stay diagnosable.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "REDACTED",
    "redact_text",
    "redact_structure",
    "register_secret_value",
    "clear_registered_secrets",
    "is_secret_key_name",
]

REDACTED = "[REDACTED]"

# --- Value-shape matchers --------------------------------------------------
# The first three are promoted verbatim from
# cutctx/cache/compression_store.py:60-65 so there is one definition in the
# tree rather than three drifting copies.

#: ``FOO_API_KEY=bar`` / ``"token": "bar"`` style assignments.
#: Group 2 absorbs the optional quotes on both sides so JSON-shaped
#: ``"token": "value"`` is matched as well as shell-shaped ``TOKEN=value``.
#: The lookaheads stop this pattern from clobbering a value that
#: ``_AUTH_VALUE_RE`` has already handled (it runs first).
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_-]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH)[A-Z0-9_-]*)"
    r"([\"']?\s*[:=]\s*[\"']?)"
    r"(?!\[REDACTED\])(?!(?:Bearer|Basic)\b)"
    r"([^\"'\s,}]+)"
)

#: ``Authorization: Bearer <token>`` / ``Basic <token>``.
_AUTH_VALUE_RE = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{12,}")

#: OpenAI / Anthropic style provider keys: ``sk-``, ``sk-ant-``, ``sess-``.
_PROVIDER_KEY_RE = re.compile(r"\b(?:sk|sess)[-_][A-Za-z0-9_-]{12,}\b")

#: Cutctx licence keys: ``<tier-prefix>_<hex hmac>`` (e.g. ``hlk_9f3c…``).
_LICENSE_KEY_RE = re.compile(r"\b[a-z]{2,6}_[0-9a-f]{32,}\b")

#: Order matters. ``_AUTH_VALUE_RE`` must run before
#: ``_SECRET_ASSIGNMENT_RE``, otherwise the latter matches the key
#: "Authorization", treats the scheme word "Bearer" as the value, redacts
#: *that*, and leaves the actual token in cleartext.
_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_AUTH_VALUE_RE, r"\1 " + REDACTED),
    (_SECRET_ASSIGNMENT_RE, r"\1\2" + REDACTED),
    (_PROVIDER_KEY_RE, REDACTED),
    (_LICENSE_KEY_RE, REDACTED),
)

# --- Key-name matchers -----------------------------------------------------
# Superset of cutctx/proxy/helpers.py:_should_redact_key. That helper is
# suffix-only; this one also matches infixes so ``admin-key-v2``,
# ``x-cutctx-credential`` and ``client_apikey`` are caught.
_SECRET_NAME_PARTS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "admin_key",
    "client_key",
    "license_key",
    "licence_key",
    "secret",
    "password",
    "passwd",
    "credential",
    "authorization",
    "auth_token",
    "access_token",
    "refresh_token",
    "session_token",
    "bearer",
    "private_key",
    "signing_key",
    "cookie",
)

_SECRET_NAME_SUFFIXES: tuple[str, ...] = (
    "_key",
    "_token",
    "_secret",
    "_password",
)

# Registered literal secret values (admin key, client key, licence key).
# These have no guessable shape, so exact-value substitution is the only way
# to catch them. Stored in a module-level set; callers register at startup.
_REGISTERED_SECRETS: set[str] = set()

#: Values shorter than this are ignored when registering — redacting a 3-char
#: string would corrupt unrelated log content.
_MIN_REGISTERED_SECRET_LEN = 8


def register_secret_value(value: str | None) -> None:
    """Register a literal secret so every sink redacts it by exact match.

    Used for credentials with no guessable shape — most importantly the
    operator-chosen admin API key, which no regex can identify.
    """
    if not value:
        return
    candidate = str(value).strip()
    if len(candidate) >= _MIN_REGISTERED_SECRET_LEN:
        _REGISTERED_SECRETS.add(candidate)


def clear_registered_secrets() -> None:
    """Drop all registered literal secrets (used by tests)."""
    _REGISTERED_SECRETS.clear()


def is_secret_key_name(key: Any) -> bool:
    """True if a mapping key's *name* implies its value is a credential."""
    if not isinstance(key, str):
        return False
    normalized = key.strip().lower().replace("-", "_").replace(" ", "_")
    if any(part in normalized for part in _SECRET_NAME_PARTS):
        return True
    return normalized.endswith(_SECRET_NAME_SUFFIXES)


def redact_text(value: str) -> str:
    """Redact credential-shaped substrings and registered secrets from text."""
    if not value:
        return value
    result = value
    # Registered literal values first: an exact match is unambiguous, and
    # doing it first stops a later pattern from partially rewriting it.
    for secret in _REGISTERED_SECRETS:
        if secret in result:
            result = result.replace(secret, REDACTED)
    for pattern, replacement in _VALUE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_structure(value: Any, *, _depth: int = 0) -> Any:
    """Recursively redact credentials from a JSON-like structure.

    Applies both rules: a value whose *key name* implies a credential is
    replaced wholesale; every remaining string is scanned for credential
    *shapes* and registered literal secrets.

    Returns a new object; the input is never mutated.
    """
    # Bound recursion so a pathological/cyclic structure cannot hang a log write.
    if _depth > 12:
        return value
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if is_secret_key_name(key) and item is not None:
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_structure(item, _depth=_depth + 1)
        return redacted
    if isinstance(value, list | tuple):
        rebuilt = [redact_structure(item, _depth=_depth + 1) for item in value]
        return type(value)(rebuilt) if isinstance(value, tuple) else rebuilt
    if isinstance(value, str):
        return redact_text(value)
    return value

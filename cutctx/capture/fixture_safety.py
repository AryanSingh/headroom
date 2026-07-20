"""Deterministic sanitization and secret scanning for protocol fixtures."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any

SENSITIVE_HEADER_PARTS = (
    "authorization",
    "api-key",
    "apikey",
    "token",
    "secret",
    "cookie",
    "attestation",
)
ID_KEY_PARTS = ("session", "thread", "request", "response", "call", "tool_use")
TEXT_KEYS = {
    "content",
    "input",
    "instructions",
    "output",
    "prompt",
    "reasoning",
    "system",
    "text",
}
SAFE_TEXT_KEYS = {
    "action",
    "client",
    "client_version",
    "id",
    "method",
    "model",
    "name",
    "path",
    "role",
    "transport",
    "type",
}
_SECRET_PATTERNS = (
    ("secret", re.compile(r"\b(?:sk|sess)[-_][A-Za-z0-9_-]{8,}\b", re.I)),
    ("bearer token", re.compile(r"\bBearer\s+(?!<redacted>)[^\s\"']+", re.I)),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    (
        "home-directory path",
        re.compile(r"(?:/Users/[^/\s]+|/home/[^/\s]+|[A-Z]:\\\\Users\\\\[^\\\\\s]+)"),
    ),
    ("cookie", re.compile(r"\b(?:cookie|set-cookie)\s*[:=]\s*(?!<redacted>)[^\s,;]+", re.I)),
)


class FixtureSafetyError(ValueError):
    """Raised when sanitized fixture material still contains private data."""


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:12]


def _synthetic_text(value: str, *, kind: str = "text") -> str:
    if not value:
        return value
    marker = f"<synthetic:{kind}:{_digest(value)}>"
    target = max(len(marker), len(value))
    repeats = (target + len(marker) - 1) // len(marker)
    return (marker * repeats)[:target]


def _synthetic_base64(value: str) -> str:
    try:
        decoded_size = len(base64.b64decode(value, validate=True))
    except Exception:
        decoded_size = max(1, len(value) * 3 // 4)
    seed = hashlib.sha256(value.encode("ascii", errors="replace")).digest()
    synthetic = (seed * ((decoded_size + len(seed) - 1) // len(seed)))[:decoded_size]
    return base64.b64encode(synthetic).decode("ascii")


def _id_kind(key: str) -> str | None:
    lowered = key.lower()
    for kind in ID_KEY_PARTS:
        if kind in lowered and (
            lowered == kind or lowered.endswith("_id") or lowered.endswith("id")
        ):
            return kind
    return None


def _sanitize(value: Any, *, key: str = "", in_headers: bool = False) -> Any:
    lowered = key.lower()
    if in_headers and lowered == "chatgpt-account-id":
        return f"acct_fixture_{_digest(str(value))}"
    if in_headers and any(part in lowered for part in SENSITIVE_HEADER_PARTS):
        return "<redacted>"
    if lowered == "encrypted_content" and isinstance(value, str):
        return f"encrypted_fixture_{_digest(value)}"
    if isinstance(value, str) and lowered == "image_url" and value.startswith("data:"):
        prefix, separator, encoded = value.partition(",")
        if separator and ";base64" in prefix:
            return f"{prefix},{_synthetic_base64(encoded)}"
        return _synthetic_text(value, kind="image_url")
    if isinstance(value, str) and (lowered.endswith("_b64") or lowered == "data"):
        return _synthetic_base64(value)
    identifier_kind = _id_kind(lowered)
    if identifier_kind and isinstance(value, str):
        return f"{identifier_kind}_fixture_{_digest(value)}"
    if isinstance(value, dict):
        child_headers = in_headers or lowered in {"headers", "request_headers", "response_headers"}
        return {
            str(child_key): _sanitize(child, key=str(child_key), in_headers=child_headers)
            for child_key, child in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(child, key=key, in_headers=in_headers) for child in value]
    if isinstance(value, str):
        if lowered in SAFE_TEXT_KEYS:
            return value
        if lowered in TEXT_KEYS or any(
            token in lowered for token in ("message", "description", "metadata", "repo", "path")
        ):
            return _synthetic_text(value, kind=lowered or "text")
        # Unknown opaque values are scanned after sanitization. Replace them
        # only when they carry a known private-data shape.
        if any(pattern.search(value) for _, pattern in _SECRET_PATTERNS):
            return _synthetic_text(value, kind=lowered or "opaque")
    return value


def sanitize_capture_record(record: Any) -> Any:
    """Return a deterministic, structure-preserving sanitized copy."""

    sanitized = _sanitize(record)
    assert_fixture_safe(sanitized)
    return sanitized


def assert_fixture_safe(value: Any) -> None:
    """Refuse data containing credentials, private paths, email, or raw prompts."""

    def check_prompt_fields(node: Any, key: str = "") -> None:
        lowered = key.lower()
        if isinstance(node, dict):
            for child_key, child in node.items():
                check_prompt_fields(child, str(child_key))
            return
        if isinstance(node, list):
            for child in node:
                check_prompt_fields(child, key)
            return
        if (
            isinstance(node, str)
            and lowered not in SAFE_TEXT_KEYS
            and (
                lowered in TEXT_KEYS
                or any(token in lowered for token in ("message", "description", "metadata", "repo"))
            )
            and node
            and not node.startswith(("<synthetic:", "encrypted_fixture_"))
        ):
            raise FixtureSafetyError(f"fixture contains unredacted prompt field {key!r}")

    check_prompt_fields(value)
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for label, pattern in _SECRET_PATTERNS:
        if pattern.search(serialized):
            raise FixtureSafetyError(f"fixture contains unredacted {label}")
    if re.search(
        r'"(?:authorization|x-api-key|cookie|openai-attestation)"\s*:\s*"(?!<redacted>)',
        serialized,
        re.I,
    ):
        raise FixtureSafetyError("fixture contains an unredacted secret header")

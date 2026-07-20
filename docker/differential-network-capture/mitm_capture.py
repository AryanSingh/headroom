"""mitmproxy addon that writes sanitized HTTP exchanges as JSONL."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from mitmproxy import http

LANE = os.environ.get("CAPTURE_LANE", "unknown")
OUTPUT = Path(os.environ.get("CAPTURE_OUTPUT", f"/captures/{LANE}.jsonl"))
INCLUDE_HOSTS = {
    host.strip().lower()
    for host in os.environ.get("CAPTURE_INCLUDE_HOSTS", "api.anthropic.com").split(",")
    if host.strip()
}
SENSITIVE_HEADER_PARTS = (
    "authorization",
    "api-key",
    "apikey",
    "token",
    "secret",
    "cookie",
    "attestation",
)
SENSITIVE_QUERY_PARTS = ("key", "token", "secret", "signature", "code")
TEXT_KEYS = {
    "content",
    "description",
    "input",
    "instructions",
    "output",
    "prompt",
    "reasoning",
    "system",
    "text",
}
SAFE_KEYS = {"model", "name", "role", "type"}
ID_PARTS = ("session", "thread", "request", "response", "call", "tool_use")
_sequence = 0


def _redact_headers(headers: http.Headers) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items(multi=True):
        if any(part in key.lower() for part in SENSITIVE_HEADER_PARTS):
            result[key] = "<redacted>"
        else:
            result[key] = value
    return result


def _sanitize_url(url: str) -> str:
    parsed = urlsplit(url)
    pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if any(part in key.lower() for part in SENSITIVE_QUERY_PARTS):
            pairs.append((key, "<redacted>"))
        else:
            pairs.append((key, value))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(pairs), ""))


def _request_json(content: bytes) -> object | None:
    try:
        return _sanitize_json(json.loads(content.decode("utf-8")))
    except Exception:
        return None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:12]


def _synthetic_text(value: str, key: str) -> str:
    if not value:
        return value
    marker = f"<synthetic:{key or 'text'}:{_digest(value)}>"
    target = max(len(marker), len(value))
    return (marker * ((target + len(marker) - 1) // len(marker)))[:target]


def _synthetic_base64(value: str) -> str:
    try:
        decoded_size = len(base64.b64decode(value, validate=True))
    except Exception:
        decoded_size = max(1, len(value) * 3 // 4)
    seed = hashlib.sha256(value.encode("ascii", errors="replace")).digest()
    synthetic = (seed * ((decoded_size + len(seed) - 1) // len(seed)))[:decoded_size]
    return base64.b64encode(synthetic).decode("ascii")


def _identifier_kind(key: str) -> str | None:
    lowered = key.lower()
    for part in ID_PARTS:
        if part in lowered and (
            lowered == part or lowered.endswith("_id") or lowered.endswith("id")
        ):
            return part
    return None


def _sanitize_json(value: object, key: str = "") -> object:
    """Preserve protocol shape while removing prompts and stable identifiers."""

    lowered = key.lower()
    if lowered == "encrypted_content" and isinstance(value, str):
        return f"encrypted_fixture_{_digest(value)}"
    if isinstance(value, str) and lowered == "image_url" and value.startswith("data:"):
        prefix, separator, encoded = value.partition(",")
        if separator and ";base64" in prefix:
            return f"{prefix},{_synthetic_base64(encoded)}"
        return _synthetic_text(value, "image_url")
    if isinstance(value, str) and (lowered.endswith("_b64") or lowered == "data"):
        return _synthetic_base64(value)
    identifier_kind = _identifier_kind(lowered)
    if identifier_kind and isinstance(value, str):
        return f"{identifier_kind}_fixture_{_digest(value)}"
    if isinstance(value, dict):
        return {
            str(child_key): _sanitize_json(child, str(child_key))
            for child_key, child in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_json(child, key) for child in value]
    if isinstance(value, str):
        if lowered in SAFE_KEYS:
            return value
        if lowered in TEXT_KEYS or any(
            part in lowered for part in ("message", "metadata", "repo", "path")
        ):
            return _synthetic_text(value, lowered)
        if re.search(
            r"(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|/Users/[^/\s]+|/home/[^/\s]+)",
            value,
            re.I,
        ):
            return _synthetic_text(value, lowered)
    return value


def response(flow: http.HTTPFlow) -> None:
    global _sequence
    host = flow.request.pretty_host.lower()
    if INCLUDE_HOSTS and host not in INCLUDE_HOSTS:
        return

    _sequence += 1
    request_body = flow.request.raw_content or b""
    response_body = flow.response.raw_content if flow.response else b""
    record = {
        "lane": LANE,
        "sequence": _sequence,
        "timestamp": time.time(),
        "method": flow.request.method,
        "url": _sanitize_url(flow.request.pretty_url),
        "host": flow.request.pretty_host,
        "request_headers": _redact_headers(flow.request.headers),
        "request_body_size": len(request_body),
        "request_body_sha256": hashlib.sha256(request_body).hexdigest() if request_body else None,
        "request_json": _request_json(request_body),
        "response_status": flow.response.status_code if flow.response else None,
        "response_headers": _redact_headers(flow.response.headers) if flow.response else {},
        "response_body_size": len(response_body),
        "response_body_sha256": hashlib.sha256(response_body).hexdigest()
        if response_body
        else None,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.chmod(0o700)
    with OUTPUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, separators=(",", ":"), sort_keys=True))
        fh.write("\n")
    OUTPUT.chmod(0o600)

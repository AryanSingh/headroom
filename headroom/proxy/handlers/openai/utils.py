"""OpenAI handler mixin for HeadroomProxy.

Contains all OpenAI Chat Completions, Responses API, and passthrough handlers.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import copy
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING, Any

from headroom.proxy.helpers import (
    COMPRESSION_TIMEOUT_SECONDS,
    _headroom_bypass_enabled,
    extract_tags,
    jitter_delay_ms,
)
from headroom.proxy.stage_timer import StageTimer, emit_stage_timings_log
from headroom.proxy.ws_session_registry import (
    TerminationCause,
    WebSocketSessionRegistry,
    WSSessionHandle,
)

if TYPE_CHECKING:
    from fastapi import Request, WebSocket
    from fastapi.responses import JSONResponse, Response, StreamingResponse

import httpx

from headroom.copilot_auth import apply_copilot_api_auth, build_copilot_upstream_url
from headroom.pipeline import PipelineStage, summarize_routing_markers
from headroom.proxy.auth_mode import classify_auth_mode, classify_client
from headroom.proxy.compression_decision import CompressionDecision
from headroom.proxy.cost import _summarize_transforms, header_safe_transforms
from headroom.proxy.outcome import RequestOutcome
from headroom.proxy.project_context import classify_project, set_current_project

logger = logging.getLogger("headroom.proxy")

_OPENAI_RESPONSES_UNIT_CACHE_MAX_ENTRIES = 10_000
_OPENAI_RESPONSES_UNIT_CACHE_VERSION = "openai_responses_unit_v1"
_OPENAI_RESPONSES_UNIT_PARALLELISM_ENV = "HEADROOM_TOOL_OUTPUT_COMPRESSION_PARALLELISM"
_OPENAI_RESPONSES_UNIT_PARALLELISM_DEFAULT = 4
_OPENAI_RESPONSES_UNIT_PARALLELISM_MAX = 16
_OPENAI_RESPONSES_UNIT_CACHE_INIT_LOCK = threading.RLock()
_OPENAI_RESPONSES_UNIT_EXECUTOR_LOCK = threading.RLock()
_OPENAI_RESPONSES_UNIT_EXECUTOR: ThreadPoolExecutor | None = None

def _usage_int(value: Any) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _passthrough_usage_from_json(payload: Any) -> dict[str, int]:
    """Normalize usage from pass-through provider response shapes."""
    if not isinstance(payload, dict):
        return {}

    usage_meta = payload.get("usageMetadata")
    if isinstance(usage_meta, dict):
        return {
            "input_tokens": _usage_int(usage_meta.get("promptTokenCount")),
            "output_tokens": _usage_int(usage_meta.get("candidatesTokenCount")),
            "cache_read_input_tokens": _usage_int(usage_meta.get("cachedContentTokenCount")),
        }

    usage = payload.get("usage")
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens")
        if input_tokens is None:
            input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("output_tokens")
        if output_tokens is None:
            output_tokens = usage.get("completion_tokens")
        details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
        cache_read = details.get("cached_tokens") if isinstance(details, dict) else None
        return {
            "input_tokens": _usage_int(input_tokens),
            "output_tokens": _usage_int(output_tokens),
            "cache_read_input_tokens": _usage_int(usage.get("cache_read_input_tokens", cache_read)),
            "cache_creation_input_tokens": _usage_int(usage.get("cache_creation_input_tokens")),
        }

    return {}


def _passthrough_model_from_path(path: str, endpoint_name: str) -> str:
    marker = "/models/"
    if marker in path:
        model_part = path.split(marker, 1)[1].split("/", 1)[0]
        model = model_part.split(":", 1)[0]
        if model:
            return model
    return f"passthrough:{endpoint_name}"


def _openai_responses_unit_parallelism() -> int:
    raw = os.getenv(_OPENAI_RESPONSES_UNIT_PARALLELISM_ENV)
    if raw is None or raw.strip() == "":
        return _OPENAI_RESPONSES_UNIT_PARALLELISM_DEFAULT
    try:
        requested = int(raw)
    except ValueError:
        logger.warning(
            "Invalid %s=%r; using default %d",
            _OPENAI_RESPONSES_UNIT_PARALLELISM_ENV,
            raw,
            _OPENAI_RESPONSES_UNIT_PARALLELISM_DEFAULT,
        )
        return _OPENAI_RESPONSES_UNIT_PARALLELISM_DEFAULT
    return max(1, min(_OPENAI_RESPONSES_UNIT_PARALLELISM_MAX, requested))


def _openai_responses_unit_executor() -> ThreadPoolExecutor:
    global _OPENAI_RESPONSES_UNIT_EXECUTOR
    with _OPENAI_RESPONSES_UNIT_EXECUTOR_LOCK:
        if _OPENAI_RESPONSES_UNIT_EXECUTOR is None:
            _OPENAI_RESPONSES_UNIT_EXECUTOR = ThreadPoolExecutor(
                max_workers=_OPENAI_RESPONSES_UNIT_PARALLELISM_MAX,
                thread_name_prefix="headroom-openai-unit",
            )
        return _OPENAI_RESPONSES_UNIT_EXECUTOR


def _openai_responses_unit_cache_key(unit: Any, *, model: str) -> str:
    text_hash = hashlib.sha256(unit.text.encode("utf-8", errors="replace")).hexdigest()
    key_payload = {
        "version": _OPENAI_RESPONSES_UNIT_CACHE_VERSION,
        "model": model,
        "provider": unit.provider,
        "endpoint": unit.endpoint,
        "role": unit.role,
        "item_type": unit.item_type,
        "cache_zone": unit.cache_zone,
        "mutable": unit.mutable,
        "min_bytes": unit.min_bytes,
        "context": unit.context,
        "question": unit.question,
        "bias": unit.bias,
        "metadata": unit.metadata,
        "text_sha256": text_hash,
    }
    serialized = json.dumps(key_payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _openai_responses_result_with_cache_hit(result: Any) -> Any:
    router_result = getattr(result, "router_result", None)
    if router_result is None:
        return result
    return replace(result, router_result=replace(router_result, cache_hit=True))


def _codex_ws_text_shape(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "empty"
    if stripped.startswith("```"):
        return "code_fence"
    if stripped.startswith("<") and stripped.endswith(">"):
        return "xml_or_html"
    if stripped.startswith("["):
        return "json_array_like"
    if stripped.startswith("{"):
        lines = [line for line in stripped.splitlines() if line.strip()]
        if len(lines) > 1 and all(line.lstrip().startswith("{") for line in lines[:20]):
            return "jsonl_like"
        return "json_object_like"
    if stripped.startswith("Traceback (most recent call last)"):
        return "traceback"
    lines = stripped.splitlines()
    sample = lines[:50]
    if sample:
        timestamp_lines = sum(
            1
            for line in sample
            if len(line) >= 10 and line[:4].isdigit() and line[4:5] == "-" and line[7:8] == "-"
        )
        level_lines = sum(
            1
            for line in sample
            if any(level in line for level in (" ERROR ", " WARN ", " WARNING ", " INFO "))
        )
        search_lines = sum(
            1
            for line in sample
            if ":" in line and line.split(":", 2)[1:2] and line.split(":", 2)[1].isdigit()
        )
        if timestamp_lines >= max(2, len(sample) // 5) or level_lines >= max(2, len(sample) // 5):
            return "log_like"
        if search_lines >= max(2, len(sample) // 3):
            return "search_result_like"
    return "plain_text_like"


def _json_debug_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def _log_codex_compression_debug(_event: str, **_payload: Any) -> None:
    return


def _codex_compression_debug_enabled() -> bool:
    return _log_codex_compression_debug is not _CODEX_COMPRESSION_DEBUG_NOOP


def _json_shape(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except Exception as exc:
        return {"is_json": False, "error": type(exc).__name__}
    if isinstance(parsed, dict):
        return {
            "is_json": True,
            "kind": "object",
            "keys": list(parsed.keys()),
            "length": len(parsed),
        }
    if isinstance(parsed, list):
        return {"is_json": True, "kind": "array", "length": len(parsed)}
    return {"is_json": True, "kind": type(parsed).__name__}


def _routing_log_debug(_router_result: Any) -> list[dict[str, Any]]:
    return []


def _json_byte_len(value: Any) -> int:
    return len(_json_debug_dumps(value).encode("utf-8", errors="replace"))


def _compact_openai_tool_schema_value(
    value: Any,
    _parent_key: str | None = None,
) -> Any:
    if isinstance(value, list):
        return [_compact_openai_tool_schema_value(item, _parent_key) for item in value]

    if not isinstance(value, dict):
        return value

    compacted: dict[str, Any] = {}
    for key, child in value.items():
        # Don't drop keys that are property *names* inside a JSON Schema
        # `properties` object — only drop them when they are schema annotations.
        # e.g. a tool with a field literally named "title" must not be stripped.
        if _parent_key != "properties" and key in _OPENAI_TOOL_SCHEMA_DROP_KEYS:
            continue

        if key == "description" and isinstance(child, str):
            compacted[key] = " ".join(child.split())
            continue

        compacted[key] = _compact_openai_tool_schema_value(child, key)

    return compacted


def _compact_openai_responses_tools(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], bool, int, int]:
    tools = payload.get("tools")
    if not isinstance(tools, list) or not tools:
        return payload, False, 0, 0

    compacted_tools = _compact_openai_tool_schema_value(tools)
    before = _json_byte_len(tools)
    after = _json_byte_len(compacted_tools)
    if after >= before:
        return payload, False, before, after

    updated = copy.deepcopy(payload)
    updated["tools"] = compacted_tools
    return updated, True, before, after


def _responses_input_item_text_bytes(item: Any) -> int:
    if not isinstance(item, dict):
        return _json_byte_len(item)

    output = item.get("output")
    if isinstance(output, str):
        return len(output.encode("utf-8", errors="replace"))

    content = item.get("content")
    if isinstance(content, str):
        return len(content.encode("utf-8", errors="replace"))
    if isinstance(content, list):
        total = 0
        for part in content:
            if isinstance(part, str):
                total += len(part.encode("utf-8", errors="replace"))
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                total += len(part["text"].encode("utf-8", errors="replace"))
        return total

    return _json_byte_len(item)


def _openai_responses_context_budget(payload: dict[str, Any]) -> dict[str, Any]:
    payload_bytes = _json_byte_len(payload)
    buckets: dict[str, int] = {}
    for key in ("instructions", "tools", "input", "messages", "client_metadata"):
        if key in payload:
            buckets[key] = _json_byte_len(payload.get(key))

    other_bytes = max(payload_bytes - sum(buckets.values()), 0)
    if other_bytes:
        buckets["other"] = other_bytes

    input_breakdown: dict[str, dict[str, int]] = {}
    items = payload.get("input") or payload.get("messages")
    if isinstance(items, list):
        for item in items:
            item_type = item.get("type", "unknown") if isinstance(item, dict) else "non_dict"
            row = input_breakdown.setdefault(
                str(item_type),
                {"items": 0, "bytes": 0, "text_bytes": 0},
            )
            row["items"] += 1
            row["bytes"] += _json_byte_len(item)
            row["text_bytes"] += _responses_input_item_text_bytes(item)

    return {
        "payload_bytes": payload_bytes,
        "buckets": {
            key: {
                "bytes": value,
                "pct": (value / payload_bytes * 100.0) if payload_bytes else 0.0,
            }
            for key, value in sorted(
                buckets.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        },
        "input_breakdown": input_breakdown,
    }


def _extract_codex_handshake_headers(upstream: Any) -> list[tuple[str, str]]:
    """Return the ``x-codex-*`` headers from an upstream WS handshake response.

    OpenAI delivers the Codex subscription/rate-limit window only on the
    WebSocket handshake response headers (not in data frames). We forward
    that subset onto the client-facing 101 so Codex, ``/stats``, and the
    headroom-desktop gauge can all read the live window. Filtered strictly
    to ``x-codex-*`` -- never ``set-cookie``/``authorization``/etc.
    """
    resp = getattr(upstream, "response", None)
    headers = getattr(resp, "headers", None)
    if headers is None:
        return []
    raw_items = getattr(headers, "raw_items", None)
    try:
        items = list(raw_items()) if callable(raw_items) else list(headers.items())
    except Exception:
        return []
    out: list[tuple[str, str]] = []
    for name, value in items:
        name_str = name.decode("latin-1") if isinstance(name, (bytes, bytearray)) else str(name)
        if name_str.lower().startswith("x-codex-"):
            value_str = (
                value.decode("latin-1") if isinstance(value, (bytes, bytearray)) else str(value)
            )
            out.append((name_str, value_str))
    return out


def _infer_openai_cache_write_tokens(input_tokens: int, cache_read_tokens: int) -> int:
    """Infer OpenAI automatic prompt-cache writes from uncached input tokens.

    OpenAI reports prompt-cache reads as ``cached_tokens`` but does not expose a
    separate write counter. For dashboard observability, the uncached portion of
    a Codex/OpenAI request is the best available write-volume proxy. OpenAI has
    no write premium in our cache economics, so this affects cache-write
    counters, not dollar savings.
    """

    return max(input_tokens - cache_read_tokens, 0)


def _extract_responses_usage(event: dict[str, Any]) -> tuple[int, int, int, int, int]:
    """Return input/output/cache usage from a Responses event.

    Codex WebSocket streams include usage on ``response.completed`` events.
    The shape mirrors HTTP Responses usage:
    ``response.usage.input_tokens`` plus
    ``response.usage.input_tokens_details.cached_tokens``.
    """

    if event.get("type") != "response.completed":
        return 0, 0, 0, 0, 0

    response = event.get("response")
    if not isinstance(response, dict):
        response = {}
    usage = response.get("usage") or event.get("usage")
    if not isinstance(usage, dict):
        return 0, 0, 0, 0, 0

    def _int(value: Any) -> int:
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return 0

    input_tokens = _int(usage.get("input_tokens"))
    output_tokens = _int(usage.get("output_tokens"))
    details = usage.get("input_tokens_details")
    cached_tokens = _int(details.get("cached_tokens")) if isinstance(details, dict) else 0
    cache_write_tokens = _infer_openai_cache_write_tokens(input_tokens, cached_tokens)
    uncached_tokens = max(input_tokens - cached_tokens, 0)
    return input_tokens, output_tokens, cached_tokens, cache_write_tokens, uncached_tokens


def _decode_openai_bearer_payload(headers: dict[str, str]) -> dict[str, Any] | None:
    """Best-effort decode of an OpenAI OAuth bearer token payload.

    OpenClaw's Codex OAuth flow may forward only the bearer token after the
    provider base URL is overridden. In that case the explicit
    ``ChatGPT-Account-ID`` header can be missing even though the JWT still
    carries the account id we need to route to the ChatGPT Codex backend.
    """
    auth = headers.get("authorization") or headers.get("Authorization")
    if not auth:
        return None

    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or token.count(".") < 2:
        return None

    payload = token.split(".", 2)[1]
    payload += "=" * (-len(payload) % 4)
    # Intentionally no signature verification here: this is only a best-effort
    # routing hint extractor. Upstream still performs the actual auth/authz checks.
    try:
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        data = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None

    return data if isinstance(data, dict) else None


def _resolve_codex_routing_headers(headers: dict[str, str]) -> tuple[dict[str, str], bool]:
    """Resolve ChatGPT Codex routing hints from explicit headers or OAuth JWT."""
    resolved = dict(headers)
    lower_lookup = {k.lower(): k for k in resolved}

    if "chatgpt-account-id" in lower_lookup:
        return resolved, True

    payload = _decode_openai_bearer_payload(resolved)
    auth_claims = payload.get("https://api.openai.com/auth") if isinstance(payload, dict) else None
    account_id = auth_claims.get("chatgpt_account_id") if isinstance(auth_claims, dict) else None
    if isinstance(account_id, str) and account_id.strip():
        resolved["ChatGPT-Account-ID"] = account_id.strip()
        return resolved, True

    return resolved, False


_CODEX_COMPRESSION_DEBUG_NOOP = _log_codex_compression_debug

_OPENAI_TOOL_SCHEMA_DROP_KEYS = {
    "$id",
    "$schema",
    "$comment",
    "deprecated",
    "examples",
    "example",
    "markdownDescription",
    "readOnly",
    "title",
    "writeOnly",
}

RESPONSES_CONTEXT_SEARCH_TIMEOUT_SECONDS = 2.0

WS_FIRST_FRAME_TIMEOUT_SECONDS = 60.0


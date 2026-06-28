"""Conservative tool-surface slimming for oversized tool manifests."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from cutctx.utils import extract_user_query

_ENABLE_ENV = "CUTCTX_TOOL_SURFACE_SLIMMING"
_MAX_TOOLS_ENV = "CUTCTX_TOOL_SURFACE_MAX_TOOLS"
_MIN_TOOLS_ENV = "CUTCTX_TOOL_SURFACE_MIN_TOOLS"

_DEFAULT_MAX_TOOLS = 24
_DEFAULT_MIN_TOOLS = 12
_MAX_SCHEMA_CHARS = 1600
_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "get",
    "help",
    "in",
    "into",
    "of",
    "on",
    "or",
    "show",
    "the",
    "to",
    "use",
    "with",
}
_FORCED_PREFIXES = ("cutctx", "memory_", "mcp__", "ccr_")


@dataclass(frozen=True)
class ToolSurfaceResult:
    tools: list[dict[str, Any]]
    modified: bool
    tokens_saved: int
    dropped_count: int
    kept_count: int


def tool_surface_slimming_enabled() -> bool:
    return os.environ.get(_ENABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def tool_surface_limits() -> tuple[int, int]:
    max_tools = _coerce_positive_int(os.environ.get(_MAX_TOOLS_ENV), _DEFAULT_MAX_TOOLS)
    min_tools = _coerce_positive_int(os.environ.get(_MIN_TOOLS_ENV), _DEFAULT_MIN_TOOLS)
    return max(max_tools, 1), max(min_tools, 1)


def slim_tool_surface(
    tools: list[dict[str, Any]] | None,
    *,
    query: str,
    tokenizer: Any | None = None,
    tool_choice: Any = None,
) -> ToolSurfaceResult:
    if not tool_surface_slimming_enabled() or not isinstance(tools, list):
        return ToolSurfaceResult(tools or [], False, 0, 0, len(tools or []))

    max_tools, min_tools = tool_surface_limits()
    if len(tools) < min_tools or len(tools) <= max_tools:
        return ToolSurfaceResult(tools, False, 0, 0, len(tools))

    explicit_tool_names = _explicit_tool_names(tool_choice)
    query_terms = _query_terms(query)

    ranked: list[tuple[int, int, dict[str, Any], str | None, bool]] = []
    for index, tool in enumerate(tools):
        tool_name = _tool_name(tool)
        forced = (
            not tool_name
            or tool_name in explicit_tool_names
            or any(tool_name.startswith(prefix) for prefix in _FORCED_PREFIXES)
        )
        ranked.append((_tool_score(tool, query_terms), index, tool, tool_name, forced))

    forced = [entry for entry in ranked if entry[4]]
    forced_indexes = {entry[1] for entry in forced}
    remaining = [entry for entry in ranked if entry[1] not in forced_indexes]
    target_remaining = max(0, max_tools - len(forced))
    if target_remaining <= 0:
        kept = sorted(forced, key=lambda item: item[1])
    else:
        chosen = sorted(
            remaining,
            key=lambda item: (item[0], _name_match_bonus(item[3], query_terms), -item[1]),
            reverse=True,
        )[:target_remaining]
        kept = sorted([*forced, *chosen], key=lambda item: item[1])

    if len(kept) >= len(tools):
        return ToolSurfaceResult(tools, False, 0, 0, len(tools))

    slimmed = [entry[2] for entry in kept]
    tokens_saved = _estimate_token_delta(tools, slimmed, tokenizer)
    return ToolSurfaceResult(
        slimmed,
        True,
        tokens_saved,
        len(tools) - len(slimmed),
        len(slimmed),
    )


def extract_responses_query(payload: dict[str, Any]) -> str:
    messages = payload.get("messages")
    if isinstance(messages, list):
        q = extract_user_query(messages)
        if q:
            return q

    input_data = payload.get("input")
    if isinstance(input_data, str):
        return input_data.strip()
    if isinstance(input_data, list):
        for item in reversed(input_data):
            text = _responses_input_text(item)
            if text:
                return text
    return ""


def _responses_input_text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""
    role = str(item.get("role") or item.get("type") or "").lower()
    if role not in {"user", "message", "input_text", "input"}:
        return ""
    content = item.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if block.get("type") in {"input_text", "text"}:
                    text = str(block.get("text", "")).strip()
                    if text:
                        return text
    text = str(item.get("text", "")).strip()
    return text


def _coerce_positive_int(raw: str | None, default: int) -> int:
    try:
        return max(1, int(raw or default))
    except (TypeError, ValueError):
        return default


def _query_terms(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_]{3,}", (query or "").lower())
        if token not in _STOPWORDS
    }


def _explicit_tool_names(tool_choice: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(tool_choice, str):
        if tool_choice not in {"auto", "none", "required"}:
            names.add(tool_choice)
        return names
    if not isinstance(tool_choice, dict):
        return names

    direct = tool_choice.get("name")
    if isinstance(direct, str) and direct:
        names.add(direct)
    fn = tool_choice.get("function")
    if isinstance(fn, dict):
        fn_name = fn.get("name")
        if isinstance(fn_name, str) and fn_name:
            names.add(fn_name)
    return names


def _tool_name(tool: dict[str, Any]) -> str | None:
    if not isinstance(tool, dict):
        return None
    if isinstance(tool.get("name"), str) and tool.get("name"):
        return str(tool["name"])
    fn = tool.get("function")
    if isinstance(fn, dict) and isinstance(fn.get("name"), str) and fn.get("name"):
        return str(fn["name"])
    return None


def _tool_description(tool: dict[str, Any]) -> str:
    if not isinstance(tool, dict):
        return ""
    if isinstance(tool.get("description"), str):
        return str(tool["description"])
    fn = tool.get("function")
    if isinstance(fn, dict) and isinstance(fn.get("description"), str):
        return str(fn["description"])
    return ""


def _tool_schema(tool: dict[str, Any]) -> Any:
    if not isinstance(tool, dict):
        return None
    for key in ("input_schema", "parameters"):
        if key in tool:
            return tool.get(key)
    fn = tool.get("function")
    if isinstance(fn, dict):
        return fn.get("parameters")
    return None


def _tool_score(tool: dict[str, Any], query_terms: set[str]) -> int:
    if not query_terms:
        return 0
    name = (_tool_name(tool) or "").lower()
    description = _tool_description(tool).lower()
    schema = _schema_text(_tool_schema(tool))
    score = _name_match_bonus(name, query_terms)
    score += 2 * sum(1 for term in query_terms if term in description)
    score += sum(1 for term in query_terms if term in schema)
    return score


def _name_match_bonus(name: str | None, query_terms: set[str]) -> int:
    if not name:
        return 0
    lowered = name.lower()
    bonus = 0
    for term in query_terms:
        if term == lowered or term in lowered:
            bonus += 6
    return bonus


def _schema_text(schema: Any) -> str:
    if schema is None:
        return ""
    try:
        return json.dumps(schema, ensure_ascii=False).lower()[:_MAX_SCHEMA_CHARS]
    except Exception:
        return ""


def _estimate_token_delta(
    before_tools: list[dict[str, Any]],
    after_tools: list[dict[str, Any]],
    tokenizer: Any | None,
) -> int:
    try:
        before_json = json.dumps(before_tools, ensure_ascii=False)
        after_json = json.dumps(after_tools, ensure_ascii=False)
        if tokenizer is not None:
            return max(0, tokenizer.count_text(before_json) - tokenizer.count_text(after_json))
        return max(0, (len(before_json.encode("utf-8")) - len(after_json.encode("utf-8"))) // 4)
    except Exception:
        return 0

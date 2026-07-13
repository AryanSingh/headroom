"""
JSON Schema compression for LLM tool definitions and results.

Achieves 30-60% token reduction on tool schemas by:
1. Stripping metadata keys (title, $schema, examples, etc.)
2. Truncating long descriptions (LLMs don't need 500-word docs)
3. Removing redundant type annotations when inferable
4. Converting array results to positional format (strip field names)
5. Shortening enum values and default markers

Compatible with both Anthropic and OpenAI tool schema formats.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────── Schema metadata keys to strip ───────────────────

# Keys that are metadata annotations, not functional for LLM tool use.
# When these appear inside a JSON Schema `properties` object's child
# dicts, they are safe to drop because the LLM only needs: name, type,
# description, required, enum, default, and nested properties.
_SCHEMA_DROP_KEYS: frozenset[str] = frozenset(
    {
        "$id",
        "$schema",
        "$comment",
        "title",  # Redundant with property name
        "examples",  # Large, rarely needed
        "example",  # Singular variant
        "markdownDescription",
        "readOnly",
        "writeOnly",
        "deprecated",
        "format",  # e.g. "date-time" — redundant with type: string
        "pattern",  # Regex constraints — LLMs rarely need these
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "minProperties",
        "maxProperties",
        "multipleOf",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "uniqueItems",
        "additionalProperties",  # Strict validation hint, not needed for LLM
        "then",
        "else",
        "if",
        "not",
        "allOf",
        "anyOf",
        "oneOf",
    }
)

# Keys that should NEVER be stripped (functional for LLM tool use).
_SCHEMA_KEEP_KEYS: frozenset[str] = frozenset(
    {
        "type",
        "description",
        "required",
        "properties",
        "items",
        "enum",
        "default",
        "const",
        "name",  # OpenAI tool definition top-level
        "parameters",  # OpenAI/Anthropic tool definition top-level
        "tool_use",  # Anthropic content block type
    }
)

# Maximum description length before truncation (tokens ≈ chars/4).
_MAX_DESCRIPTION_LENGTH = 200

# Maximum description length for deeply nested properties (shorter).
_MAX_NESTED_DESCRIPTION_LENGTH = 100

# Minimum savings ratio to apply compaction (avoid bloat on small schemas).
_MIN_SAVINGS_RATIO = 0.05


def compress_tool_schemas(
    tools: list[dict[str, Any]] | None,
    *,
    max_description_length: int = _MAX_DESCRIPTION_LENGTH,
    aggressive: bool = False,
) -> tuple[list[dict[str, Any]], bool, int, int]:
    """
    Compress tool schema definitions for token savings.

    Returns (compacted_tools, was_modified, bytes_before, bytes_after).
    """
    if not tools or not isinstance(tools, list):
        return tools or [], False, 0, 0

    before_bytes = _json_bytes(tools)

    # Built-in/reserved tools (namespace wrappers like `image_gen`, and
    # bare server-side tools like `web_search`/`image_generation`) are not
    # "function" tools — their schema is pinned by the provider and
    # validated byte-for-byte. Compressing them (stripping keys like
    # additionalProperties, truncating descriptions) silently corrupts that
    # pinned schema and the request is rejected with "Function '<name>' is
    # reserved for use by this model and must match the configured schema."
    # regardless of which model is targeted. Only client-defined "function"
    # tools are safe to compress.
    compacted = [
        tool
        if isinstance(tool, dict) and tool.get("type") not in (None, "function")
        else _compress_tool(tool, max_description_length, aggressive, depth=0)
        for tool in tools
    ]

    after_bytes = _json_bytes(compacted)

    if after_bytes >= before_bytes:
        return tools, False, before_bytes, after_bytes

    return compacted, True, before_bytes, after_bytes


def compress_tool_results(
    messages: list[dict[str, Any]],
    *,
    max_array_items_for_positional: int = 10,
    min_fields_for_positional: int = 3,
) -> list[dict[str, Any]]:
    """
    Compress tool_result content blocks by converting arrays of
    homogeneous objects to positional format.

    Before: [{"id": 1, "name": "Alice", "score": 95}, {"id": 2, "name": "Bob", "score": 87}]
    After:  {"_t": ["id", "name", "score"], "_d": [[1, "Alice", 95], [2, "Bob", 87]]}

    Only applied when arrays have enough items and fields to justify
    the schema overhead.
    """
    if not messages:
        return messages

    modified = False
    result = []

    for msg in messages:
        if not isinstance(msg, dict):
            result.append(msg)
            continue

        # Handle Anthropic tool_result content blocks
        if msg.get("type") == "tool_result":
            content = msg.get("content")
            if isinstance(content, str):
                new_content = _try_compress_json_content(
                    content, max_array_items_for_positional, min_fields_for_positional
                )
                if new_content != content:
                    msg = {**msg, "content": new_content}
                    modified = True
            elif isinstance(content, list):
                new_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = part.get("text", "")
                        new_text = _try_compress_json_content(
                            text, max_array_items_for_positional, min_fields_for_positional
                        )
                        if new_text != text:
                            new_parts.append({**part, "text": new_text})
                            modified = True
                        else:
                            new_parts.append(part)
                    else:
                        new_parts.append(part)
                if modified:
                    msg = {**msg, "content": new_parts}

        # Handle OpenAI tool message content
        elif msg.get("role") == "tool":
            content = msg.get("content", "")
            if isinstance(content, str):
                new_content = _try_compress_json_content(
                    content, max_array_items_for_positional, min_fields_for_positional
                )
                if new_content != content:
                    msg = {**msg, "content": new_content}
                    modified = True

        # Handle assistant messages with tool_use blocks (Anthropic)
        elif msg.get("role") == "assistant":
            content = msg.get("content")
            if isinstance(content, list):
                new_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "tool_result":
                        inner_content = part.get("content")
                        if isinstance(inner_content, str):
                            new_content = _try_compress_json_content(
                                inner_content,
                                max_array_items_for_positional,
                                min_fields_for_positional,
                            )
                            if new_content != inner_content:
                                new_parts.append({**part, "content": new_content})
                                modified = True
                            else:
                                new_parts.append(part)
                        else:
                            new_parts.append(part)
                    else:
                        new_parts.append(part)
                if modified:
                    msg = {**msg, "content": new_parts}

        # Handle user messages with tool_result content blocks (Anthropic format)
        # Format: {"role": "user", "content": [{"type": "tool_result", "content": "...", ...}]}
        elif msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, list):
                msg_modified = False
                new_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "tool_result":
                        inner_content = part.get("content")
                        if isinstance(inner_content, str):
                            new_content = _try_compress_json_content(
                                inner_content,
                                max_array_items_for_positional,
                                min_fields_for_positional,
                            )
                            if new_content != inner_content:
                                new_parts.append({**part, "content": new_content})
                                msg_modified = True
                            else:
                                new_parts.append(part)
                        elif isinstance(inner_content, list):
                            new_inner = []
                            for ic in inner_content:
                                if isinstance(ic, dict) and ic.get("type") == "text":
                                    text = ic.get("text", "")
                                    new_text = _try_compress_json_content(
                                        text,
                                        max_array_items_for_positional,
                                        min_fields_for_positional,
                                    )
                                    if new_text != text:
                                        new_inner.append({**ic, "text": new_text})
                                        msg_modified = True
                                    else:
                                        new_inner.append(ic)
                                else:
                                    new_inner.append(ic)
                            if msg_modified:
                                new_parts.append({**part, "content": new_inner})
                            else:
                                new_parts.append(part)
                        else:
                            new_parts.append(part)
                    else:
                        new_parts.append(part)
                if msg_modified:
                    msg = {**msg, "content": new_parts}
                    modified = True

        result.append(msg)

    return result


# ─────────────────── Internal helpers ───────────────────


def _compress_tool(
    tool: dict[str, Any],
    max_desc_len: int,
    aggressive: bool,
    depth: int,
) -> dict[str, Any]:
    """Recursively compress a single tool definition."""
    compacted: dict[str, Any] = {}

    for key, value in tool.items():
        # Strip metadata keys (but not at the top level of the tool def)
        if depth > 0 and key in _SCHEMA_DROP_KEYS and key not in _SCHEMA_KEEP_KEYS:
            continue

        if key == "description" and isinstance(value, str):
            # Truncate long descriptions
            limit = _MAX_NESTED_DESCRIPTION_LENGTH if depth > 1 else max_desc_len
            value = _truncate_description(value, limit)
            # Always normalize whitespace
            value = " ".join(value.split())

        elif key == "parameters" and isinstance(value, dict):
            value = _compress_parameters(value, max_desc_len, aggressive, depth + 1)

        elif key == "properties" and isinstance(value, dict):
            value = {
                k: _compress_tool(v, max_desc_len, aggressive, depth + 1)
                if isinstance(v, dict)
                else v
                for k, v in value.items()
            }

        elif key == "items" and isinstance(value, dict):
            value = _compress_tool(value, max_desc_len, aggressive, depth + 1)

        elif isinstance(value, dict):
            value = _compress_tool(value, max_desc_len, aggressive, depth + 1)

        elif isinstance(value, list):
            value = [
                _compress_tool(item, max_desc_len, aggressive, depth + 1)
                if isinstance(item, dict)
                else item
                for item in value
            ]

        compacted[key] = value

    return compacted


def _compress_parameters(
    params: dict[str, Any],
    max_desc_len: int,
    aggressive: bool,
    depth: int,
) -> dict[str, Any]:
    """Compress a parameters object."""
    compacted: dict[str, Any] = {}

    for key, value in params.items():
        if key in _SCHEMA_DROP_KEYS and key not in _SCHEMA_KEEP_KEYS:
            continue

        if key == "description" and isinstance(value, str):
            value = _truncate_description(value, max_desc_len)
            value = " ".join(value.split())

        elif key == "properties" and isinstance(value, dict):
            compacted_props: dict[str, Any] = {}
            for prop_name, prop_value in value.items():
                if isinstance(prop_value, dict):
                    compressed_prop = _compress_tool(
                        prop_value, max_desc_len, aggressive, depth + 1
                    )
                    # Aggressive mode: strip type from simple string properties
                    if aggressive and compressed_prop.get("type") == "string":
                        compressed_prop.pop("description", None)
                    compacted_props[prop_name] = compressed_prop
                else:
                    compacted_props[prop_name] = prop_value
            value = compacted_props

        compacted[key] = value

    return compacted


def _truncate_description(desc: str, max_len: int) -> str:
    """Truncate a description to max_len characters at a sentence boundary."""
    if len(desc) <= max_len:
        return desc

    # Try to cut at sentence boundary
    truncated = desc[:max_len]
    last_period = truncated.rfind(".")
    last_comma = truncated.rfind(",")
    cut_point = max(last_period, last_comma)

    if cut_point > max_len // 2:
        return truncated[: cut_point + 1].rstrip(",") + "..."

    return truncated.rstrip(",") + "..."


def _try_compress_json_content(
    text: str,
    max_items: int,
    min_fields: int,
) -> str:
    """Try compress JSON content, else conservatively trim code or shell text."""

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return _try_trim_code_or_shell_text(text)

    if isinstance(parsed, list) and len(parsed) >= 2:
        compressed = _try_positional_array(parsed, max_items, min_fields)
        if compressed is not None:
            result = json.dumps(compressed, separators=(",", ":"))
            original = json.dumps(parsed, separators=(",", ":"))
            if len(result) < len(original):
                return result

    return text


def _try_trim_code_or_shell_text(text: str) -> str:
    """Apply low-risk trimming only to obviously code-like or shell-like text."""

    if not isinstance(text, str) or not text.strip():
        return text
    if not _looks_like_code_or_shell(text):
        return text

    from cutctx.proxy.deblank import Deblanker
    from cutctx.proxy.snip import Snipper

    trimmed = Snipper.snip(text)
    minified, _restore_map = Deblanker.deblank(trimmed)
    return minified if len(minified) < len(text) else text


def _looks_like_code_or_shell(text: str) -> bool:
    markers = (
        "Traceback (most recent call last):",
        "$ ",
        ">>> ",
        "Exception:",
        "Error:",
        "stderr",
        "stdout",
        "diff --git",
        "def ",
        "class ",
        "function ",
        "import ",
        "#include",
        "SELECT ",
        "FROM ",
        "npm ",
        "pip ",
    )
    return any(marker in text for marker in markers)


def _try_positional_array(
    items: list[dict[str, Any]],
    max_items: int,
    min_fields: int,
) -> dict[str, Any] | None:
    """
    Convert array-of-objects to positional format if beneficial.

    Returns {"_t": [field_names], "_d": [[values...], ...]} or None.
    """
    if len(items) < 2:
        return None

    if len(items) > max_items:
        return None

    if not all(isinstance(item, dict) for item in items):
        return None

    # Extract schema from first item
    first_keys = list(items[0].keys())

    if len(first_keys) < min_fields:
        return None

    # Check all items have the same keys (homogeneous)
    key_sets = [set(item.keys()) for item in items]
    if not all(ks == set(first_keys) for ks in key_sets):
        return None

    # Build positional data
    rows = []
    for item in items:
        row = [item.get(k) for k in first_keys]
        rows.append(row)

    return {"_t": first_keys, "_d": rows}


def _json_bytes(obj: Any) -> int:
    """Fast byte count for JSON-serializable objects."""
    return len(json.dumps(obj, separators=(",", ":")).encode("utf-8"))

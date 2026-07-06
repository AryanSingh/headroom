# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""WS11 Tool-result memoization interceptor.

Per artifacts/savings-moat-expansion-specs.md WS11 step 3:
"Interception wiring alongside CCR's tool handling in response_handler.py
— extend, don't duplicate."

This module provides a thin layer that:
1. Inspects an LLM response for tool calls
2. For each allowlisted tool call, asks the ToolMemoizer if a cached
   result is available
3. If yes, fabricates a tool_result (byte-identical to the stored
   payload) so the upstream round-trip is short-circuited
4. If no, passes the tool call through to the existing CCR tool
   handling / upstream pipeline

Flag-off contract: when config.enabled is False, this module is a
strict no-op — no state, no interception, byte-identical response
passes through.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from .memoizer import MemoizeConfig, ToolMemoizer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class InterceptedToolCall:
    """A tool call intercepted from the LLM response, before
    fabrication. Carries the wire-format tool_call block so the caller
    can pass it through unchanged."""

    tool_call_id: str
    name: str
    args: Any


@dataclass
class InterceptedToolResult:
    """A fabricated tool result for a cache hit. The `content` is
    BYTE-IDENTICAL to the stored payload (per spec: 'pass-through
    re-serialization byte-identical')."""

    tool_call_id: str
    name: str
    content: str


@dataclass
class InterceptResult:
    """The result of intercepting tool calls in a single LLM response.

    - `response` is the (potentially-modified) response. With flag off,
      this is the EXACT same object as the input (no copy).
    - `fabricated` lists the tool_results that should be short-circuited
      from upstream. The caller adds these to the conversation as
      `tool` role messages with `tool_call_id` set to the matching call.
    - `passthrough_tool_calls` lists the tool calls that were NOT
      fabricated (cache miss or non-allowlisted). The caller forwards
      these to the existing CCR tool handling / upstream pipeline.
    - `replaced` is kept for backward compatibility with the spec's
      example shape; in the current implementation it is always empty
      because the interceptor does not mutate the response object —
      the caller does the replacement.
    """

    response: Any
    fabricated: list[InterceptedToolResult] = field(default_factory=list)
    passthrough_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    replaced: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# The interceptor
# ---------------------------------------------------------------------------


class MemoizeInterceptor:
    """Per-session tool-call interceptor that short-circuits cached calls.

    Usage:
        interceptor = MemoizeInterceptor(MemoizeConfig(enabled=True))
        # After each upstream LLM response:
        out = interceptor.intercept_tool_calls(response, session_id=...)
        for fab in out.fabricated:
            # Append a 'tool' role message with the fabricated content
            ...
        for tc in out.passthrough_tool_calls:
            # Forward to existing CCR tool handling / upstream
            ...
        # After the upstream tool calls return:
        interceptor.memoizer.record(session_id, tool_name, args, response_bytes)
    """

    def __init__(
        self,
        config: MemoizeConfig | None = None,
        memoizer: ToolMemoizer | None = None,
    ) -> None:
        # Default to flag-off. The flag-off golden contract: with the
        # default config, this module is a no-op.
        self.config = config or MemoizeConfig()
        self.memoizer = memoizer or ToolMemoizer(self.config)

    def intercept_tool_calls(self, response: Any, session_id: str) -> InterceptResult:
        """Inspect the response for tool calls. For each allowlisted
        call, check the memoizer. On hit, fabricate a tool_result.
        On miss, pass through to the existing pipeline.

        With flag off, the response is returned UNCHANGED (same
        object reference) and the result lists are empty.
        """
        result = InterceptResult(response=response)

        if not self.config.enabled:
            return result

        if not isinstance(response, dict):
            return result

        # Find tool calls in OpenAI / Anthropic / Google formats.
        tool_calls = self._extract_tool_calls(response)
        if not tool_calls:
            return result

        for tc in tool_calls:
            tool_name, args = self._parse_tool_call(tc)
            if not tool_name:
                continue
            decision = self.memoizer.maybe_memoize(
                session_id=session_id,
                tool_name=tool_name,
                args=args,
            )
            if decision.action == "hit" and decision.payload is not None:
                # Cache hit: fabricate a tool_result with the stored
                # bytes. Per spec, this is byte-identical to the
                # stored payload — no re-serialization.
                result.fabricated.append(
                    InterceptedToolResult(
                        tool_call_id=self._tool_call_id(tc),
                        name=tool_name,
                        content=decision.payload,
                    )
                )
            else:
                # Cache miss or non-allowlisted: pass through.
                result.passthrough_tool_calls.append(tc)

        return result

    def invalidate_for_write(self, session_id: str, tool_name: str, args: Any) -> None:
        """Public re-export of the memoizer's invalidation method
        so callers don't have to reach through the interceptor."""
        self.memoizer.invalidate_for_write(session_id, tool_name, args)

    # -----------------------------------------------------------------------
    # Wire-format detection
    # -----------------------------------------------------------------------

    def _extract_tool_calls(self, response: Any) -> list[dict[str, Any]]:
        """Find all tool_call blocks in the response, across providers.

        Supports:
        - OpenAI:     message.tool_calls[]
        - Anthropic:  message.content[] with type=tool_use
        - Google:     message.tool_calls[] with functionCall{}
        """
        try:
            choices = response.get("choices") or []
        except AttributeError:
            return []
        if not choices:
            return []
        out: list[dict[str, Any]] = []
        for choice in choices:
            message = (choice or {}).get("message") or {}
            # OpenAI / Google: tool_calls array
            tc_array = message.get("tool_calls")
            if tc_array:
                for tc in tc_array:
                    if isinstance(tc, dict):
                        out.append(tc)
            # Anthropic: content blocks
            content = message.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        out.append(block)
        return out

    def _parse_tool_call(self, tc: dict[str, Any]) -> tuple[str | None, Any]:
        """Extract (tool_name, args) from a tool_call block.

        OpenAI format:
            {"function": {"name": "...", "arguments": "<json string>"}}
        Anthropic format:
            {"name": "...", "input": {...}}
        Google format:
            {"functionCall": {"name": "...", "args": {...}}}
        """
        # OpenAI
        func = tc.get("function")
        if isinstance(func, dict):
            name = func.get("name")
            args_str = func.get("arguments")
            if isinstance(args_str, str):
                try:
                    return name, json.loads(args_str)
                except json.JSONDecodeError:
                    return name, args_str
            return name, args_str
        # Anthropic
        if "name" in tc and "input" in tc:
            return tc.get("name"), tc.get("input")
        # Google
        fc = tc.get("functionCall")
        if isinstance(fc, dict):
            return fc.get("name"), fc.get("args")
        return None, None

    def _tool_call_id(self, tc: dict[str, Any]) -> str:
        """Extract the tool_call_id from a tool_call block.

        OpenAI: tc["id"]
        Anthropic: tc["id"]
        Google: tc["id"]
        """
        return str(tc.get("id", "") or "")


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


__all__ = [
    "MemoizeInterceptor",
    "InterceptResult",
    "InterceptedToolCall",
    "InterceptedToolResult",
]

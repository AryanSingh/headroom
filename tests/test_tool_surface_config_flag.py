"""Tests for the tool_surface_slimming_enabled config flag.

Verifies that the typed config field (bool = True) overrides the env
var, and that allowlisted tools (those with forced prefixes) are never
slimmed regardless of the flag.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from cutctx.proxy.tool_surface import (
    _FORCED_PREFIXES,
    slim_tool_surface,
    tool_surface_slimming_enabled,
)


class FakeConfig:
    def __init__(self, enabled: bool = True):
        self.tool_surface_slimming_enabled = enabled


class TestToolSurfaceSlimmingEnabled:
    """Direct unit tests for the config-flag gate function."""

    def test_no_config_default_enabled(self) -> None:
        """Without config and without env, it's enabled by default."""
        with patch.dict(os.environ, clear=True):
            assert tool_surface_slimming_enabled() is True

    def test_config_false_disables(self) -> None:
        """Config False disables slimminig regardless of env."""
        with patch.dict(os.environ, {"CUTCTX_TOOL_SURFACE_SLIMMING": "true"}):
            assert tool_surface_slimming_enabled(FakeConfig(enabled=False)) is False

    def test_config_true_overrides_env_off(self) -> None:
        """Config True enables even when env var says off."""
        with patch.dict(os.environ, {"CUTCTX_TOOL_SURFACE_SLIMMING": "off"}):
            assert tool_surface_slimming_enabled(FakeConfig(enabled=True)) is True

    def test_env_off_alone_disables(self) -> None:
        """Without config, env 'off' disables."""
        with patch.dict(os.environ, {"CUTCTX_TOOL_SURFACE_SLIMMING": "0"}):
            assert tool_surface_slimming_enabled() is False


class TestToolSurfaceAllowlist:
    """Forced-prefix tools are never slimmed regardless of flag."""

    def _make_tool(self, name: str) -> dict:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": "A test tool.",
                "parameters": {"type": "object", "properties": {}},
            },
        }

    def test_cutctx_prefix_tool_kept_when_slimming_active(self) -> None:
        """cutctx-prefixed tools survive when slimming runs."""
        # Provide enough tools to trigger slimming (default max=16)
        tools = [self._make_tool(f"tool_{i}") for i in range(20)]
        tools.append(self._make_tool("cutctx_retrieve"))
        result = slim_tool_surface(
            tools,
            query="test query",
            config=FakeConfig(enabled=True),
        )
        names = {t["function"]["name"] for t in result.tools}
        assert "cutctx_retrieve" in names
        assert result.modified is True

    def test_cutctx_prefix_tool_kept_when_slimming_disabled(self) -> None:
        """When slimming is disabled all tools are kept as-is."""
        tools = [self._make_tool("cutctx_retrieve"), self._make_tool("get_weather")]
        result = slim_tool_surface(
            tools,
            query="anything",
            config=FakeConfig(enabled=False),
        )
        assert result.modified is False
        assert len(result.tools) == 2

    def test_multiple_forced_prefixes_respected(self) -> None:
        """All forced-prefix tools are kept when slimming is active."""
        tools = [self._make_tool(f"{prefix}test") for prefix in _FORCED_PREFIXES]
        # Create more than max_tools (default 16) to trigger slimming
        filler = [self._make_tool(f"extra_{i}") for i in range(20)]
        all_tools = tools + filler

        result = slim_tool_surface(
            all_tools,
            query="test",
            config=FakeConfig(enabled=True),
        )
        names = {t["function"]["name"] for t in result.tools}
        for prefix in _FORCED_PREFIXES:
            assert f"{prefix}test" in names, f"Tool with prefix '{prefix}' was slimmed"


class TestToolSurfaceHistoryForcing:
    """Tools already invoked in message history must never be slimmed out.

    Regression test for a 400 "Tool reference 'X' not found in available
    tools" error: if a prior turn called a tool whose definition then gets
    dropped by relevance-based slimming, the upstream API rejects the next
    request because a tool_use/tool_call in history has no matching schema.
    """

    def _make_tool(self, name: str) -> dict:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": "A test tool.",
                "parameters": {"type": "object", "properties": {}},
            },
        }

    def test_anthropic_tool_use_history_forces_keep(self) -> None:
        tools = [self._make_tool(f"tool_{i}") for i in range(20)]
        tools.append(self._make_tool("TaskGet"))
        messages = [
            {"role": "user", "content": "do something"},
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "toolu_1", "name": "TaskGet", "input": {}}],
            },
            {"role": "user", "content": "is work done"},
        ]
        result = slim_tool_surface(
            tools,
            query="is work done",
            config=FakeConfig(enabled=True),
            messages=messages,
        )
        names = {t["function"]["name"] for t in result.tools}
        assert "TaskGet" in names

    def test_openai_chat_tool_calls_history_forces_keep(self) -> None:
        tools = [self._make_tool(f"tool_{i}") for i in range(20)]
        tools.append(self._make_tool("get_weather"))
        messages = [
            {"role": "user", "content": "weather?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": "{}"},
                    }
                ],
            },
        ]
        result = slim_tool_surface(
            tools,
            query="anything else",
            config=FakeConfig(enabled=True),
            messages=messages,
        )
        names = {t["function"]["name"] for t in result.tools}
        assert "get_weather" in names

    def test_openai_responses_function_call_history_forces_keep(self) -> None:
        tools = [self._make_tool(f"tool_{i}") for i in range(20)]
        tools.append(self._make_tool("search_docs"))
        input_items = [
            {"type": "message", "role": "user", "content": "search for X"},
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "search_docs",
                "arguments": "{}",
            },
        ]
        result = slim_tool_surface(
            tools,
            query="follow up",
            config=FakeConfig(enabled=True),
            messages=input_items,
        )
        names = {t["function"]["name"] for t in result.tools}
        assert "search_docs" in names

    def test_no_history_still_slims_normally(self) -> None:
        """Sanity check: without matching history, unrelated tools can be dropped."""
        tools = [self._make_tool(f"tool_{i}") for i in range(20)]
        result = slim_tool_surface(
            tools,
            query="tool_0 please",
            config=FakeConfig(enabled=True),
            messages=[{"role": "user", "content": "tool_0 please"}],
        )
        assert result.modified is True
        assert len(result.tools) < len(tools)

"""Unit tests for the episodic memory subsystem.

Covers:
- EpisodicMemoryStore (file-based persistence)
- extract_session_insights (LLM + heuristic extraction)
- _filter_messages / _format_transcript (internal helpers)
- format_memory_block (tag wrapping)
- EpisodicSessionTracker (session lifecycle)
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_memory_dir():
    """Provide a temporary directory for episodic memory storage."""
    with tempfile.TemporaryDirectory(prefix="headroom_epi_test_") as d:
        yield d


@pytest.fixture
def store(tmp_memory_dir):
    """Create an EpisodicMemoryStore backed by the temp directory."""
    from headroom.memory.store import EpisodicMemoryStore

    return EpisodicMemoryStore(memory_dir=tmp_memory_dir)


@pytest.fixture
def tracker(store):
    """Create an EpisodicSessionTracker with a real store."""
    from headroom.memory.session_tracker import EpisodicSessionTracker

    return EpisodicSessionTracker(store, idle_timeout_seconds=2, enabled=True)


# ---------------------------------------------------------------------------
# EpisodicMemoryStore tests
# ---------------------------------------------------------------------------


class TestEpisodicMemoryStore:
    def test_save_and_load(self, store):
        store.save_memory("proj1", "## Session 1\n- User prefers Python")
        result = store.load_memories("proj1")
        assert "User prefers Python" in result
        assert "Session 1" in result

    def test_load_empty_project(self, store):
        assert store.load_memories("nonexistent") == ""

    def test_append(self, store):
        store.save_memory("proj1", "## S1\n- fact1")
        store.save_memory("proj1", "## S2\n- fact2")
        result = store.load_memories("proj1")
        assert "fact1" in result
        assert "fact2" in result
        assert result.count("---") == 2  # two section delimiters

    def test_empty_content_noop(self, store):
        path = store.save_memory("proj1", "")
        assert store.load_memories("proj1") == ""

    def test_whitespace_only_noop(self, store):
        store.save_memory("proj1", "   \n  ")
        assert store.load_memories("proj1") == ""

    def test_has_memories(self, store):
        assert not store.has_memories("proj1")
        store.save_memory("proj1", "content")
        assert store.has_memories("proj1")

    def test_clear_memories(self, store):
        store.save_memory("proj1", "content")
        assert store.clear_memories("proj1") is True
        assert not store.has_memories("proj1")
        assert store.clear_memories("proj1") is False  # already gone

    def test_list_projects(self, store):
        store.save_memory("aaa", "content1")
        store.save_memory("bbb", "content2")
        projects = store.list_projects()
        assert len(projects) >= 2

    def test_get_memory_stats(self, store):
        stats = store.get_memory_stats("proj1")
        assert stats["exists"] is False
        assert stats["section_count"] == 0

        store.save_memory("proj1", "## First\n- a")
        stats = store.get_memory_stats("proj1")
        assert stats["exists"] is True
        assert stats["size_bytes"] > 0
        assert stats["section_count"] >= 1

    def test_save_to_path_traversal(self, store):
        """Project hash containing ../ should be sanitized via SHA-256."""
        path = store.save_memory("../../etc/passwd", "malicious")
        # The hash is sanitized by _file_for: SHA-256 of the input
        assert path.exists()
        assert str(store.memory_dir) in str(path)
        # No file should appear outside the memory dir
        assert not str(path).startswith("../../")

    def test_compute_project_hash_stability(self):
        from headroom.memory.store import compute_project_hash

        h1 = compute_project_hash("/Users/test/myproject")
        h2 = compute_project_hash("/Users/test/myproject")
        assert h1 == h2
        assert len(h1) == 16  # 16 hex chars

    def test_compute_project_hash_normalizes(self):
        from headroom.memory.store import compute_project_hash

        h1 = compute_project_hash("/Users/test/myproject/")
        h2 = compute_project_hash("/Users/test/myproject")
        assert h1 == h2  # trailing slash normalized


# ---------------------------------------------------------------------------
# _filter_messages tests
# ---------------------------------------------------------------------------


class TestFilterMessages:
    def test_filters_system_messages(self):
        from headroom.memory.extractor import _filter_messages

        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result = _filter_messages(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_filters_empty_messages(self):
        from headroom.memory.extractor import _filter_messages

        msgs = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "  "},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = _filter_messages(msgs)
        assert len(result) == 1

    def test_filters_thinking_blocks(self):
        from headroom.memory.extractor import _filter_messages

        msgs = [
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "Let me think..."},
                    {"type": "text", "text": "Here is the answer."},
                ],
            }
        ]
        result = _filter_messages(msgs)
        assert len(result) == 1
        assert "answer" in result[0]["content"]

    def test_filters_tool_errors(self):
        from headroom.memory.extractor import _filter_messages

        msgs = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_result",
                        "is_error": True,
                        "content": "File not found",
                    },
                    {"type": "text", "text": "Let me try again."},
                ],
            }
        ]
        result = _filter_messages(msgs)
        # The entire message is dropped because has_tool_error=True
        # Actually, looking at the code: text_parts are collected, but has_tool_error
        # is set to True, so the whole message is skipped
        # Let me verify: the code says `if text_parts and not has_tool_error`
        # So yes, tool errors cause the entire assistant message to be skipped
        assert len(result) == 0

    def test_includes_successful_tool_results(self):
        from headroom.memory.extractor import _filter_messages

        msgs = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_result",
                        "is_error": False,
                        "content": "File saved successfully",
                    },
                    {"type": "text", "text": "Done!"},
                ],
            }
        ]
        result = _filter_messages(msgs)
        assert len(result) == 1
        assert "Tool output" in result[0]["content"]

    def test_string_content_preserved(self):
        from headroom.memory.extractor import _filter_messages

        msgs = [{"role": "user", "content": "Hello world"}]
        result = _filter_messages(msgs)
        assert result[0]["content"] == "Hello world"


# ---------------------------------------------------------------------------
# _format_transcript tests
# ---------------------------------------------------------------------------


class TestFormatTranscript:
    def test_basic_formatting(self):
        from headroom.memory.extractor import _format_transcript

        msgs = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = _format_transcript(msgs)
        assert "User: Hello" in result
        assert "Assistant: Hi!" in result

    def test_truncation(self):
        from headroom.memory.extractor import _format_transcript

        msgs = [{"role": "user", "content": "x" * 10000}]
        result = _format_transcript(msgs, max_chars=500)
        assert len(result) < 600
        assert "truncated" in result.lower()


# ---------------------------------------------------------------------------
# format_memory_block tests
# ---------------------------------------------------------------------------


class TestFormatMemoryBlock:
    def test_wraps_with_tag(self):
        from headroom.memory.extractor import format_memory_block

        result = format_memory_block("## Insights\n- fact1")
        assert result.startswith("[SYSTEM: Past Session Memories]")
        assert "fact1" in result

    def test_empty_insights(self):
        from headroom.memory.extractor import format_memory_block

        assert format_memory_block("") == ""
        assert format_memory_block("  ") == ""

    def test_includes_project_path(self):
        from headroom.memory.extractor import format_memory_block

        result = format_memory_block("insights", project_path="/my/project")
        assert "/my/project" in result


# ---------------------------------------------------------------------------
# extract_session_insights tests
# ---------------------------------------------------------------------------


class TestExtractSessionInsights:
    @pytest.mark.asyncio
    async def test_empty_messages(self):
        from headroom.memory.extractor import extract_session_insights

        result = await extract_session_insights([])
        assert result == ""

    @pytest.mark.asyncio
    async def test_all_filtered_messages(self):
        from headroom.memory.extractor import extract_session_insights

        result = await extract_session_insights(
            [{"role": "system", "content": "sys msg"}]
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_heuristic_fallback_no_api_key(self):
        """Without API key, falls back to heuristic extraction."""
        from headroom.memory.extractor import extract_session_insights

        msgs = [
            {
                "role": "user",
                "content": "Add dark mode to the dashboard component.tsx",
            },
            {
                "role": "assistant",
                "content": "I'll create a ThemeContext in src/theme.ts",
            },
        ]
        # Ensure no API key is available
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            result = await extract_session_insights(msgs, api_key="")
        # Heuristic fallback should produce something
        assert result != ""
        assert "Insights" in result or "dark mode" in result.lower()

    @pytest.mark.asyncio
    async def test_llm_extract_called(self):
        """When API key is provided, LLM extraction is attempted."""
        from headroom.memory.extractor import extract_session_insights

        msgs = [
            {"role": "user", "content": "Add dark mode to dashboard.py"},
            {"role": "assistant", "content": "Done! Created ThemeContext."},
        ]

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [
                {
                    "type": "text",
                    "text": "## Session Insights\n- Added dark mode",
                }
            ]
        }
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        # httpx is imported locally inside _llm_extract, so patch at source
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await extract_session_insights(
                msgs, api_key="test-key-123"
            )

        assert "dark mode" in result.lower()
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_heuristic(self):
        """LLM failure should fall back to heuristic extraction."""
        from headroom.memory.extractor import extract_session_insights

        msgs = [
            {"role": "user", "content": "Fix the bug in cache.py"},
            {"role": "assistant", "content": "Fixed! Updated the TTL logic."},
        ]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await extract_session_insights(
                msgs, api_key="test-key-123"
            )

        # Should fall back to heuristic
        assert result != ""


# ---------------------------------------------------------------------------
# EpisodicSessionTracker tests
# ---------------------------------------------------------------------------


class TestEpisodicSessionTracker:
    def test_disabled_tracker(self, store):
        from headroom.memory.session_tracker import EpisodicSessionTracker

        tracker = EpisodicSessionTracker(store, enabled=False)
        assert not tracker.enabled
        result = tracker.on_request("/project", [{"role": "user", "content": "hi"}])
        assert isinstance(result, str)  # returns hash even when disabled
        assert tracker.load_episodic_memories("/project") == ""

    def test_on_request_buffers_messages(self, store):
        from headroom.memory.session_tracker import EpisodicSessionTracker

        tracker = EpisodicSessionTracker(store, enabled=True)
        h = tracker.on_request(
            "/project",
            [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ],
        )
        assert isinstance(h, str) and len(h) == 16

        stats = tracker.get_stats()
        assert stats["active_sessions"] == 1
        assert stats["total_tracked"] == 1

    def test_on_request_accumulates(self, store):
        from headroom.memory.session_tracker import EpisodicSessionTracker

        tracker = EpisodicSessionTracker(store, enabled=True)
        tracker.on_request("/project", [{"role": "user", "content": "msg1"}])
        tracker.on_request("/project", [{"role": "user", "content": "msg2"}])
        stats = tracker.get_stats()
        assert stats["active_sessions"] == 1

    def test_load_memories_empty(self, store):
        from headroom.memory.session_tracker import EpisodicSessionTracker

        tracker = EpisodicSessionTracker(store, enabled=True)
        result = tracker.load_episodic_memories("/project")
        assert result == ""

    def test_load_memories_after_save(self, store):
        from headroom.memory.session_tracker import EpisodicSessionTracker

        tracker = EpisodicSessionTracker(store, enabled=True)
        # Save directly to store
        from headroom.memory.store import compute_project_hash

        h = compute_project_hash("/project")
        store.save_memory(h, "## Past session\n- User likes dark mode")
        result = tracker.load_episodic_memories("/project")
        assert "[SYSTEM: Past Session Memories]" in result
        assert "dark mode" in result

    @pytest.mark.asyncio
    async def test_sweep_extracts_on_idle(self, store):
        from headroom.memory.session_tracker import EpisodicSessionTracker

        tracker = EpisodicSessionTracker(
            store, idle_timeout_seconds=0, enabled=True
        )  # immediate timeout

        tracker.on_request(
            "/project",
            [{"role": "user", "content": "Add dark mode to dashboard.py"}],
        )

        # Mock the LLM extraction to avoid API calls
        with patch(
            "headroom.memory.session_tracker.extract_session_insights",
            new_callable=AsyncMock,
            return_value="## Session Insights\n- Dark mode added",
        ) as mock_extract:
            await tracker._check_idle_sessions()
            # Give background task time to complete
            await asyncio.sleep(0.1)

        mock_extract.assert_called_once()
        # Memories should now be stored
        from headroom.memory.store import compute_project_hash

        h = compute_project_hash("/project")
        assert store.has_memories(h)

    def test_get_stats(self, store):
        from headroom.memory.session_tracker import EpisodicSessionTracker

        tracker = EpisodicSessionTracker(store, enabled=True)
        stats = tracker.get_stats()
        assert stats["enabled"] is True
        assert stats["active_sessions"] == 0
        assert stats["total_tracked"] == 0

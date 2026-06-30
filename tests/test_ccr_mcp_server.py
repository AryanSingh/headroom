from __future__ import annotations

import asyncio
import importlib
import json
from types import SimpleNamespace

import pytest

from cutctx.cache.compression_store import (
    get_compression_store,
    reset_compression_store,
)
from cutctx import mcp_server


def test_shared_stats_work_without_fcntl(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mcp_server, "_HAS_FCNTL", False)
    monkeypatch.setattr(mcp_server, "fcntl", None)
    monkeypatch.setattr(mcp_server, "SHARED_STATS_DIR", tmp_path)
    monkeypatch.setattr(mcp_server, "SHARED_STATS_FILE", tmp_path / "session_stats.jsonl")
    monkeypatch.setattr(mcp_server.os, "getpid", lambda: 4242)
    monkeypatch.setattr(mcp_server.time, "time", lambda: 1001.0)

    event = {"type": "compress", "timestamp": 1000.0}
    mcp_server._append_shared_event(event)

    raw_lines = mcp_server.SHARED_STATS_FILE.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 1
    assert json.loads(raw_lines[0]) == {"type": "compress", "timestamp": 1000.0, "pid": 4242}

    events = mcp_server._read_shared_events(window_seconds=60)
    assert events == [{"type": "compress", "timestamp": 1000.0, "pid": 4242}]


# --- Shared compression store wiring ---------------------------------------
# MCP's _get_local_store() must return the get_compression_store() singleton —
# the same instance the proxy and response_handler use — so content compressed
# on either side is retrievable in-process. These pin that wiring so a private
# store can't creep back.


@pytest.fixture
def fresh_store():
    reset_compression_store()
    yield
    reset_compression_store()


def test_mcp_uses_shared_singleton_store(fresh_store) -> None:
    """MCP's store is the global singleton, not a private instance."""
    pytest.importorskip("mcp", reason="MCP SDK required")
    server = mcp_server.CutctxMCPServer(check_proxy=False)
    assert server._get_local_store() is get_compression_store()


def test_mcp_retrieves_proxy_stored_content(fresh_store) -> None:
    """Content stored via the singleton (as the proxy does) is retrievable
    through MCP's local-store path. The HTTP fallback is disabled so this
    passes only via the shared store."""
    pytest.importorskip("mcp", reason="MCP SDK required")
    original = '{"some": "original proxy-compressed content"}'
    hash_key = get_compression_store().store(original, '{"compressed": true}')

    server = mcp_server.CutctxMCPServer(check_proxy=False)
    result = asyncio.run(server._retrieve_content(hash_key, query=None))

    assert result.get("source") == "local"
    assert result["original_content"] == original


def test_mcp_compress_reports_zero_savings_for_noop_ratio_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    fresh_store,
) -> None:
    """No-op compressions should report zero savings even if an upstream
    compression_ratio field is inconsistent."""
    pytest.importorskip("mcp", reason="MCP SDK required")

    def fake_compress(messages, model):
        return SimpleNamespace(
            messages=messages,
            tokens_before=131,
            tokens_after=131,
            compression_ratio=0.0,
            transforms_applied=["router:noop"],
        )

    compress_module = importlib.import_module("cutctx.compress")
    monkeypatch.setattr(compress_module, "compress", fake_compress)

    server = mcp_server.CutctxMCPServer(check_proxy=False)
    result = server._compress_content("PASS unit test 1\nPASS unit test 2\n")

    assert result["original_tokens"] == 131
    assert result["compressed_tokens"] == 131
    assert result["tokens_saved"] == 0
    assert result["savings_percent"] == 0
    assert result["transforms"] == ["router:noop"]

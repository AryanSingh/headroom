"""Regression: a session's live requests must surface even when the shared
JSONL log file becomes unwritable.

Symptom this guards against: the dashboard kept showing *stale* on-disk
requests while the current session's requests never appeared. Root cause was a
read/write split — ``log()`` always appends to the in-memory deque, but the
file write degraded silently on ``OSError`` while ``get_recent()`` still read
the (stale) file tail first and never fell back to the deque.
"""

from __future__ import annotations

import time

from cutctx.proxy.request_logger import RequestLog, RequestLogger


def _entry(request_id: str, model: str = "claude-opus-4-5") -> RequestLog:
    return RequestLog(
        request_id=request_id,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        provider="anthropic",
        model=model,
        input_tokens_original=100,
        input_tokens_optimized=60,
        output_tokens=20,
        tokens_saved=40,
        savings_percent=40.0,
        optimization_latency_ms=1.0,
        total_latency_ms=10.0,
        tags={"client": "claude-desktop"},
        cache_hit=False,
        transforms_applied=["smart_crusher"],
    )


def test_recent_prefers_deque_when_file_write_degrades(tmp_path):
    path = tmp_path / "requests.jsonl"
    logger = RequestLogger(log_file=str(path))

    # Seed a healthy on-disk request (previous session).
    logger.log(_entry("old-session-req"))
    assert any(r["request_id"] == "old-session-req" for r in logger.get_recent(10))

    # Simulate the log file becoming unwritable mid-session (read-only fs /
    # permissions / disk full). Point the logger at a path that cannot be
    # opened for append so the real write raises OSError.
    logger.log_file = tmp_path / "no_such_dir" / "requests.jsonl"

    logger.log(_entry("live-session-req"))

    # The write should have degraded (flagged), not crashed.
    assert logger._file_write_degraded is True

    ids = {r["request_id"] for r in logger.get_recent(10)}
    # The live request MUST be visible now — served from the in-memory deque
    # rather than a stale file tail.
    assert "live-session-req" in ids
    assert "old-session-req" in ids


def test_recent_uses_file_when_writes_healthy(tmp_path):
    """Healthy path is unchanged: file-backed reads still work."""
    path = tmp_path / "requests.jsonl"
    logger = RequestLogger(log_file=str(path))
    logger.log(_entry("req-1"))
    logger.log(_entry("req-2"))

    assert logger._file_write_degraded is False
    ids = [r["request_id"] for r in logger.get_recent(10)]
    assert ids[-2:] == ["req-1", "req-2"]

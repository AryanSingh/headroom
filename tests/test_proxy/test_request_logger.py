"""Tests for the in-memory request logger.

Covers the `log_full_messages` gate, which controls whether the
pre-compression (`request_messages`) and post-compression
(`compressed_messages`) payloads persist past the in-memory entry onto disk.
Both sides are governed by the same flag so the two sides of the compression
stay in sync - it's pointless to store one without the other.
"""

from __future__ import annotations

from dataclasses import asdict

from cutctx.proxy.models import RequestLog
from cutctx.proxy.request_logger import RequestLogger


def _entry(**overrides) -> RequestLog:
    base: dict = {
        "request_id": "r1",
        "timestamp": "2026-04-24T10:00:00Z",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "input_tokens_original": 100,
        "input_tokens_optimized": 40,
        "output_tokens": 10,
        "tokens_saved": 60,
        "savings_percent": 60.0,
        "optimization_latency_ms": 1.0,
        "total_latency_ms": 20.0,
        "tags": {},
        "cache_hit": False,
        "transforms_applied": ["kompress:user:0.4"],
    }
    base.update(overrides)
    return RequestLog(**base)


def test_get_recent_strips_compressed_messages_alongside_request_and_response():
    logger = RequestLogger(log_file=None, log_full_messages=True)
    logger.log(
        _entry(
            request_messages=[{"role": "user", "content": "pre"}],
            compressed_messages=[{"role": "user", "content": "post"}],
            response_content="ok",
        )
    )

    recent = logger.get_recent(10)
    assert len(recent) == 1
    assert "request_messages" not in recent[0]
    assert "compressed_messages" not in recent[0]
    assert "response_content" not in recent[0]


def test_get_recent_with_messages_returns_compressed_messages():
    logger = RequestLogger(log_file=None, log_full_messages=True)
    logger.log(
        _entry(
            request_messages=[{"role": "user", "content": "pre"}],
            compressed_messages=[{"role": "user", "content": "post"}],
        )
    )

    recent = logger.get_recent_with_messages(10)
    assert len(recent) == 1
    assert recent[0]["request_messages"] == [{"role": "user", "content": "pre"}]
    assert recent[0]["compressed_messages"] == [{"role": "user", "content": "post"}]


def test_request_logger_marks_only_current_receipt_as_redacted():
    logger = RequestLogger(log_file=None, log_full_messages=True)
    first = _entry(
        request_id="image",
        request_messages=[
            {
                "role": "user",
                "image_url": "data:image/png;base64," + "A" * 9000,
            }
        ],
        decision_receipt={"observation": {"payload_capture": "captured"}},
    )
    second = _entry(
        request_id="text",
        request_messages=[{"role": "user", "content": "hello"}],
        decision_receipt={"observation": {"payload_capture": "captured"}},
    )

    logger.log(first)
    logger.log(second)

    rows = logger.get_recent_with_messages(2)
    assert rows[0]["decision_receipt"]["observation"]["payload_capture"] == "redacted"
    assert rows[1]["decision_receipt"]["observation"]["payload_capture"] == "captured"


def test_jsonl_file_strips_both_sides_when_log_full_messages_disabled(tmp_path):
    log_file = tmp_path / "requests.jsonl"
    logger = RequestLogger(log_file=str(log_file), log_full_messages=False)
    logger.log(
        _entry(
            request_messages=[{"role": "user", "content": "pre"}],
            compressed_messages=[{"role": "user", "content": "post"}],
            response_content="ok",
        )
    )

    import json

    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert "request_messages" not in obj
    assert "compressed_messages" not in obj
    assert "response_content" not in obj


def test_request_logger_warms_recent_entries_from_jsonl(tmp_path):
    log_file = tmp_path / "requests.jsonl"
    entry = _entry(request_id="warm-1")
    import json

    log_file.write_text(json.dumps(asdict(entry)) + "\n")

    logger = RequestLogger(log_file=str(log_file), log_full_messages=False)
    recent = logger.get_recent(10)

    assert len(recent) == 1
    assert recent[0]["request_id"] == "warm-1"


def test_get_recent_reads_live_from_shared_file_across_instances(tmp_path):
    """Two RequestLogger instances (simulating two proxy processes) sharing
    the same log_file must both see entries the other one wrote, without
    either process restarting — this is what lets 'Recent Activity' on any
    cutctx proxy's dashboard show requests handled by a different proxy."""
    log_file = tmp_path / "requests.jsonl"
    logger_a = RequestLogger(log_file=str(log_file), log_full_messages=False)
    logger_b = RequestLogger(log_file=str(log_file), log_full_messages=False)

    logger_a.log(_entry(request_id="from-a"))
    logger_b.log(_entry(request_id="from-b"))

    recent_on_a = logger_a.get_recent(10)
    recent_on_b = logger_b.get_recent(10)

    ids_on_a = {e["request_id"] for e in recent_on_a}
    ids_on_b = {e["request_id"] for e in recent_on_b}
    assert ids_on_a == {"from-a", "from-b"}
    assert ids_on_b == {"from-a", "from-b"}


def test_get_recent_with_messages_reads_live_from_shared_file_across_instances(tmp_path):
    log_file = tmp_path / "requests.jsonl"
    logger_a = RequestLogger(log_file=str(log_file), log_full_messages=True)
    logger_b = RequestLogger(log_file=str(log_file), log_full_messages=True)

    logger_a.log(
        _entry(
            request_id="from-a",
            request_messages=[{"role": "user", "content": "pre-a"}],
            compressed_messages=[{"role": "user", "content": "post-a"}],
        )
    )
    logger_b.log(
        _entry(
            request_id="from-b",
            request_messages=[{"role": "user", "content": "pre-b"}],
            compressed_messages=[{"role": "user", "content": "post-b"}],
        )
    )

    recent = logger_a.get_recent_with_messages(10)

    by_id = {entry["request_id"]: entry for entry in recent}
    assert by_id["from-a"]["request_messages"] == [{"role": "user", "content": "pre-a"}]
    assert by_id["from-b"]["compressed_messages"] == [{"role": "user", "content": "post-b"}]


def test_get_request_with_messages_prefers_shared_log_file(tmp_path):
    log_file = tmp_path / "requests.jsonl"
    logger_a = RequestLogger(log_file=str(log_file), log_full_messages=True)
    logger_b = RequestLogger(log_file=str(log_file), log_full_messages=True)

    logger_a.log(
        _entry(
            request_id="from-a",
            request_messages=[{"role": "user", "content": "pre-a"}],
            compressed_messages=[{"role": "user", "content": "post-a"}],
        )
    )

    entry = logger_b.get_request_with_messages("from-a")

    assert entry is not None
    assert entry["request_id"] == "from-a"
    assert entry["request_messages"] == [{"role": "user", "content": "pre-a"}]


def test_get_recent_falls_back_to_memory_when_no_log_file():
    logger = RequestLogger(log_file=None)
    logger.log(_entry(request_id="mem-only"))

    recent = logger.get_recent(10)
    assert [e["request_id"] for e in recent] == ["mem-only"]


def test_get_recent_with_messages_falls_back_to_memory_when_shared_log_unavailable(
    tmp_path, monkeypatch
):
    log_file = tmp_path / "requests.jsonl"
    logger = RequestLogger(log_file=str(log_file), log_full_messages=True)
    logger.log(
        _entry(
            request_id="mem-fallback",
            request_messages=[{"role": "user", "content": "pre"}],
            compressed_messages=[{"role": "user", "content": "post"}],
        )
    )

    monkeypatch.setattr(
        "cutctx.proxy.request_logger._tail_lines",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk unavailable")),
    )

    recent = logger.get_recent_with_messages(10)

    assert len(recent) == 1
    assert recent[0]["request_id"] == "mem-fallback"
    assert recent[0]["compressed_messages"] == [{"role": "user", "content": "post"}]


def test_get_request_with_messages_falls_back_to_memory_when_shared_log_unavailable(
    tmp_path, monkeypatch
):
    log_file = tmp_path / "requests.jsonl"
    logger = RequestLogger(log_file=str(log_file), log_full_messages=True)
    logger.log(
        _entry(
            request_id="mem-detail",
            request_messages=[{"role": "user", "content": "pre"}],
            compressed_messages=[{"role": "user", "content": "post"}],
        )
    )

    monkeypatch.setattr(
        "cutctx.proxy.request_logger._tail_lines",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk unavailable")),
    )

    entry = logger.get_request_with_messages("mem-detail")

    assert entry is not None
    assert entry["request_id"] == "mem-detail"
    assert entry["request_messages"] == [{"role": "user", "content": "pre"}]


def test_get_memory_stats_accounts_for_compressed_messages():
    logger = RequestLogger(log_file=None)
    logger.log(
        _entry(
            compressed_messages=[{"role": "user", "content": "post"}],
        )
    )

    stats = logger.get_memory_stats()
    assert stats.entry_count == 1
    assert stats.size_bytes > 0

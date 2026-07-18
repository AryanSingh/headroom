"""Bounded tail-read guarantees for the shared request log.

The single-trace lookup previously tailed MAX_LOG_ENTRIES (10k) full-message
entries with a quadratic buffer re-split — on a multi-hundred-MB shared log
one dashboard click froze the proxy event loop for minutes and cascaded into
/health 503 flapping.
"""

from __future__ import annotations

import json
import time

from cutctx.proxy.request_logger import RequestLogger, _tail_lines


def _write_log(path, n, payload_bytes=200):
    filler = "x" * payload_bytes
    with open(path, "w") as f:
        for i in range(n):
            f.write(json.dumps({"request_id": f"req-{i}", "blob": filler}) + "\n")


def test_tail_lines_returns_last_n(tmp_path):
    path = tmp_path / "log.jsonl"
    _write_log(path, 1_000)
    lines = _tail_lines(path, 10)
    assert len(lines) == 10
    assert json.loads(lines[-1])["request_id"] == "req-999"
    assert json.loads(lines[0])["request_id"] == "req-990"


def test_trace_lookup_finds_recent_id_quickly_in_large_log(tmp_path):
    path = tmp_path / "log.jsonl"
    # ~40 MB log: 20k entries × ~2 KB. The lookup must stay bounded by the
    # trace window, not the file size.
    _write_log(path, 20_000, payload_bytes=2_000)
    logger = RequestLogger(log_file=str(path))

    start = time.perf_counter()
    hit = logger.get_request_with_messages("req-19999")
    miss = logger.get_request_with_messages("req-0")
    elapsed = time.perf_counter() - start

    assert hit is not None and hit["request_id"] == "req-19999"
    # An id older than the lookup window is a miss (the inspector only
    # targets recently displayed requests).
    assert miss is None
    assert elapsed < 2.0, f"trace lookup took {elapsed:.2f}s — unbounded read regressed"

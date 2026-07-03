"""Tests for WS7 Context Assurance evidence ledger."""

from __future__ import annotations

import json

from cutctx.assurance import (
    EVENT_COMPRESSION,
    EVENT_POLICY_BLOCK,
    EVENT_POLICY_REDACT,
    EVENT_RETRIEVAL,
    EvidenceLedger,
)


def test_ledger_append_and_read(tmp_path):
    ledger = EvidenceLedger(path=tmp_path / "test.db")
    event = ledger.record(
        event_id="evt-001",
        event_type=EVENT_COMPRESSION,
        session_id="sess-1",
        workspace_id="ws-1",
        project_id="proj-1",
        detail={"original_tokens": 1000, "compressed_tokens": 300},
    )

    assert event.event_id == "evt-001"
    assert event.event_type == EVENT_COMPRESSION
    assert event.row_hash != ""

    events = ledger.query(limit=10)
    assert len(events) == 1
    assert events[0].event_id == "evt-001"


def test_ledger_hmac_chain(tmp_path):
    ledger = EvidenceLedger(path=tmp_path / "chain.db")
    ledger.record(event_id="evt-001", event_type=EVENT_COMPRESSION, session_id="sess-1")
    ledger.record(event_id="evt-002", event_type=EVENT_RETRIEVAL, session_id="sess-1")

    chain = ledger.verify_chain()
    assert chain["total_events"] == 2
    assert not chain["chain_broken"]

    # Second event (newest, events[0]) should link to first event (oldest, events[1])
    events = ledger.query(limit=10)  # Ordered by timestamp DESC
    assert events[0].prev_hash == events[1].row_hash  # Newest links to oldest


def test_ledger_chain_detects_tamper(tmp_path):
    ledger = EvidenceLedger(path=tmp_path / "tamper.db")
    ledger.record(event_id="evt-001", event_type=EVENT_COMPRESSION, session_id="sess-1")

    # Tamper with the database directly
    import sqlite3

    with sqlite3.connect(tmp_path / "tamper.db") as conn:
        conn.execute("UPDATE evidence_ledger SET event_type = 'tampered' WHERE event_id = 'evt-001'")
        conn.commit()

    chain = ledger.verify_chain()
    assert chain["chain_broken"]


def test_ledger_filter_by_type(tmp_path):
    ledger = EvidenceLedger(path=tmp_path / "filter.db")
    ledger.record(event_id="evt-001", event_type=EVENT_COMPRESSION, session_id="sess-1")
    ledger.record(event_id="evt-002", event_type=EVENT_POLICY_BLOCK, session_id="sess-1")
    ledger.record(event_id="evt-003", event_type=EVENT_POLICY_REDACT, session_id="sess-2")

    blocks = ledger.query(event_type=EVENT_POLICY_BLOCK)
    assert len(blocks) == 1
    assert blocks[0].event_id == "evt-002"

    compressions = ledger.query(event_type=EVENT_COMPRESSION)
    assert len(compressions) == 1


def test_ledger_filter_by_session(tmp_path):
    ledger = EvidenceLedger(path=tmp_path / "session.db")
    ledger.record(event_id="evt-001", event_type=EVENT_COMPRESSION, session_id="sess-1")
    ledger.record(event_id="evt-002", event_type=EVENT_COMPRESSION, session_id="sess-2")

    sess1 = ledger.query(session_id="sess-1")
    assert len(sess1) == 1
    assert sess1[0].session_id == "sess-1"


def test_ledger_stats(tmp_path):
    ledger = EvidenceLedger(path=tmp_path / "stats.db")
    ledger.record(event_id="evt-001", event_type=EVENT_COMPRESSION, session_id="sess-1")
    ledger.record(event_id="evt-002", event_type=EVENT_RETRIEVAL, session_id="sess-1")
    ledger.record(event_id="evt-003", event_type=EVENT_POLICY_BLOCK, session_id="sess-2")

    stats = ledger.stats()
    assert stats["total_events"] == 3
    assert stats["by_event_type"][EVENT_COMPRESSION] == 1
    assert stats["by_event_type"][EVENT_RETRIEVAL] == 1
    assert stats["by_event_type"][EVENT_POLICY_BLOCK] == 1
    assert not stats["chain"]["chain_broken"]


def test_ledger_export_markdown(tmp_path):
    ledger = EvidenceLedger(path=tmp_path / "export.md")
    ledger.record(event_id="evt-001", event_type=EVENT_COMPRESSION, session_id="sess-1")
    ledger.record(event_id="evt-002", event_type=EVENT_POLICY_BLOCK, session_id="sess-1",
                  detail={"reason": "Blocked by security policy"})

    md = ledger.export_bundle(fmt="markdown")
    assert "# Context Assurance Evidence Bundle" in md
    assert "EVENT_POLICY_BLOCK" in md or "policy_block" in md
    assert "Verification Instructions" in md


def test_ledger_export_json(tmp_path):
    ledger = EvidenceLedger(path=tmp_path / "export.json")
    ledger.record(event_id="evt-001", event_type=EVENT_COMPRESSION, session_id="sess-1")

    js = json.loads(ledger.export_bundle(fmt="json"))
    assert js["event_count"] == 1
    assert len(js["events"]) == 1
    assert js["chain"]["hmac_algorithm"] == "HMAC-SHA256"


def test_ledger_empty_stats(tmp_path):
    ledger = EvidenceLedger(path=tmp_path / "empty.db")
    stats = ledger.stats()
    assert stats["total_events"] == 0
    assert stats["by_event_type"] == {}


def test_ledger_details_roundtrip(tmp_path):
    ledger = EvidenceLedger(path=tmp_path / "detail.db")
    detail = {"reason": "test", "count": 42, "nested": {"key": "value"}}
    ledger.record(
        event_id="evt-detail",
        event_type=EVENT_POLICY_BLOCK,
        session_id="sess-1",
        detail=detail,
    )

    events = ledger.query(limit=10)
    assert events[0].detail_json is not None
    restored = json.loads(events[0].detail_json)
    assert restored["reason"] == "test"
    assert restored["nested"]["key"] == "value"

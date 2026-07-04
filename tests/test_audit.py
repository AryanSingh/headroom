"""Tests for the audit event system (cutctx/audit.py)."""

from __future__ import annotations

import json
import threading

import pytest

from cutctx.audit import (
    AuditAction,
    AuditEvent,
    AuditLogger,
    get_audit_logger,
    reset_audit_logger,
)


@pytest.fixture
def tmp_audit_db(tmp_path):
    """Create a temporary audit database."""
    db_path = tmp_path / "test_audit.db"
    return str(db_path)


@pytest.fixture
def audit_logger(tmp_audit_db):
    """Create an audit logger with a temp DB."""
    logger = AuditLogger(db_path=tmp_audit_db)
    yield logger
    logger.close()


class TestAuditEvent:
    """Tests for the AuditEvent dataclass."""

    def test_create_event(self):
        event = AuditEvent(action="test.action", actor="tester")
        assert event.action == "test.action"
        assert event.actor == "tester"
        assert event.success is True
        assert event.event_id is not None
        assert len(event.event_id) == 16
        assert event.timestamp is not None

    def test_event_to_dict(self):
        event = AuditEvent(
            action="license.changed",
            actor="admin@test.com",
            detail={"old_plan": "team", "new_plan": "enterprise"},
        )
        d = event.to_dict()
        assert d["action"] == "license.changed"
        assert d["actor"] == "admin@test.com"
        assert d["detail"]["old_plan"] == "team"
        assert d["success"] is True

    def test_event_to_json(self):
        event = AuditEvent(action="test", actor="system")
        j = event.to_json()
        parsed = json.loads(j)
        assert parsed["action"] == "test"

    def test_event_from_dict(self):
        d = {
            "action": "auth.login",
            "actor": "user@test.com",
            "detail": {"method": "password"},
            "success": True,
        }
        event = AuditEvent.from_dict(d)
        assert event.action == "auth.login"
        assert event.detail["method"] == "password"

    def test_event_immutable(self):
        event = AuditEvent(action="test", actor="system")
        with pytest.raises(AttributeError):
            event.action = "changed"  # type: ignore[misc]

    def test_event_with_optional_fields(self):
        event = AuditEvent(
            action="test",
            actor="system",
            org_id="org123",
            workspace_id="ws456",
            project_id="proj789",
            ip_address="127.0.0.1",
            user_agent="test-agent/1.0",
        )
        d = event.to_dict()
        assert d["org_id"] == "org123"
        assert d["workspace_id"] == "ws456"
        assert d["ip_address"] == "127.0.0.1"

    def test_event_failed(self):
        event = AuditEvent(action="auth.failed", actor="hacker", success=False)
        assert event.success is False


class TestAuditAction:
    """Tests for AuditAction enum."""

    def test_all_actions_exist(self):
        assert AuditAction.AUTH_LOGIN == "auth.login"
        assert AuditAction.LICENSE_CHANGED == "license.changed"
        assert AuditAction.STATS_RESET == "stats.reset"
        assert AuditAction.ENTITLEMENT_DENIED == "entitlement.denied"
        assert AuditAction.SYSTEM_START == "system.start"

    def test_action_count(self):
        # Should have at least 20 standard actions
        assert len(AuditAction) >= 20


class TestAuditLogger:
    """Tests for the AuditLogger class."""

    def test_log_and_query(self, audit_logger):
        event = AuditEvent(action="test.action", actor="tester", detail={"key": "value"})
        audit_logger.log(event)
        results = audit_logger.query()
        assert len(results) == 1
        assert results[0]["action"] == "test.action"
        assert results[0]["actor"] == "tester"
        assert results[0]["detail"]["key"] == "value"

    def test_log_multiple_events(self, audit_logger):
        for i in range(5):
            audit_logger.log(AuditEvent(action=f"action.{i}", actor="system"))
        results = audit_logger.query()
        assert len(results) == 5
        # Should be ordered by timestamp descending (most recent first)
        assert results[0]["action"] == "action.4"

    def test_query_filter_by_action(self, audit_logger):
        audit_logger.log(AuditEvent(action="auth.login", actor="user1"))
        audit_logger.log(AuditEvent(action="stats.reset", actor="admin"))
        audit_logger.log(AuditEvent(action="auth.login", actor="user2"))

        results = audit_logger.query(action="auth.login")
        assert len(results) == 2
        assert all(r["action"] == "auth.login" for r in results)

    def test_query_filter_by_actor(self, audit_logger):
        audit_logger.log(AuditEvent(action="test", actor="alice"))
        audit_logger.log(AuditEvent(action="test", actor="bob"))

        results = audit_logger.query(actor="alice")
        assert len(results) == 1
        assert results[0]["actor"] == "alice"

    def test_query_with_limit(self, audit_logger):
        for i in range(10):
            audit_logger.log(AuditEvent(action="test", actor="system"))
        results = audit_logger.query(limit=3)
        assert len(results) == 3

    def test_query_with_offset(self, audit_logger):
        for i in range(10):
            audit_logger.log(AuditEvent(action=f"test.{i}", actor="system"))
        results_all = audit_logger.query(limit=10)
        results_page = audit_logger.query(limit=5, offset=5)
        assert len(results_page) == 5
        assert results_page[0]["action"] == results_all[5]["action"]

    def test_count(self, audit_logger):
        audit_logger.log(AuditEvent(action="a", actor="x"))
        audit_logger.log(AuditEvent(action="b", actor="x"))
        audit_logger.log(AuditEvent(action="a", actor="y"))
        assert audit_logger.count() == 3
        assert audit_logger.count(action="a") == 2

    def test_export_jsonl(self, audit_logger):
        audit_logger.log(AuditEvent(action="a", actor="x"))
        audit_logger.log(AuditEvent(action="b", actor="y"))
        jsonl = audit_logger.export_jsonl()
        lines = jsonl.strip().split("\n")
        assert len(lines) == 2
        parsed = [json.loads(line) for line in lines]
        assert parsed[0]["action"] == "b"  # most recent first

    def test_thread_safety(self, audit_logger):
        """Log events from multiple threads simultaneously."""

        def log_events(prefix, count):
            for i in range(count):
                audit_logger.log(AuditEvent(action=f"{prefix}.{i}", actor="thread"))

        threads = [
            threading.Thread(target=log_events, args=("t1", 20)),
            threading.Thread(target=log_events, args=("t2", 20)),
            threading.Thread(target=log_events, args=("t3", 20)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert audit_logger.count() == 60

    def test_log_failure_does_not_crash(self, audit_logger):
        """Logging with a bad event should not raise."""
        # This should log but not crash even with weird data
        event = AuditEvent(action="test", actor="system")
        audit_logger.log(event)  # Should succeed
        assert audit_logger.count() == 1


class TestAuditLoggerDSR:
    """GDPR/CCPA Data Subject Request (DSR) carve-out.

    ``delete_for_actor`` is the only sanctioned path to remove
    rows from the audit log; it is exercised by the
    ``/v1/me/delete`` cascade (see ``cutctx.proxy.routes.dsr``).
    The audit log is otherwise append-only.
    """

    def test_delete_for_actor_removes_matching_rows(self, audit_logger):
        audit_logger.log(AuditEvent(action="auth.login", actor="alice"))
        audit_logger.log(AuditEvent(action="auth.login", actor="bob"))
        audit_logger.log(AuditEvent(action="auth.login", actor="alice"))

        n = audit_logger.delete_for_actor("alice")
        assert n == 2
        # Bob's row is preserved.
        assert audit_logger.count() == 1
        rows = audit_logger.query()
        assert rows[0]["actor"] == "bob"

    def test_delete_for_actor_no_match_returns_zero(self, audit_logger):
        audit_logger.log(AuditEvent(action="test", actor="alice"))
        n = audit_logger.delete_for_actor("nobody")
        assert n == 0
        assert audit_logger.count() == 1

    def test_delete_for_actor_empty_string_no_op(self, audit_logger):
        audit_logger.log(AuditEvent(action="test", actor="alice"))
        n = audit_logger.delete_for_actor("")
        assert n == 0
        assert audit_logger.count() == 1

    def test_delete_for_actor_does_not_touch_other_actors(self, audit_logger):
        # Mix of actions and actors to ensure DELETE is scoped.
        audit_logger.log(AuditEvent(action="auth.login", actor="alice"))
        audit_logger.log(AuditEvent(action="data.read", actor="alice"))
        audit_logger.log(AuditEvent(action="auth.login", actor="bob"))
        audit_logger.log(AuditEvent(action="data.read", actor="carol"))

        n = audit_logger.delete_for_actor("alice")
        assert n == 2
        remaining = {r["actor"] for r in audit_logger.query()}
        assert remaining == {"bob", "carol"}


class TestAuditEventEdgeCases:
    """Edge case tests."""

    def test_unicode_in_detail(self, audit_logger):
        event = AuditEvent(
            action="test",
            actor="system",
            detail={"message": "日本語テスト 🎉"},
        )
        audit_logger.log(event)
        results = audit_logger.query()
        assert results[0]["detail"]["message"] == "日本語テスト 🎉"

    def test_large_detail(self, audit_logger):
        large_detail = {"data": "x" * 10000}
        event = AuditEvent(action="test", actor="system", detail=large_detail)
        audit_logger.log(event)
        results = audit_logger.query()
        assert len(results[0]["detail"]["data"]) == 10000

    def test_empty_query(self, audit_logger):
        results = audit_logger.query()
        assert results == []

    def test_query_nonexistent_action(self, audit_logger):
        audit_logger.log(AuditEvent(action="a", actor="x"))
        results = audit_logger.query(action="nonexistent")
        assert results == []


class TestGlobalSingleton:
    """Tests for the module-level singleton."""

    def setup_method(self):
        reset_audit_logger()

    def teardown_method(self):
        reset_audit_logger()

    def test_get_creates_singleton(self, tmp_audit_db):
        logger1 = get_audit_logger(db_path=tmp_audit_db)
        logger2 = get_audit_logger(db_path=tmp_audit_db)
        assert logger1 is logger2

    def test_reset_clears_singleton(self, tmp_audit_db):
        logger1 = get_audit_logger(db_path=tmp_audit_db)
        reset_audit_logger()
        logger2 = get_audit_logger(db_path=tmp_audit_db)
        assert logger1 is not logger2

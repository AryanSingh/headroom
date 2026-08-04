"""Tests for retention controls (cutctx/retention.py)."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from cutctx.retention import RetentionConfig, RetentionManager

# ---------------------------------------------------------------------------
# RetentionConfig
# ---------------------------------------------------------------------------


class TestRetentionConfig:
    def test_defaults(self):
        cfg = RetentionConfig()
        assert cfg.ccr_enabled is True
        assert cfg.ccr_max_age_seconds == 86400 * 7
        assert cfg.audit_enabled is True
        assert cfg.audit_max_age_days == 90
        assert cfg.spend_enabled is True
        assert cfg.spend_max_age_days == 365
        assert cfg.episodic_enabled is True
        assert cfg.episodic_max_age_days == 30
        assert cfg.cleanup_interval_seconds == 3600

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("CUTCTX_RETENTION_CCR_MAX_AGE_SECONDS", "3600")
        monkeypatch.setenv("CUTCTX_RETENTION_AUDIT_MAX_AGE_DAYS", "30")
        monkeypatch.setenv("CUTCTX_RETENTION_SPEND_MAX_AGE_DAYS", "180")
        monkeypatch.setenv("CUTCTX_RETENTION_EPISODIC_MAX_AGE_DAYS", "7")
        cfg = RetentionConfig.from_env()
        assert cfg.ccr_max_age_seconds == 3600
        assert cfg.audit_max_age_days == 30
        assert cfg.spend_max_age_days == 180
        assert cfg.episodic_max_age_days == 7

    def test_from_env_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("CUTCTX_RETENTION_CCR_MAX_AGE_SECONDS", "not_a_number")
        cfg = RetentionConfig.from_env()
        assert cfg.ccr_max_age_seconds == 86400 * 7  # default


# ---------------------------------------------------------------------------
# RetentionManager
# ---------------------------------------------------------------------------


class TestRetentionManager:
    def test_init_default(self):
        mgr = RetentionManager()
        assert mgr.enabled is True
        assert mgr._running is False

    def test_init_disabled(self):
        cfg = RetentionConfig(
            ccr_enabled=False,
            audit_enabled=False,
            spend_enabled=False,
            episodic_enabled=False,
        )
        mgr = RetentionManager(config=cfg)
        assert mgr.enabled is False

    def test_get_stats(self):
        mgr = RetentionManager()
        stats = mgr.get_stats()
        assert "ccr_deleted" in stats
        assert "audit_deleted" in stats
        assert "spend_deleted" in stats
        assert "episodic_deleted" in stats
        assert "config" in stats
        assert stats["cleanup_count"] == 0

    @pytest.mark.asyncio
    async def test_run_cleanup_all_disabled(self):
        cfg = RetentionConfig(
            ccr_enabled=False,
            audit_enabled=False,
            spend_enabled=False,
            episodic_enabled=False,
        )
        mgr = RetentionManager(config=cfg)
        results = await mgr.run_cleanup()
        assert results == {
            "ccr_deleted": 0,
            "audit_deleted": 0,
            "spend_deleted": 0,
            "episodic_deleted": 0,
        }

    @pytest.mark.asyncio
    async def test_run_cleanup_records_stats(self):
        cfg = RetentionConfig(
            ccr_enabled=False,
            audit_enabled=False,
            spend_enabled=False,
            episodic_enabled=False,
        )
        mgr = RetentionManager(config=cfg)
        await mgr.run_cleanup()
        stats = mgr.get_stats()
        assert stats["cleanup_count"] == 1
        assert stats["last_cleanup"] is not None

    def test_cleanup_audit_removes_old_entries(self, monkeypatch):
        """Test audit cleanup with a real SQLite DB via env var."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            # Use DELETE journal mode to avoid WAL locking issues in tests
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("""
                CREATE TABLE audit_events (
                    id TEXT PRIMARY KEY,
                    action TEXT,
                    actor TEXT,
                    detail TEXT,
                    timestamp REAL,
                    success INTEGER,
                    ip_address TEXT,
                    user_agent TEXT
                )
            """)
            old_time = time.time() - (100 * 86400)  # 100 days ago
            new_time = time.time() - (10 * 86400)  # 10 days ago
            conn.execute(
                "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("old1", "test", "user", "{}", old_time, 1, None, None),
            )
            conn.execute(
                "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("new1", "test", "user", "{}", new_time, 1, None, None),
            )
            conn.commit()
            conn.close()

            monkeypatch.setenv("CUTCTX_AUDIT_DB_PATH", str(db_path))
            cfg = RetentionConfig(
                ccr_enabled=False,
                audit_enabled=True,
                audit_max_age_days=90,
                episodic_enabled=False,
            )
            mgr = RetentionManager(config=cfg)
            deleted = mgr._cleanup_audit_log()
            assert deleted == 1

    def test_cleanup_audit_deletes_iso_timestamp_rows(self, tmp_path, monkeypatch):
        """H7 regression: production schema stores ``timestamp`` as ISO-8601 TEXT.

        The cleanup used to bind a float epoch cutoff against that TEXT column.
        SQLite sorts every numeric value before every text value, so the DELETE
        matched nothing while ``run_cleanup`` still reported success with
        ``errors: 0``. This test builds the *real* audit schema (see
        ``cutctx_ee/audit/__init__.py::_ensure_schema``) and asserts old rows
        actually go away.
        """
        from cutctx_ee.audit import AuditEvent, AuditLogger

        db_path = tmp_path / "audit-iso.db"
        monkeypatch.setenv("CUTCTX_AUDIT_DB_PATH", str(db_path))
        audit = AuditLogger(db_path=str(db_path))
        old_iso = datetime.fromtimestamp(
            time.time() - (100 * 86400), timezone.utc
        ).isoformat()
        recent_iso = datetime.fromtimestamp(
            time.time() - (10 * 86400), timezone.utc
        ).isoformat()
        audit.log(AuditEvent(action="test", actor="user", timestamp=old_iso, event_id="old1"))
        audit.log(AuditEvent(action="test", actor="user", timestamp=recent_iso, event_id="new1"))
        audit.close()

        # Sanity-check we really are exercising the TEXT column, not REAL.
        probe = sqlite3.connect(str(db_path))
        try:
            types = {
                row[0] for row in probe.execute("SELECT typeof(timestamp) FROM audit_events")
            }
        finally:
            probe.close()
        assert types == {"text"}, f"expected ISO TEXT timestamps, got {types}"

        manager = RetentionManager(
            RetentionConfig(
                ccr_enabled=False,
                audit_enabled=True,
                audit_max_age_days=90,
                spend_enabled=False,
                episodic_enabled=False,
            )
        )
        assert manager._cleanup_audit_log() == 1

        remaining = sqlite3.connect(str(db_path))
        try:
            ids = [row[0] for row in remaining.execute("SELECT event_id FROM audit_events")]
        finally:
            remaining.close()
        assert ids == ["new1"]

    def test_cleanup_audit_handles_mixed_epoch_and_iso_rows(self, tmp_path, monkeypatch):
        """H7: legacy rows that stored a numeric epoch must still be collected."""
        db_path = tmp_path / "audit-mixed.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE audit_events (event_id TEXT PRIMARY KEY, timestamp)")
        old_epoch = time.time() - (100 * 86400)
        old_iso = datetime.fromtimestamp(old_epoch, timezone.utc).isoformat()
        recent_epoch = time.time() - (10 * 86400)
        recent_iso = datetime.fromtimestamp(recent_epoch, timezone.utc).isoformat()
        conn.executemany(
            "INSERT INTO audit_events VALUES (?, ?)",
            [
                ("old-epoch", old_epoch),
                ("old-iso", old_iso),
                ("new-epoch", recent_epoch),
                ("new-iso", recent_iso),
            ],
        )
        conn.commit()
        conn.close()

        monkeypatch.setenv("CUTCTX_AUDIT_DB_PATH", str(db_path))
        manager = RetentionManager(
            RetentionConfig(
                ccr_enabled=False,
                audit_enabled=True,
                audit_max_age_days=90,
                spend_enabled=False,
                episodic_enabled=False,
            )
        )
        assert manager._cleanup_audit_log() == 2

        remaining = sqlite3.connect(str(db_path))
        try:
            ids = sorted(row[0] for row in remaining.execute("SELECT event_id FROM audit_events"))
        finally:
            remaining.close()
        assert ids == ["new-epoch", "new-iso"]

    @pytest.mark.asyncio
    async def test_run_cleanup_reports_failures_instead_of_silent_success(self, monkeypatch):
        """H7: a cleanup task that raises must bump ``errors``, not report success."""
        manager = RetentionManager(
            RetentionConfig(
                ccr_enabled=False,
                audit_enabled=True,
                spend_enabled=False,
                episodic_enabled=False,
            )
        )

        def _boom(*_args, **_kwargs):
            raise sqlite3.OperationalError("disk I/O error")

        monkeypatch.setattr(sqlite3, "connect", _boom)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        await manager.run_cleanup()
        stats = manager.get_stats()
        assert stats["errors"] == 1
        assert stats["failed_categories"] == {"audit": 1}

    def test_cleanup_audit_bulk_delete_vacuums_after_commit(self, tmp_path, monkeypatch):
        # NOTE: this fixture declares ``timestamp REAL``, which is NOT the
        # production schema (that column is TEXT/ISO-8601). It is retained
        # because it now legitimately covers the numeric-epoch branch of the
        # H7 fix; the ISO coverage lives in
        # ``test_cleanup_audit_deletes_iso_timestamp_rows`` above.
        db_path = tmp_path / "audit-bulk.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE audit_events (id TEXT PRIMARY KEY, timestamp REAL)")
        old_time = time.time() - (100 * 86400)
        conn.executemany(
            "INSERT INTO audit_events VALUES (?, ?)",
            [(f"old-{index}", old_time) for index in range(101)],
        )
        conn.commit()
        conn.close()

        monkeypatch.setenv("CUTCTX_AUDIT_DB_PATH", str(db_path))
        manager = RetentionManager(
            RetentionConfig(
                ccr_enabled=False,
                audit_enabled=True,
                audit_max_age_days=90,
                spend_enabled=False,
                episodic_enabled=False,
            )
        )

        assert manager._cleanup_audit_log() == 101

    def test_cleanup_spend_removes_old_entries(self, tmp_path, monkeypatch):
        from cutctx_ee.ledger.store import LedgerStore

        db_path = tmp_path / "spend.db"
        db_url = f"sqlite:///{db_path}"
        store = LedgerStore(db_url=db_url)
        now = int(time.time())
        store.insert_events(
            [
                {
                    "ts": now - (400 * 86400),
                    "auth_mode": "api_key",
                    "request_id": "old-request",
                },
                {
                    "ts": now - (10 * 86400),
                    "auth_mode": "api_key",
                    "request_id": "new-request",
                },
            ]
        )
        monkeypatch.setenv("CUTCTX_SPEND_DB_URL", db_url)
        manager = RetentionManager(
            RetentionConfig(
                ccr_enabled=False,
                audit_enabled=False,
                spend_enabled=True,
                spend_max_age_days=365,
                episodic_enabled=False,
            )
        )

        assert manager._cleanup_spend_ledger() == 1
        with store.SessionLocal() as session:
            from cutctx_ee.ledger.models import SpendEvent

            assert [event.request_id for event in session.query(SpendEvent).all()] == [
                "new-request"
            ]

    def test_cleanup_episodic_removes_old_files(self):
        """Test episodic memory cleanup with real files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memories_dir = Path(tmpdir) / ".cutctx" / "memories"
            memories_dir.mkdir(parents=True)
            # Create old file (set mtime to 100 days ago)
            old_file = memories_dir / "old.md"
            old_file.write_text("old content")
            old_time = time.time() - 100 * 86400
            os.utime(old_file, (old_time, old_time))
            # Create new file
            new_file = memories_dir / "new.md"
            new_file.write_text("new content")

            cfg = RetentionConfig(
                ccr_enabled=False,
                audit_enabled=False,
                episodic_enabled=True,
                episodic_max_age_days=30,
            )
            mgr = RetentionManager(config=cfg)
            # Patch Path.home to return our tmpdir
            with patch("cutctx.retention.Path") as MockPath:
                MockPath.home.return_value = Path(tmpdir)
                deleted = mgr._cleanup_episodic_memories()
                assert deleted == 1
                assert not old_file.exists()
                assert new_file.exists()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestGlobalSingleton:
    def test_get_creates_default(self):
        from cutctx.retention import get_retention_manager, reset_retention_manager

        reset_retention_manager()
        mgr = get_retention_manager()
        assert isinstance(mgr, RetentionManager)
        reset_retention_manager()

    def test_reset_clears(self):
        from cutctx.retention import get_retention_manager, reset_retention_manager

        reset_retention_manager()
        mgr1 = get_retention_manager()
        reset_retention_manager()
        mgr2 = get_retention_manager()
        assert mgr1 is not mgr2
        reset_retention_manager()

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

import cutctx_ee.retention as retention_module
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

    def test_from_env_reads_audit_path_and_dry_run(self, monkeypatch, tmp_path):
        audit_path = tmp_path / "audit.db"
        monkeypatch.setenv("CUTCTX_RETENTION_AUDIT_DB_PATH", str(audit_path))
        monkeypatch.setenv("CUTCTX_RETENTION_DRY_RUN", "true")

        cfg = RetentionConfig.from_env()

        assert cfg.audit_db_path == str(audit_path)
        assert cfg.dry_run is True


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

    def test_resolve_audit_db_path_explicit_config_wins_over_both_envs(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CUTCTX_RETENTION_AUDIT_DB_PATH", str(tmp_path / "retention.db"))
        monkeypatch.setenv("CUTCTX_AUDIT_DB_PATH", str(tmp_path / "canonical.db"))
        manager = RetentionManager(RetentionConfig(audit_db_path="~/explicit.db"))

        assert manager.resolve_audit_db_path() == Path.home() / "explicit.db"

    def test_resolve_audit_db_path_retention_env_wins_over_canonical_env(
        self, monkeypatch, tmp_path
    ):
        retention_path = tmp_path / "retention.db"
        monkeypatch.setenv("CUTCTX_RETENTION_AUDIT_DB_PATH", str(retention_path))
        monkeypatch.setenv("CUTCTX_AUDIT_DB_PATH", str(tmp_path / "canonical.db"))

        assert RetentionManager().resolve_audit_db_path() == retention_path

    def test_resolve_audit_db_path_uses_canonical_audit_env(self, monkeypatch, tmp_path):
        canonical_path = tmp_path / "canonical.db"
        monkeypatch.delenv("CUTCTX_RETENTION_AUDIT_DB_PATH", raising=False)
        monkeypatch.setenv("CUTCTX_AUDIT_DB_PATH", str(canonical_path))

        assert RetentionManager().resolve_audit_db_path() == canonical_path

    def test_resolve_audit_db_path_uses_documented_home_default(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CUTCTX_RETENTION_AUDIT_DB_PATH", raising=False)
        monkeypatch.delenv("CUTCTX_AUDIT_DB_PATH", raising=False)
        monkeypatch.setattr(retention_module.Path, "home", lambda: tmp_path)

        manager = RetentionManager()

        assert manager.resolve_audit_db_path() == tmp_path / ".cutctx" / "audit.db"
        assert manager.get_stats()["audit_db_path"] == str(tmp_path / ".cutctx" / "audit.db")

    def test_get_stats_exposes_dry_run_and_resolved_audit_path(self, tmp_path):
        manager = RetentionManager(
            RetentionConfig(dry_run=True, audit_db_path=str(tmp_path / "audit.db"))
        )

        stats = manager.get_stats()

        assert stats["dry_run"] is True
        assert stats["audit_db_path"] == str(tmp_path / "audit.db")

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
        old_iso = datetime.fromtimestamp(time.time() - (100 * 86400), timezone.utc).isoformat()
        recent_iso = datetime.fromtimestamp(time.time() - (10 * 86400), timezone.utc).isoformat()
        audit.log(AuditEvent(action="test", actor="user", timestamp=old_iso, event_id="old1"))
        audit.log(AuditEvent(action="test", actor="user", timestamp=recent_iso, event_id="new1"))
        audit.close()

        # Sanity-check we really are exercising the TEXT column, not REAL.
        probe = sqlite3.connect(str(db_path))
        try:
            types = {row[0] for row in probe.execute("SELECT typeof(timestamp) FROM audit_events")}
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

    def test_audit_dry_run_counts_old_rows_without_mutation(self, tmp_path):
        db_path = tmp_path / "audit-preview.db"
        now = time.time()
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE audit_events (event_id TEXT PRIMARY KEY, timestamp)")
        conn.executemany(
            "INSERT INTO audit_events VALUES (?, ?)",
            [
                ("old", datetime.fromtimestamp(now - 100 * 86400, timezone.utc).isoformat()),
                ("new", datetime.fromtimestamp(now - 10 * 86400, timezone.utc).isoformat()),
            ],
        )
        conn.commit()
        conn.close()

        manager = RetentionManager(
            RetentionConfig(
                dry_run=True,
                audit_db_path=str(db_path),
                audit_max_age_days=90,
                ccr_enabled=False,
                spend_enabled=False,
                episodic_enabled=False,
            )
        )

        assert manager._cleanup_audit_log() == 1
        with sqlite3.connect(db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 2

    def test_audit_mixed_timestamp_types_keep_unrecognized_text(self, tmp_path):
        db_path = tmp_path / "audit-types.db"
        now = time.time()
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE audit_events (event_id TEXT PRIMARY KEY, timestamp)")
        rows = [
            ("old-integer", int(now - 100 * 86400)),
            ("old-real", now - 100 * 86400),
            ("old-numeric-text", str(now - 100 * 86400)),
            ("old-iso", datetime.fromtimestamp(now - 100 * 86400, timezone.utc).isoformat()),
            ("recent-integer", int(now - 10 * 86400)),
            ("recent-real", now - 10 * 86400),
            ("recent-numeric-text", str(now - 10 * 86400)),
            ("recent-iso", datetime.fromtimestamp(now - 10 * 86400, timezone.utc).isoformat()),
            ("future-numeric-text", "9999999999"),
            ("malformed-multi-dot", "1.2.3"),
            ("signed-text", "-123"),
            ("scientific-text", "1e9"),
            ("whitespace-text", " 123 "),
            ("offset-iso", "2026-01-01T00:00:00+05:30"),
            ("null-value", None),
        ]
        conn.executemany("INSERT INTO audit_events VALUES (?, ?)", rows)
        conn.commit()
        conn.close()

        manager = RetentionManager(
            RetentionConfig(
                audit_db_path=str(db_path),
                audit_max_age_days=90,
                ccr_enabled=False,
                spend_enabled=False,
                episodic_enabled=False,
            )
        )

        assert manager._cleanup_audit_log() == 4
        with sqlite3.connect(db_path) as conn:
            remaining = {row[0] for row in conn.execute("SELECT event_id FROM audit_events")}
        assert remaining == {row[0] for row in rows[4:]}

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

    def test_spend_dry_run_counts_without_deleting(self, tmp_path, monkeypatch):
        from cutctx_ee.ledger.store import LedgerStore

        db_url = f"sqlite:///{tmp_path / 'spend-preview.db'}"
        store = LedgerStore(db_url=db_url)
        now = int(time.time())
        store.insert_events(
            [
                {"ts": now - 400 * 86400, "auth_mode": "api_key", "request_id": "old"},
                {"ts": now - 10 * 86400, "auth_mode": "api_key", "request_id": "new"},
            ]
        )
        monkeypatch.setenv("CUTCTX_SPEND_DB_URL", db_url)
        manager = RetentionManager(
            RetentionConfig(
                dry_run=True,
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

            assert session.query(SpendEvent).count() == 2

    def test_episodic_dry_run_counts_without_unlinking(self, tmp_path, monkeypatch):
        memories_dir = tmp_path / ".cutctx" / "memories"
        memories_dir.mkdir(parents=True)
        old_file = memories_dir / "old.md"
        old_file.write_text("old content")
        old_time = time.time() - 100 * 86400
        os.utime(old_file, (old_time, old_time))
        new_file = memories_dir / "new.md"
        new_file.write_text("new content")
        monkeypatch.setattr(retention_module.Path, "home", lambda: tmp_path)

        manager = RetentionManager(
            RetentionConfig(
                dry_run=True,
                ccr_enabled=False,
                audit_enabled=False,
                spend_enabled=False,
                episodic_enabled=True,
                episodic_max_age_days=30,
            )
        )

        assert manager._cleanup_episodic_memories() == 1
        assert old_file.exists()
        assert new_file.exists()

    def test_ccr_dry_run_never_calls_mutating_store_methods(self, monkeypatch):
        class FakeStore:
            def preview_cleanup(self, **_kwargs):
                raise AssertionError("preview cleanup must use a non-mutating API")

            def cleanup_expired(self, **_kwargs):
                raise AssertionError("cleanup_expired must not run in dry-run")

            def truncate(self, **_kwargs):
                raise AssertionError("truncate must not run in dry-run")

        monkeypatch.setattr(
            "cutctx.cache.compression_store.get_compression_store", lambda: FakeStore()
        )
        manager = RetentionManager(
            RetentionConfig(
                dry_run=True, audit_enabled=False, spend_enabled=False, episodic_enabled=False
            )
        )

        assert manager._cleanup_ccr_entries() == 0

    def test_ccr_real_store_preview_is_read_only_and_normal_cleanup_matches(self, monkeypatch):
        from cutctx.cache.compression_store import CompressionStore

        store = CompressionStore(max_entries=10)
        for index in range(3):
            store.store(f"original-{index}", f"compressed-{index}")
        monkeypatch.setattr("cutctx.cache.compression_store.get_compression_store", lambda: store)
        manager = RetentionManager(
            RetentionConfig(
                dry_run=True,
                ccr_max_age_seconds=3600,
                ccr_max_entries=2,
                audit_enabled=False,
                spend_enabled=False,
                episodic_enabled=False,
            )
        )

        assert manager._cleanup_ccr_entries() == 1
        assert store.get_stats()["entry_count"] == 3

        manager.config.dry_run = False
        assert manager._cleanup_ccr_entries() == 1
        assert store.get_stats()["entry_count"] == 2

    def test_ccr_cleanup_counts_expired_and_over_limit_union_once(self):
        from cutctx.cache.compression_store import CompressionStore

        store = CompressionStore(max_entries=10)
        created = time.time()
        with patch("cutctx.cache.compression_store.time.time", return_value=created - 100):
            store.store("expired", "expired", ttl=3600)
        store.store("active-1", "active-1", ttl=3600)
        store.store("active-2", "active-2", ttl=3600)
        store.store("active-3", "active-3", ttl=3600)

        assert store.preview_cleanup(max_age_seconds=1, max_entries=2) == 2
        assert store.get_stats()["entry_count"] == 4
        assert store.cleanup_retention(max_age_seconds=1, max_entries=2) == 2
        assert store.get_stats()["entry_count"] == 2

    @pytest.mark.asyncio
    async def test_run_cleanup_dry_run_counts_candidates_without_incrementing_stats(
        self, monkeypatch, tmp_path
    ):
        manager = RetentionManager(
            RetentionConfig(
                dry_run=True,
                audit_db_path=str(tmp_path / "audit.db"),
                ccr_enabled=True,
                audit_enabled=True,
                spend_enabled=True,
                episodic_enabled=True,
            )
        )
        monkeypatch.setattr(manager, "_cleanup_ccr_entries", lambda: 1)
        monkeypatch.setattr(manager, "_cleanup_audit_log", lambda: 2)
        monkeypatch.setattr(manager, "_cleanup_spend_ledger", lambda: 3)
        monkeypatch.setattr(manager, "_cleanup_episodic_memories", lambda: 4)

        result = await manager.run_cleanup()

        assert result == {
            "ccr_deleted": 1,
            "audit_deleted": 2,
            "spend_deleted": 3,
            "episodic_deleted": 4,
        }
        stats = manager.get_stats()
        assert stats["ccr_deleted"] == 0
        assert stats["audit_deleted"] == 0
        assert stats["spend_deleted"] == 0
        assert stats["episodic_deleted"] == 0
        assert stats["dry_run"] is True
        assert stats["audit_db_path"] == str(tmp_path / "audit.db")

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

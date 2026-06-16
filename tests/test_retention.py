"""Tests for retention controls (headroom/retention.py)."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from headroom.retention import RetentionConfig, RetentionManager

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
        assert cfg.episodic_enabled is True
        assert cfg.episodic_max_age_days == 30
        assert cfg.cleanup_interval_seconds == 3600

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("HEADROOM_RETENTION_CCR_MAX_AGE_SECONDS", "3600")
        monkeypatch.setenv("HEADROOM_RETENTION_AUDIT_MAX_AGE_DAYS", "30")
        monkeypatch.setenv("HEADROOM_RETENTION_EPISODIC_MAX_AGE_DAYS", "7")
        cfg = RetentionConfig.from_env()
        assert cfg.ccr_max_age_seconds == 3600
        assert cfg.audit_max_age_days == 30
        assert cfg.episodic_max_age_days == 7

    def test_from_env_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("HEADROOM_RETENTION_CCR_MAX_AGE_SECONDS", "not_a_number")
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
        cfg = RetentionConfig(ccr_enabled=False, audit_enabled=False, episodic_enabled=False)
        mgr = RetentionManager(config=cfg)
        assert mgr.enabled is False

    def test_get_stats(self):
        mgr = RetentionManager()
        stats = mgr.get_stats()
        assert "ccr_deleted" in stats
        assert "audit_deleted" in stats
        assert "episodic_deleted" in stats
        assert "config" in stats
        assert stats["cleanup_count"] == 0

    @pytest.mark.asyncio
    async def test_run_cleanup_all_disabled(self):
        cfg = RetentionConfig(ccr_enabled=False, audit_enabled=False, episodic_enabled=False)
        mgr = RetentionManager(config=cfg)
        results = await mgr.run_cleanup()
        assert results == {"ccr_deleted": 0, "audit_deleted": 0, "episodic_deleted": 0}

    @pytest.mark.asyncio
    async def test_run_cleanup_records_stats(self):
        cfg = RetentionConfig(ccr_enabled=False, audit_enabled=False, episodic_enabled=False)
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

            monkeypatch.setenv("HEADROOM_AUDIT_DB_PATH", str(db_path))
            cfg = RetentionConfig(
                ccr_enabled=False,
                audit_enabled=True,
                audit_max_age_days=90,
                episodic_enabled=False,
            )
            mgr = RetentionManager(config=cfg)
            deleted = mgr._cleanup_audit_log()
            assert deleted == 1

    def test_cleanup_episodic_removes_old_files(self):
        """Test episodic memory cleanup with real files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memories_dir = Path(tmpdir) / ".headroom" / "memories"
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
            with patch("headroom.retention.Path") as MockPath:
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
        from headroom.retention import get_retention_manager, reset_retention_manager

        reset_retention_manager()
        mgr = get_retention_manager()
        assert isinstance(mgr, RetentionManager)
        reset_retention_manager()

    def test_reset_clears(self):
        from headroom.retention import get_retention_manager, reset_retention_manager

        reset_retention_manager()
        mgr1 = get_retention_manager()
        reset_retention_manager()
        mgr2 = get_retention_manager()
        assert mgr1 is not mgr2
        reset_retention_manager()

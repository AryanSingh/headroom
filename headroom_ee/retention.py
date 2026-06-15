# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Retention controls for enterprise compliance.

Provides automatic expiry and cleanup for stored data:
- CCR compression entries (TTL-based)
- Audit log rotation (age-based)
- Episodic memory expiry
- SQLite WAL checkpointing

Enterprise feature — gated on entitlement_tier >= TEAM.

Usage:
    from headroom.retention import RetentionManager

    manager = RetentionManager(config=RetentionConfig())
    await manager.start()
    # ... later ...
    await manager.run_cleanup()
    await manager.stop()
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("headroom.retention")


@dataclass
class RetentionConfig:
    """Configuration for data retention policies."""

    # CCR compression store
    ccr_enabled: bool = True
    ccr_max_age_seconds: int = 86400 * 7  # 7 days
    ccr_max_entries: int = 10000

    # Audit log
    audit_enabled: bool = True
    audit_max_age_days: int = 90  # 90 days
    audit_max_db_size_mb: int = 500  # 500MB
    audit_checkpoint_interval: int = 3600  # WAL checkpoint every hour

    # Episodic memory
    episodic_enabled: bool = True
    episodic_max_age_days: int = 30  # 30 days

    # Cleanup schedule
    cleanup_interval_seconds: int = 3600  # Run cleanup every hour
    cleanup_batch_size: int = 100  # Rows per batch delete

    @classmethod
    def from_env(cls) -> RetentionConfig:
        """Create config from environment variables."""
        return cls(
            ccr_enabled=_get_bool("HEADROOM_RETENTION_CCR_ENABLED", True),
            ccr_max_age_seconds=_get_int("HEADROOM_RETENTION_CCR_MAX_AGE_SECONDS", 86400 * 7),
            ccr_max_entries=_get_int("HEADROOM_RETENTION_CCR_MAX_ENTRIES", 10000),
            audit_enabled=_get_bool("HEADROOM_RETENTION_AUDIT_ENABLED", True),
            audit_max_age_days=_get_int("HEADROOM_RETENTION_AUDIT_MAX_AGE_DAYS", 90),
            audit_max_db_size_mb=_get_int("HEADROOM_RETENTION_AUDIT_MAX_DB_MB", 500),
            audit_checkpoint_interval=_get_int(
                "HEADROOM_RETENTION_AUDIT_CHECKPOINT_INTERVAL", 3600
            ),
            episodic_enabled=_get_bool("HEADROOM_RETENTION_EPISODIC_ENABLED", True),
            episodic_max_age_days=_get_int("HEADROOM_RETENTION_EPISODIC_MAX_AGE_DAYS", 30),
            cleanup_interval_seconds=_get_int("HEADROOM_RETENTION_CLEANUP_INTERVAL", 3600),
            cleanup_batch_size=_get_int("HEADROOM_RETENTION_CLEANUP_BATCH_SIZE", 100),
        )


class RetentionManager:
    """Manages data retention policies and cleanup.

    Runs periodic cleanup tasks to enforce retention policies across
    all storage backends (CCR, audit, episodic memory).
    """

    def __init__(self, config: RetentionConfig | None = None):
        self.config = config or RetentionConfig()
        self._task: asyncio.Task | None = None
        self._running = False
        self._stats = {
            "ccr_deleted": 0,
            "audit_deleted": 0,
            "episodic_deleted": 0,
            "last_cleanup": None,
            "cleanup_count": 0,
            "errors": 0,
        }

    @property
    def enabled(self) -> bool:
        """Check if any retention policy is enabled."""
        return self.config.ccr_enabled or self.config.audit_enabled or self.config.episodic_enabled

    async def start(self) -> None:
        """Start the background cleanup task."""
        if not self.enabled:
            logger.debug("Retention controls disabled")
            return
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            "Retention manager started (interval=%ds, ccr=%s, audit=%s, episodic=%s)",
            self.config.cleanup_interval_seconds,
            self.config.ccr_enabled,
            self.config.audit_enabled,
            self.config.episodic_enabled,
        )

    async def stop(self) -> None:
        """Stop the background cleanup task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Retention manager stopped")

    def get_stats(self) -> dict[str, Any]:
        """Return retention manager statistics."""
        return {
            **self._stats,
            "config": {
                "ccr_max_age_seconds": self.config.ccr_max_age_seconds,
                "ccr_max_entries": self.config.ccr_max_entries,
                "audit_max_age_days": self.config.audit_max_age_days,
                "audit_max_db_size_mb": self.config.audit_max_db_size_mb,
                "episodic_max_age_days": self.config.episodic_max_age_days,
                "cleanup_interval_seconds": self.config.cleanup_interval_seconds,
            },
        }

    async def _cleanup_loop(self) -> None:
        """Background loop that runs cleanup periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval_seconds)
                await self.run_cleanup()
            except asyncio.CancelledError:
                break
            except Exception:
                self._stats["errors"] += 1
                logger.warning("Retention cleanup failed", exc_info=True)

    async def run_cleanup(self) -> dict[str, int]:
        """Run all retention cleanup tasks.

        Returns dict of cleanup counts per category.
        """
        results = {"ccr_deleted": 0, "audit_deleted": 0, "episodic_deleted": 0}

        if self.config.ccr_enabled:
            results["ccr_deleted"] = await asyncio.to_thread(self._cleanup_ccr_entries)

        if self.config.audit_enabled:
            results["audit_deleted"] = await asyncio.to_thread(self._cleanup_audit_log)

        if self.config.episodic_enabled:
            results["episodic_deleted"] = await asyncio.to_thread(self._cleanup_episodic_memories)

        self._stats["ccr_deleted"] += results["ccr_deleted"]
        self._stats["audit_deleted"] += results["audit_deleted"]
        self._stats["episodic_deleted"] += results["episodic_deleted"]
        self._stats["last_cleanup"] = time.time()
        self._stats["cleanup_count"] += 1

        total = sum(results.values())
        if total > 0:
            logger.info(
                "Retention cleanup: ccr=%d, audit=%d, episodic=%d",
                results["ccr_deleted"],
                results["audit_deleted"],
                results["episodic_deleted"],
            )

        return results

    def _cleanup_ccr_entries(self) -> int:
        """Remove expired CCR entries from the compression store."""
        try:
            from headroom.cache.compression_store import get_compression_store

            store = get_compression_store()
            deleted = store.cleanup_expired(max_age_seconds=self.config.ccr_max_age_seconds)
            # Also enforce max entries limit
            store.truncate(max_entries=self.config.ccr_max_entries)
            return deleted
        except Exception:
            logger.debug("CCR cleanup failed", exc_info=True)
            return 0

    def _cleanup_audit_log(self) -> int:
        """Remove old audit log entries and checkpoint WAL."""
        db_path = (
            Path(os.environ.get("HEADROOM_AUDIT_DB_PATH", ""))
            if os.environ.get("HEADROOM_AUDIT_DB_PATH")
            else Path.home() / ".headroom" / "audit.db"
        )
        if not db_path.exists():
            return 0

        try:
            # Check DB size limit
            db_size_mb = db_path.stat().st_size / (1024 * 1024)
            if db_size_mb > self.config.audit_max_db_size_mb:
                logger.warning(
                    "Audit DB exceeds size limit: %.1fMB > %dMB",
                    db_size_mb,
                    self.config.audit_max_db_size_mb,
                )

            conn = sqlite3.connect(str(db_path))
            try:
                # Delete old entries
                cutoff = time.time() - (self.config.audit_max_age_days * 86400)
                cursor = conn.execute(
                    "DELETE FROM audit_events WHERE timestamp < ?",
                    (cutoff,),
                )
                deleted = cursor.rowcount

                # VACUUM if significant deletion
                if deleted > 100:
                    conn.execute("VACUUM")

                # WAL checkpoint (may fail if journal mode is DELETE)
                try:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except sqlite3.OperationalError:
                    pass  # Not in WAL mode, skip checkpoint

                conn.commit()
                return deleted
            finally:
                conn.close()
        except Exception:
            logger.debug("Audit cleanup failed", exc_info=True)
            return 0

    def _cleanup_episodic_memories(self) -> int:
        """Remove old episodic memory files."""
        try:
            memories_dir = Path.home() / ".headroom" / "memories"
            if not memories_dir.exists():
                return 0

            deleted = 0
            cutoff = time.time() - (self.config.episodic_max_age_days * 86400)

            for md_file in memories_dir.glob("*.md"):
                try:
                    if md_file.stat().st_mtime < cutoff:
                        md_file.unlink()
                        deleted += 1
                except OSError:
                    continue

            return deleted
        except Exception:
            logger.debug("Episodic memory cleanup failed", exc_info=True)
            return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key, "").strip().lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return default


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


# Module-level singleton
_retention_manager: RetentionManager | None = None


def get_retention_manager() -> RetentionManager:
    """Get or create the global retention manager."""
    global _retention_manager  # noqa: PLW0603
    if _retention_manager is None:
        _retention_manager = RetentionManager(RetentionConfig.from_env())
    return _retention_manager


def reset_retention_manager() -> None:
    """Reset the global retention manager (for testing)."""
    global _retention_manager  # noqa: PLW0603
    _retention_manager = None

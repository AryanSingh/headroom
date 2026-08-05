# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Retention controls for enterprise compliance.

Provides automatic expiry and cleanup for stored data:
- CCR compression entries (TTL-based)
- Audit log rotation (age-based)
- Spend ledger rotation (age-based)
- Episodic memory expiry
- SQLite WAL checkpointing

Enterprise feature — gated on entitlement_tier >= TEAM.

Usage:
    from cutctx.retention import RetentionManager

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
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any

logger = logging.getLogger("cutctx.retention")

_STRICT_NUMERIC_TEXT = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
_CANONICAL_UTC_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?\+00:00$")


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
    # Explicit audit DB path. Empty means "resolve from the retention-specific
    # or canonical audit env var, else the documented user-level default".
    audit_db_path: str = ""

    # Global preview switch. When true every cleanup task COUNTS what it would
    # remove and removes nothing. Deletion is irreversible and previously the
    # only way to find out what a policy would do was to let it run — during
    # audit verification that permanently destroyed 19,861 real audit rows.
    dry_run: bool = False

    # Spend ledger
    spend_enabled: bool = True
    spend_max_age_days: int = 365  # 1 year by default

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
            ccr_enabled=_get_bool("CUTCTX_RETENTION_CCR_ENABLED", True),
            ccr_max_age_seconds=_get_int("CUTCTX_RETENTION_CCR_MAX_AGE_SECONDS", 86400 * 7),
            ccr_max_entries=_get_int("CUTCTX_RETENTION_CCR_MAX_ENTRIES", 10000),
            audit_enabled=_get_bool("CUTCTX_RETENTION_AUDIT_ENABLED", True),
            audit_max_age_days=_get_int("CUTCTX_RETENTION_AUDIT_MAX_AGE_DAYS", 90),
            audit_max_db_size_mb=_get_int("CUTCTX_RETENTION_AUDIT_MAX_DB_MB", 500),
            audit_checkpoint_interval=_get_int("CUTCTX_RETENTION_AUDIT_CHECKPOINT_INTERVAL", 3600),
            audit_db_path=os.environ.get("CUTCTX_RETENTION_AUDIT_DB_PATH", ""),
            dry_run=_get_bool("CUTCTX_RETENTION_DRY_RUN", False),
            spend_enabled=_get_bool("CUTCTX_RETENTION_SPEND_ENABLED", True),
            spend_max_age_days=_get_int("CUTCTX_RETENTION_SPEND_MAX_AGE_DAYS", 365),
            episodic_enabled=_get_bool("CUTCTX_RETENTION_EPISODIC_ENABLED", True),
            episodic_max_age_days=_get_int("CUTCTX_RETENTION_EPISODIC_MAX_AGE_DAYS", 30),
            cleanup_interval_seconds=_get_int("CUTCTX_RETENTION_CLEANUP_INTERVAL", 3600),
            cleanup_batch_size=_get_int("CUTCTX_RETENTION_CLEANUP_BATCH_SIZE", 100),
        )


class RetentionManager:
    """Manages data retention policies and cleanup.

    Runs periodic cleanup tasks to enforce retention policies across
    all storage backends (CCR, audit, spend ledger, episodic memory).
    """

    def __init__(self, config: RetentionConfig | None = None):
        self.config = config or RetentionConfig()
        self._task: asyncio.Task | None = None
        self._running = False
        self._stats = {
            "ccr_deleted": 0,
            "audit_deleted": 0,
            "spend_deleted": 0,
            "episodic_deleted": 0,
            "last_cleanup": None,
            "cleanup_count": 0,
            "errors": 0,
            # Per-category failure counters. Without these a cleanup whose
            # every task raised still reported ``errors: 0`` and four zero
            # deletion counts, which is indistinguishable from "nothing to do".
            "failed_categories": {},
        }

    def _record_failure(self, category: str) -> None:
        """Record that a cleanup category raised, so stats stop lying."""
        self._stats["errors"] += 1
        failures = self._stats["failed_categories"]
        failures[category] = failures.get(category, 0) + 1

    @property
    def enabled(self) -> bool:
        """Check if any retention policy is enabled."""
        return (
            self.config.ccr_enabled
            or self.config.audit_enabled
            or self.config.spend_enabled
            or self.config.episodic_enabled
        )

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
            "Retention manager started (interval=%ds, ccr=%s, audit=%s, spend=%s, episodic=%s)",
            self.config.cleanup_interval_seconds,
            self.config.ccr_enabled,
            self.config.audit_enabled,
            self.config.spend_enabled,
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
            "dry_run": self.config.dry_run,
            "audit_db_path": str(self.resolve_audit_db_path()),
            "config": {
                "ccr_max_age_seconds": self.config.ccr_max_age_seconds,
                "ccr_max_entries": self.config.ccr_max_entries,
                "audit_max_age_days": self.config.audit_max_age_days,
                "audit_max_db_size_mb": self.config.audit_max_db_size_mb,
                "spend_max_age_days": self.config.spend_max_age_days,
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
        results = {
            "ccr_deleted": 0,
            "audit_deleted": 0,
            "spend_deleted": 0,
            "episodic_deleted": 0,
        }

        if self.config.ccr_enabled:
            results["ccr_deleted"] = await asyncio.to_thread(self._cleanup_ccr_entries)

        if self.config.audit_enabled:
            results["audit_deleted"] = await asyncio.to_thread(self._cleanup_audit_log)

        if self.config.spend_enabled:
            results["spend_deleted"] = await asyncio.to_thread(self._cleanup_spend_ledger)

        if self.config.episodic_enabled:
            results["episodic_deleted"] = await asyncio.to_thread(self._cleanup_episodic_memories)

        if not self.config.dry_run:
            self._stats["ccr_deleted"] += results["ccr_deleted"]
            self._stats["audit_deleted"] += results["audit_deleted"]
            self._stats["spend_deleted"] += results["spend_deleted"]
            self._stats["episodic_deleted"] += results["episodic_deleted"]
        self._stats["last_cleanup"] = time.time()
        self._stats["cleanup_count"] += 1

        total = sum(results.values())
        if total > 0:
            logger.info(
                "Retention cleanup: ccr=%d, audit=%d, spend=%d, episodic=%d",
                results["ccr_deleted"],
                results["audit_deleted"],
                results["spend_deleted"],
                results["episodic_deleted"],
            )

        return results

    def _cleanup_ccr_entries(self) -> int:
        """Remove expired CCR entries from the compression store."""
        try:
            from cutctx.cache.compression_store import get_compression_store

            store = get_compression_store()
            if self.config.dry_run:
                return store.preview_cleanup(
                    max_age_seconds=self.config.ccr_max_age_seconds,
                    max_entries=self.config.ccr_max_entries,
                )
            return store.cleanup_retention(
                max_age_seconds=self.config.ccr_max_age_seconds,
                max_entries=self.config.ccr_max_entries,
            )
        except Exception:
            self._record_failure("ccr")
            logger.warning("CCR retention cleanup failed", exc_info=True)
            return 0

    def resolve_audit_db_path(self) -> Path:
        """Resolve the audit DB this manager will operate on, explicitly.

        Precedence, most specific first:

        1. ``RetentionConfig.audit_db_path`` — set it and nothing else is
           consulted. This is the only form a test or ops script should use.
        2. ``CUTCTX_RETENTION_AUDIT_DB_PATH`` — retention-specific override.
        3. ``CUTCTX_AUDIT_DB_PATH`` — the proxy-wide audit DB location.
        4. ``~/.cutctx/audit.db`` — the implicit user-level default.

        The implicit default remains supported for compatibility. Exposing the
        resolved path makes the target inspectable before anything is deleted;
        resolution alone does not protect a bare manager from that target.
        """
        explicit = (self.config.audit_db_path or "").strip()
        if explicit:
            return Path(explicit).expanduser()
        for env_key in ("CUTCTX_RETENTION_AUDIT_DB_PATH", "CUTCTX_AUDIT_DB_PATH"):
            value = (os.environ.get(env_key) or "").strip()
            if value:
                return Path(value).expanduser()
        return Path.home() / ".cutctx" / "audit.db"

    def _cleanup_audit_log(self) -> int:
        """Remove old audit log entries and checkpoint WAL.

        Honours ``config.dry_run``: the same predicate is evaluated as a
        COUNT and nothing is written.
        """
        db_path = self.resolve_audit_db_path()
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
                cutoff_epoch = time.time() - (self.config.audit_max_age_days * 86400)
                candidates = []
                for rowid, raw_timestamp in conn.execute(
                    "SELECT rowid, timestamp FROM audit_events"
                ):
                    timestamp = _parse_retention_timestamp(raw_timestamp)
                    if timestamp is not None and timestamp < cutoff_epoch:
                        candidates.append(rowid)

                if self.config.dry_run:
                    would_delete = len(candidates)
                    logger.info(
                        "Retention DRY RUN: would delete %d audit row(s) from %s",
                        would_delete,
                        db_path,
                    )
                    return would_delete

                deleted = 0
                for rowid in candidates:
                    cursor = conn.execute("DELETE FROM audit_events WHERE rowid = ?", (rowid,))
                    deleted += max(0, cursor.rowcount or 0)

                # End the delete transaction before maintenance statements.
                # SQLite rejects VACUUM while a transaction is active.
                conn.commit()

                # VACUUM if significant deletion
                if deleted > 100:
                    conn.execute("VACUUM")

                # WAL checkpoint (may fail if journal mode is DELETE)
                try:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except sqlite3.OperationalError:
                    pass  # Not in WAL mode, skip checkpoint

                return deleted
            finally:
                conn.close()
        except Exception:
            self._record_failure("audit")
            logger.warning("Audit retention cleanup failed", exc_info=True)
            return 0

    def _cleanup_episodic_memories(self) -> int:
        """Remove old episodic memory files."""
        try:
            memories_dir = Path.home() / ".cutctx" / "memories"
            if not memories_dir.exists():
                return 0

            deleted = 0
            cutoff = time.time() - (self.config.episodic_max_age_days * 86400)

            for md_file in memories_dir.glob("*.md"):
                try:
                    if md_file.stat().st_mtime < cutoff:
                        deleted += 1
                        if not self.config.dry_run:
                            md_file.unlink()
                except OSError:
                    continue

            return deleted
        except Exception:
            self._record_failure("episodic")
            logger.warning("Episodic memory retention cleanup failed", exc_info=True)
            return 0

    def _cleanup_spend_ledger(self) -> int:
        """Remove expired spend events and reclaim SQLite storage."""
        db_url = os.environ.get("CUTCTX_SPEND_DB_URL", "sqlite:///spend_ledger.db")
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(db_url)
            cutoff = int(time.time() - (self.config.spend_max_age_days * 86400))
            try:
                with engine.begin() as conn:
                    if self.config.dry_run:
                        result = conn.execute(
                            text("SELECT COUNT(*) FROM spend_events WHERE ts < :cutoff"),
                            {"cutoff": cutoff},
                        )
                        deleted = int(result.scalar_one() or 0)
                    else:
                        result = conn.execute(
                            text("DELETE FROM spend_events WHERE ts < :cutoff"),
                            {"cutoff": cutoff},
                        )
                        deleted = max(0, int(result.rowcount or 0))

                if not self.config.dry_run and deleted > 100 and engine.dialect.name == "sqlite":
                    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                        conn.execute(text("VACUUM"))
                return deleted
            finally:
                engine.dispose()
        except Exception:
            self._record_failure("spend")
            logger.warning("Spend ledger retention cleanup failed", exc_info=True)
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


def _parse_retention_timestamp(value: Any) -> float | None:
    """Parse only supported timestamp formats for the retention boundary."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        numeric = float(value)
        return numeric if isfinite(numeric) else None
    if not isinstance(value, str):
        return None
    if _STRICT_NUMERIC_TEXT.fullmatch(value):
        numeric = float(value)
        return numeric if isfinite(numeric) else None
    if not _CANONICAL_UTC_ISO.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


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

"""Tests for SQLite schema migration system.

Covers:
1. No-op when versions match (0->0, 1->1, 1->1)
2. Successful multi-step upgrade (1->2->3) with steps applied in order
3. Newer-than-expected case still raises
4. Version gap with no registered migration raises with clear error
5. Resumability: a step failing mid-way leaves user_version at the last successfully completed step
6. Backwards compatibility: existing stamp_schema_version calls without migrations still work
7. SQLAlchemy adapter works the same way
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from cutctx.storage.sqlite_schema import (
    _MIGRATION_REGISTRY,
    register_migration,
    stamp_schema_version,
    stamp_sqlalchemy_schema_version,
    upgrade_schema,
)


@pytest.fixture(autouse=True)
def _clear_migration_registry():
    """Clear the global migration registry before and after each test."""
    yield
    _MIGRATION_REGISTRY.clear()


def _create_test_db(path: Path, version: int = 0) -> None:
    """Create a test database with a given PRAGMA user_version."""
    with sqlite3.connect(str(path)) as conn:
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute(f"PRAGMA user_version = {version}")


def _get_version(path: Path) -> int:
    """Read the PRAGMA user_version from a database."""
    with sqlite3.connect(str(path)) as conn:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])


class TestSchemaVersionNoOp:
    """Tests for the no-op case when versions match."""

    def test_no_op_version_0_to_0(self, tmp_path):
        """Version 0 (unversioned) with expected 0 is no-op."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=0)

        with sqlite3.connect(str(db_path)) as conn:
            stamp_schema_version(conn, expected=0, store_name="test_store")

        assert _get_version(db_path) == 0

    def test_no_op_version_1_to_1(self, tmp_path):
        """Version 1 with expected 1 is no-op."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=1)

        with sqlite3.connect(str(db_path)) as conn:
            stamp_schema_version(conn, expected=1, store_name="test_store")

        assert _get_version(db_path) == 1

    def test_no_op_version_3_to_3(self, tmp_path):
        """Version 3 with expected 3 is no-op."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=3)

        with sqlite3.connect(str(db_path)) as conn:
            stamp_schema_version(conn, expected=3, store_name="test_store")

        assert _get_version(db_path) == 3


class TestBackwardsCompatibility:
    """Tests for backwards compatibility without registered migrations."""

    def test_stamp_0_to_1_without_migrations(self, tmp_path):
        """Version 0 (legacy unversioned) upgrades to 1 silently without migrations."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=0)

        with sqlite3.connect(str(db_path)) as conn:
            stamp_schema_version(conn, expected=1, store_name="test_store")

        assert _get_version(db_path) == 1

    def test_stamp_1_to_2_without_migrations_not_allowed(self, tmp_path):
        """Version 1->2 without migrations raises (not a legacy upgrade)."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=1)

        with pytest.raises(RuntimeError) as exc_info:
            with sqlite3.connect(str(db_path)) as conn:
                stamp_schema_version(conn, expected=2, store_name="test_store")

        message = str(exc_info.value)
        assert "no migration is registered" in message
        # The message must describe the situation correctly: the database is
        # OLDER than the runtime expects, not newer.
        assert "predates this build" in message
        assert "version 1" in message and "expects 2" in message
        assert _get_version(db_path) == 1  # Version unchanged


class TestMultiStepUpgrade:
    """Tests for successful multi-step upgrades with registered migrations."""

    def test_single_step_upgrade_1_to_2(self, tmp_path):
        """Single migration step: 1->2."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=1)

        # Register a migration
        @register_migration("test_store", 2)
        def migrate_1_to_2(conn: sqlite3.Connection) -> None:
            conn.execute("ALTER TABLE items ADD COLUMN new_col TEXT DEFAULT 'migrated'")

        with sqlite3.connect(str(db_path)) as conn:
            upgrade_schema(conn, "test_store", 2)

        # Verify version was updated
        assert _get_version(db_path) == 2

        # Verify schema was actually updated
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("PRAGMA table_info(items)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "new_col" in columns

    def test_multi_step_upgrade_1_to_3(self, tmp_path):
        """Multi-step upgrade: 1->2->3."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=1)

        # Track which steps were executed in order
        executed_steps = []

        @register_migration("test_store", 2)
        def migrate_1_to_2(conn: sqlite3.Connection) -> None:
            executed_steps.append(2)
            conn.execute("ALTER TABLE items ADD COLUMN col_v2 INTEGER DEFAULT 0")

        @register_migration("test_store", 3)
        def migrate_2_to_3(conn: sqlite3.Connection) -> None:
            executed_steps.append(3)
            conn.execute("ALTER TABLE items ADD COLUMN col_v3 TEXT DEFAULT 'v3'")

        with sqlite3.connect(str(db_path)) as conn:
            upgrade_schema(conn, "test_store", 3)

        # Verify steps executed in order
        assert executed_steps == [2, 3]
        assert _get_version(db_path) == 3

        # Verify both schema changes were applied
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("PRAGMA table_info(items)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "col_v2" in columns
            assert "col_v3" in columns

    def test_multi_step_upgrade_2_to_4(self, tmp_path):
        """Upgrade from version 2 to 4, skipping migrations 1->2."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=2)

        executed_steps = []

        @register_migration("test_store", 2)
        def migrate_1_to_2(conn: sqlite3.Connection) -> None:
            # This should NOT be executed since we start at version 2
            executed_steps.append(2)

        @register_migration("test_store", 3)
        def migrate_2_to_3(conn: sqlite3.Connection) -> None:
            executed_steps.append(3)
            conn.execute("ALTER TABLE items ADD COLUMN col_v3 TEXT")

        @register_migration("test_store", 4)
        def migrate_3_to_4(conn: sqlite3.Connection) -> None:
            executed_steps.append(4)
            conn.execute("ALTER TABLE items ADD COLUMN col_v4 TEXT")

        with sqlite3.connect(str(db_path)) as conn:
            upgrade_schema(conn, "test_store", 4)

        # Should only execute 3 and 4, not 2
        assert executed_steps == [3, 4]
        assert _get_version(db_path) == 4


class TestNewerThanExpected:
    """Tests for the case where database is newer than expected."""

    def test_newer_than_expected_raises(self, tmp_path):
        """Database version newer than expected raises RuntimeError."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=3)

        with pytest.raises(RuntimeError) as exc_info:
            with sqlite3.connect(str(db_path)) as conn:
                stamp_schema_version(conn, expected=2, store_name="test_store")

        assert "newer than this runtime supports" in str(exc_info.value)
        assert "upgrade Cutctx" in str(exc_info.value)
        assert _get_version(db_path) == 3  # Version unchanged

    def test_newer_with_upgrade_schema_raises(self, tmp_path):
        """upgrade_schema also raises for newer versions."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=3)

        with pytest.raises(RuntimeError) as exc_info:
            with sqlite3.connect(str(db_path)) as conn:
                upgrade_schema(conn, "test_store", 2)

        assert "newer than this runtime supports" in str(exc_info.value)


class TestVersionGapWithoutMigration:
    """Tests for version gaps with no registered migration path."""

    def test_version_gap_raises(self, tmp_path):
        """Version gap with no migrations raises clear error."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=1)

        # No migrations registered for this store
        with pytest.raises(RuntimeError) as exc_info:
            with sqlite3.connect(str(db_path)) as conn:
                upgrade_schema(conn, "test_store_no_migrations", 2)

        error_msg = str(exc_info.value)
        assert "migration path" in error_msg
        assert "version 1" in error_msg
        assert "expected 2" in error_msg

    def test_version_gap_missing_intermediate_migration(self, tmp_path):
        """Missing an intermediate migration raises error."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=1)

        # Register only 3, not 2
        @register_migration("test_store", 3)
        def migrate_2_to_3(conn: sqlite3.Connection) -> None:
            pass

        with pytest.raises(RuntimeError) as exc_info:
            with sqlite3.connect(str(db_path)) as conn:
                upgrade_schema(conn, "test_store", 3)

        error_msg = str(exc_info.value)
        assert "incomplete migration path" in error_msg or "missing migrations" in error_msg


class TestResumability:
    """Tests for resumability after partial migration failure."""

    def test_resumable_after_failed_step(self, tmp_path):
        """Failed migration leaves version at last successful step (resumable)."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=1)

        call_count = {"step_2": 0, "step_3": 0}

        @register_migration("test_store", 2)
        def migrate_1_to_2(conn: sqlite3.Connection) -> None:
            call_count["step_2"] += 1
            conn.execute("ALTER TABLE items ADD COLUMN col_v2 TEXT")

        @register_migration("test_store", 3)
        def migrate_2_to_3(conn: sqlite3.Connection) -> None:
            call_count["step_3"] += 1
            raise ValueError("Intentional migration failure")

        # First upgrade attempt should fail at step 3
        with pytest.raises(ValueError):
            with sqlite3.connect(str(db_path)) as conn:
                upgrade_schema(conn, "test_store", 3)

        # Step 2 succeeded and was committed; step 3 failed and was rolled back
        assert _get_version(db_path) == 2
        assert call_count["step_2"] == 1
        assert call_count["step_3"] == 1  # It was attempted

        # Verify step 2 actually succeeded (schema changed)
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("PRAGMA table_info(items)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "col_v2" in columns

    def test_resumable_fix_and_retry(self, tmp_path):
        """Can fix and retry after a failed migration step."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=1)

        attempt_count = {"step_3": 0}

        @register_migration("test_store", 2)
        def migrate_1_to_2(conn: sqlite3.Connection) -> None:
            conn.execute("ALTER TABLE items ADD COLUMN col_v2 TEXT")

        @register_migration("test_store", 3)
        def migrate_2_to_3(conn: sqlite3.Connection) -> None:
            attempt_count["step_3"] += 1
            if attempt_count["step_3"] == 1:
                raise ValueError("First attempt fails")
            conn.execute("ALTER TABLE items ADD COLUMN col_v3 TEXT")

        # First attempt fails at step 3
        with pytest.raises(ValueError):
            with sqlite3.connect(str(db_path)) as conn:
                upgrade_schema(conn, "test_store", 3)

        assert _get_version(db_path) == 2

        # Retry should skip step 2 and try step 3 again
        with sqlite3.connect(str(db_path)) as conn:
            upgrade_schema(conn, "test_store", 3)

        assert _get_version(db_path) == 3
        assert attempt_count["step_3"] == 2
        # Verify both steps eventually succeeded
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("PRAGMA table_info(items)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "col_v2" in columns
            assert "col_v3" in columns


class TestStampWithMigrations:
    """Tests for stamp_schema_version when migrations are registered."""

    def test_stamp_triggers_upgrade_when_migrations_exist(self, tmp_path):
        """stamp_schema_version uses upgrade_schema when migrations exist."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=1)

        @register_migration("test_store", 2)
        def migrate_1_to_2(conn: sqlite3.Connection) -> None:
            conn.execute("ALTER TABLE items ADD COLUMN col_v2 TEXT")

        with sqlite3.connect(str(db_path)) as conn:
            stamp_schema_version(conn, expected=2, store_name="test_store")

        assert _get_version(db_path) == 2


class TestSQLAlchemyAdapter:
    """Tests for the SQLAlchemy adapter."""

    def test_sqlalchemy_skip_non_sqlite(self):
        """SQLAlchemy adapter returns silently for non-SQLite dialects."""

        # Create a mock engine with a non-SQLite dialect
        class MockDialect:
            name = "postgresql"

        class MockEngine:
            dialect = MockDialect()

        # Should not raise
        stamp_sqlalchemy_schema_version(MockEngine(), expected=1, store_name="test")

    def test_sqlalchemy_backwards_compat(self, tmp_path):
        """SQLAlchemy adapter maintains backwards compat without migrations."""
        pytest.importorskip("sqlalchemy")
        from sqlalchemy import create_engine

        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"
        engine = create_engine(db_url)

        # Create table via SQLAlchemy
        from sqlalchemy import Column, Integer, MetaData, String, Table

        metadata = MetaData()
        items = Table("items", metadata, Column("id", Integer, primary_key=True))
        metadata.create_all(engine)

        # Stamp via SQLAlchemy adapter
        stamp_sqlalchemy_schema_version(engine, expected=1, store_name="test_store")

        # Verify version was stamped
        assert _get_version(db_path) == 1


class TestEdgeCases:
    """Edge cases and error conditions."""

    def test_migration_with_different_store_names(self, tmp_path):
        """Different store names maintain separate migration registries."""
        db_path_1 = tmp_path / "store1.db"
        db_path_2 = tmp_path / "store2.db"
        _create_test_db(db_path_1, version=1)
        _create_test_db(db_path_2, version=1)

        @register_migration("store_1", 2)
        def migrate_store_1(conn: sqlite3.Connection) -> None:
            conn.execute("ALTER TABLE items ADD COLUMN store1_col TEXT")

        @register_migration("store_2", 2)
        def migrate_store_2(conn: sqlite3.Connection) -> None:
            conn.execute("ALTER TABLE items ADD COLUMN store2_col TEXT")

        with sqlite3.connect(str(db_path_1)) as conn:
            upgrade_schema(conn, "store_1", 2)

        with sqlite3.connect(str(db_path_2)) as conn:
            upgrade_schema(conn, "store_2", 2)

        # Each database has its own column
        with sqlite3.connect(str(db_path_1)) as conn:
            cursor = conn.execute("PRAGMA table_info(items)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "store1_col" in columns
            assert "store2_col" not in columns

        with sqlite3.connect(str(db_path_2)) as conn:
            cursor = conn.execute("PRAGMA table_info(items)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "store2_col" in columns
            assert "store1_col" not in columns

    def test_partial_version_gap(self, tmp_path):
        """Partial version gap (migrations exist but not for all steps) raises."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path, version=1)

        @register_migration("test_store", 3)
        def migrate_2_to_3(conn: sqlite3.Connection) -> None:
            pass

        # No migration for 1->2, but we're trying to go to 3
        with pytest.raises(RuntimeError):
            with sqlite3.connect(str(db_path)) as conn:
                upgrade_schema(conn, "test_store", 3)

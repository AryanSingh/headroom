"""Shared SQLite schema-version guard and migration system.

SQLite's ``PRAGMA user_version`` is application-owned metadata.  Every mutable
store should stamp a version after its schema initialization so future releases
can distinguish a legacy database from an incompatible newer one.

This module provides:
- Schema version stamping (backwards compatible)
- Migration registry for ordered schema upgrades
- Resumable multi-step upgrade path inside transactions
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Migration registry: store_name -> {target_version: migration_function}
# Each migration_function(conn: sqlite3.Connection) applies a single step.
_MIGRATION_REGISTRY: dict[str, dict[int, Callable[[sqlite3.Connection], None]]] = {}


def register_migration(
    store_name: str,
    target_version: int,
) -> Callable[[Callable[[sqlite3.Connection], None]], Callable[[sqlite3.Connection], None]]:
    """Decorator to register a migration step for a store.

    Each migration is a callable that takes a sqlite3.Connection and modifies
    the schema. Migrations are applied in order by target_version.

    Example:
        @register_migration("my_store", 2)
        def migrate_1_to_2(conn: sqlite3.Connection) -> None:
            conn.execute("ALTER TABLE items ADD COLUMN new_col TEXT DEFAULT ''")

    Args:
        store_name: The name of the store (matches stamp_schema_version store_name)
        target_version: The version this migration brings the schema to

    Returns:
        A decorator function
    """

    def decorator(
        func: Callable[[sqlite3.Connection], None],
    ) -> Callable[[sqlite3.Connection], None]:
        if store_name not in _MIGRATION_REGISTRY:
            _MIGRATION_REGISTRY[store_name] = {}
        _MIGRATION_REGISTRY[store_name][target_version] = func
        return func

    return decorator


def upgrade_schema(
    conn: sqlite3.Connection,
    store_name: str,
    target_version: int,
) -> None:
    """Apply registered migrations to upgrade a database schema.

    Migrations are applied in order, one step at a time. The PRAGMA user_version
    is updated after each step, so an interrupted upgrade is resumable.

    If the database version already matches the target, this is a no-op.
    If the database version is newer than the target, a RuntimeError is raised.
    If the database version is older than the target but no migrations exist
    for that store, a RuntimeError is raised.

    Args:
        conn: An open sqlite3.Connection
        store_name: The name of the store
        target_version: The version to upgrade to

    Raises:
        RuntimeError: If database is newer than target, or if there's a version
                      gap with no migration path
    """
    row = conn.execute("PRAGMA user_version").fetchone()
    current = int(row[0]) if row else 0

    # Newer version: cannot downgrade
    if current > target_version:
        raise RuntimeError(
            f"{store_name} schema version {current} is newer than this runtime "
            f"supports ({target_version}); upgrade Cutctx before opening this database"
        )

    # Already at target version
    if current == target_version:
        return

    # Need to upgrade: check if migrations exist
    migrations = _MIGRATION_REGISTRY.get(store_name, {})
    if not migrations:
        raise RuntimeError(
            f"{store_name} schema is at version {current} but expected {target_version}; "
            f"no migration path exists. This likely means the database was created by "
            f"a newer version of Cutctx and cannot be opened by this version. "
            f"Please upgrade Cutctx."
        )

    # Find all migration steps from current to target
    migration_steps = sorted(
        (version, func)
        for version, func in migrations.items()
        if current < version <= target_version
    )

    if not migration_steps:
        raise RuntimeError(
            f"{store_name} schema is at version {current} but expected {target_version}; "
            f"migration steps {current + 1} through {target_version} are not registered"
        )

    # Validate that all steps are present (no gaps in the migration path)
    expected_versions = set(range(current + 1, target_version + 1))
    actual_versions = {version for version, _ in migration_steps}
    if actual_versions != expected_versions:
        missing = expected_versions - actual_versions
        raise RuntimeError(
            f"{store_name} schema has incomplete migration path from {current} to {target_version}; "
            f"missing migrations for version(s): {sorted(missing)}"
        )

    # Apply migrations in order, updating version after each step
    for step_target_version, migration_func in migration_steps:
        try:
            migration_func(conn)
            conn.execute(f"PRAGMA user_version = {step_target_version}")
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(
                "Migration for %s to version %d failed: %s",
                store_name,
                step_target_version,
                e,
            )
            raise


def stamp_schema_version(
    conn: sqlite3.Connection,
    *,
    expected: int,
    store_name: str,
) -> None:
    """Stamp an initialized schema and reject databases from newer releases.

    This function is backwards compatible with the old behavior for cases where
    no migrations are registered (version 0->1). For version upgrades with
    registered migrations, it delegates to upgrade_schema().

    Args:
        conn: An open sqlite3.Connection
        expected: The expected schema version
        store_name: The name of the store (used in error messages and migration registry)

    Raises:
        RuntimeError: If database is newer than expected, or if an upgrade path
                      is needed but no migrations are registered
    """
    row = conn.execute("PRAGMA user_version").fetchone()
    current = int(row[0]) if row else 0

    if current > expected:
        raise RuntimeError(
            f"{store_name} schema version {current} is newer than this runtime "
            f"supports ({expected}); upgrade Cutctx before opening this database"
        )

    # For version upgrades, check if migrations are registered
    if current < expected:
        migrations = _MIGRATION_REGISTRY.get(store_name, {})
        if migrations:
            # Migrations are registered: use the full upgrade path
            upgrade_schema(conn, store_name, expected)
        else:
            # No migrations registered: only allow legacy 0->expected case.
            # For any other version gap (e.g., 1->2), migrations are required.
            if current == 0:
                # Legacy unversioned database: ok to stamp to expected
                # This allows version 0->1 and 0->N for new stores.
                conn.execute(f"PRAGMA user_version = {expected}")
            else:
                # Non-legacy database that is OLDER than this runtime expects,
                # with no registered migration to close the gap. Refusing is
                # the safe choice: the previous behaviour stamped the expected
                # version without changing the schema, leaving a stale database
                # labelled as current.
                raise RuntimeError(
                    f"{store_name} schema is at version {current} but this runtime "
                    f"expects {expected}, and no migration is registered to upgrade "
                    f"it. The database predates this build. Register migration "
                    f"steps for '{store_name}' with @register_migration, or delete "
                    f"the store to have it recreated (data will be lost)."
                )


def stamp_sqlalchemy_schema_version(engine: Any, *, expected: int, store_name: str) -> None:
    """SQLAlchemy-engine adapter for :func:`stamp_schema_version`."""
    dialect = getattr(getattr(engine, "dialect", None), "name", None)
    if dialect != "sqlite":
        return
    with engine.connect() as conn:
        current = int(conn.exec_driver_sql("PRAGMA user_version").scalar_one())
        if current > expected:
            raise RuntimeError(
                f"{store_name} schema version {current} is newer than this runtime "
                f"supports ({expected}); upgrade Cutctx before opening this database"
            )
        if current < expected:
            migrations = _MIGRATION_REGISTRY.get(store_name, {})
            if migrations:
                # Migrations are registered: use the full upgrade path
                upgrade_schema(conn, store_name, expected)
            else:
                # No migrations registered: only allow legacy 0->expected case
                if current == 0:
                    # Legacy unversioned database: ok to stamp to expected
                    conn.exec_driver_sql(f"PRAGMA user_version = {expected}")
                    conn.commit()
                else:
                    # Non-legacy database with version gap but no migrations
                    raise RuntimeError(
                        f"{store_name} schema is at version {current} but expected {expected}; "
                        f"no migration path exists. This likely means the database was created by "
                        f"a newer version of Cutctx and cannot be opened by this version. "
                        f"Please upgrade Cutctx."
                    )


__all__ = [
    "stamp_schema_version",
    "stamp_sqlalchemy_schema_version",
    "register_migration",
    "upgrade_schema",
]

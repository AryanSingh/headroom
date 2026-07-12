"""Shared SQLite schema-version guard.

SQLite's ``PRAGMA user_version`` is application-owned metadata.  Every mutable
store should stamp a version after its schema initialization so future releases
can distinguish a legacy database from an incompatible newer one.
"""

from __future__ import annotations

import sqlite3


def stamp_schema_version(
    conn: sqlite3.Connection,
    *,
    expected: int,
    store_name: str,
) -> None:
    """Stamp an initialized schema and reject databases from newer releases."""
    row = conn.execute("PRAGMA user_version").fetchone()
    current = int(row[0]) if row else 0
    if current > expected:
        raise RuntimeError(
            f"{store_name} schema version {current} is newer than this runtime "
            f"supports ({expected}); upgrade Cutctx before opening this database"
        )
    if current < expected:
        # Version 0 is the legacy, unversioned schema. Callers invoke this only
        # after their idempotent CREATE/ALTER initialization has succeeded.
        conn.execute(f"PRAGMA user_version = {expected}")


__all__ = ["stamp_schema_version"]

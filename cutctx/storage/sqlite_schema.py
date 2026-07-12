"""Shared SQLite schema-version guard.

SQLite's ``PRAGMA user_version`` is application-owned metadata.  Every mutable
store should stamp a version after its schema initialization so future releases
can distinguish a legacy database from an incompatible newer one.
"""

from __future__ import annotations

import sqlite3
from typing import Any


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
            conn.exec_driver_sql(f"PRAGMA user_version = {expected}")
            conn.commit()


__all__ = ["stamp_schema_version", "stamp_sqlalchemy_schema_version"]

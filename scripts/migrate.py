#!/usr/bin/env python3
"""Ordered, version-tracked migration runner for the hosted Postgres schema.

Before this existed, the files in ``sql/`` were applied by hand through the
Supabase SQL editor. Nothing recorded what had been applied, nothing enforced
ordering, and nothing detected a file being edited after it had already run.
This runner closes those three gaps:

* **Ordering** is explicit. ``MIGRATIONS`` below is the source of truth —
  filenames do not sort into the correct dependency order, so alphabetical
  discovery is not safe here.
* **Applied state** is recorded in a ``schema_migrations`` table, so re-running
  is a no-op and a partially-migrated database can be resumed.
* **Drift** is caught by storing a SHA-256 of each file at apply time. Editing
  an already-applied migration is reported by ``verify`` instead of silently
  diverging between environments.

Every migration in ``sql/`` is already idempotent (``IF NOT EXISTS`` /
``CREATE OR REPLACE``), which is what makes adopting this runner safe on a
database that was previously migrated by hand: ``apply`` can be pointed at an
existing database and will bring the bookkeeping table up to date without
re-creating objects. Use ``--baseline`` for that.

Target-database prerequisites
----------------------------
Verified by applying all five migrations against stock ``postgres:16``. These
files were authored for Supabase and need two things a vanilla Postgres does
not provide:

* An ``anon`` role — the RLS policies in ``create_proxy_telemetry_v2.sql``
  grant to it. Create with ``CREATE ROLE anon NOINHERIT;``.
* The ``pg_cron`` extension — ``create_dashboard_summary.sql`` schedules an
  hourly refresh. It must be preloaded, not merely created::

      shared_preload_libraries = 'pg_cron'
      cron.database_name = '<your database>'

  Supabase provides both already. On self-managed Postgres, install pg_cron
  (https://github.com/citusdata/pg_cron) or drop the cron scheduling from that
  migration if the hourly refresh is not required.

Usage
-----
    python scripts/migrate.py plan       # what would run, in order
    python scripts/migrate.py verify     # checksum drift + manifest coverage
    python scripts/migrate.py apply      # apply pending migrations
    python scripts/migrate.py apply --baseline
                                         # record all as applied, run nothing

``plan`` and ``verify`` work without a database driver or connection.
``apply`` requires ``psycopg`` (v3) or ``psycopg2`` and a connection URL in
``DATABASE_URL`` or ``SUPABASE_DB_URL``.

Exit codes: 0 success, 1 drift or failure, 2 usage/configuration error.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = REPO_ROOT / "sql"

# Dependency order, not alphabetical order. `create_dashboard_summary` builds a
# refresh function that queries proxy_telemetry_v2, so the base table must
# exist first; the `upgrade_*` files then patch those objects in sequence.
# A new .sql file MUST be appended here — tests/test_sql_migrations.py fails if
# sql/ contains a file this tuple does not mention.
MIGRATIONS: tuple[str, ...] = (
    "create_proxy_telemetry_v2.sql",
    "create_dashboard_summary.sql",
    "upgrade_dashboard_v2.sql",
    "upgrade_telemetry_cache_bust.sql",
    "upgrade_telemetry_stack_context.sql",
)

BOOKKEEPING_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    text PRIMARY KEY,
    checksum    text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
);
"""


def checksum(path: Path) -> str:
    """SHA-256 of a migration file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_sql_files() -> list[str]:
    """Every .sql filename present in sql/, sorted for stable comparison."""
    if not SQL_DIR.is_dir():
        return []
    return sorted(p.name for p in SQL_DIR.glob("*.sql"))


def manifest_problems() -> list[str]:
    """Mismatches between the manifest and what is actually on disk."""
    problems: list[str] = []
    on_disk = set(discover_sql_files())
    declared = set(MIGRATIONS)

    for name in sorted(on_disk - declared):
        problems.append(
            f"{name}: present in sql/ but not registered in MIGRATIONS — "
            "append it in dependency order"
        )
    for name in sorted(declared - on_disk):
        problems.append(f"{name}: registered in MIGRATIONS but missing from sql/")
    if len(MIGRATIONS) != len(set(MIGRATIONS)):
        problems.append("MIGRATIONS contains duplicate entries")
    return problems


def _connection_url() -> str | None:
    for var in ("DATABASE_URL", "SUPABASE_DB_URL"):
        value = os.environ.get(var, "").strip()
        if value:
            return value
    return None


def _connect(url: str):
    """Open a Postgres connection using whichever driver is installed."""
    try:
        import psycopg  # type: ignore[import-not-found]

        return psycopg.connect(url)
    except ModuleNotFoundError:
        pass
    try:
        import psycopg2  # type: ignore[import-not-found]

        return psycopg2.connect(url)
    except ModuleNotFoundError as exc:
        raise SystemExit("apply requires a Postgres driver: pip install 'psycopg[binary]'") from exc


def _applied_state(conn) -> dict[str, str]:
    """Map of filename -> recorded checksum."""
    with conn.cursor() as cur:
        cur.execute(BOOKKEEPING_DDL)
        cur.execute("SELECT filename, checksum FROM schema_migrations")
        return {row[0]: row[1] for row in cur.fetchall()}


def cmd_plan(_args: argparse.Namespace) -> int:
    problems = manifest_problems()
    for problem in problems:
        print(f"MANIFEST: {problem}", file=sys.stderr)

    print("Migration order:")
    for i, name in enumerate(MIGRATIONS, 1):
        path = SQL_DIR / name
        marker = "" if path.exists() else "  [MISSING]"
        digest = checksum(path)[:12] if path.exists() else "-" * 12
        print(f"  {i}. {name}  sha256:{digest}{marker}")

    url = _connection_url()
    if url:
        print("\nConnection URL is set; run 'apply' to execute pending migrations.")
    else:
        print("\nNo DATABASE_URL / SUPABASE_DB_URL set — this is a dry plan only.")
    return 1 if problems else 0


def cmd_verify(_args: argparse.Namespace) -> int:
    failed = False
    for problem in manifest_problems():
        print(f"MANIFEST: {problem}", file=sys.stderr)
        failed = True

    url = _connection_url()
    if not url:
        print("Manifest checked. Set DATABASE_URL to also verify applied checksums.")
        return 1 if failed else 0

    conn = _connect(url)
    try:
        applied = _applied_state(conn)
    finally:
        conn.close()

    for name in MIGRATIONS:
        path = SQL_DIR / name
        if not path.exists() or name not in applied:
            continue
        current = checksum(path)
        if current != applied[name]:
            print(
                f"DRIFT: {name} was applied as {applied[name][:12]} but is now "
                f"{current[:12]} — the file changed after it ran",
                file=sys.stderr,
            )
            failed = True

    pending = [n for n in MIGRATIONS if n not in applied]
    if pending:
        print(f"Pending: {', '.join(pending)}")
    else:
        print("All registered migrations are applied.")
    return 1 if failed else 0


def cmd_apply(args: argparse.Namespace) -> int:
    problems = manifest_problems()
    if problems:
        for problem in problems:
            print(f"MANIFEST: {problem}", file=sys.stderr)
        print("Refusing to apply with an inconsistent manifest.", file=sys.stderr)
        return 2

    url = _connection_url()
    if not url:
        print("Set DATABASE_URL or SUPABASE_DB_URL before applying.", file=sys.stderr)
        return 2

    conn = _connect(url)
    try:
        applied = _applied_state(conn)
        conn.commit()

        pending = [n for n in MIGRATIONS if n not in applied]
        if not pending:
            print("Nothing to do — all migrations already applied.")
            return 0

        for name in pending:
            path = SQL_DIR / name
            digest = checksum(path)
            if args.baseline:
                # Record without executing: for a database already migrated by
                # hand through the Supabase editor.
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO schema_migrations (filename, checksum) "
                        "VALUES (%s, %s) ON CONFLICT (filename) DO NOTHING",
                        (name, digest),
                    )
                conn.commit()
                print(f"baselined {name}")
                continue

            print(f"applying {name} ...", flush=True)
            try:
                # One transaction per migration so a failure leaves earlier
                # migrations applied and recorded, and this one fully rolled
                # back — resumable rather than half-applied.
                with conn.cursor() as cur:
                    cur.execute(path.read_text())
                    cur.execute(
                        "INSERT INTO schema_migrations (filename, checksum) "
                        "VALUES (%s, %s) ON CONFLICT (filename) DO NOTHING",
                        (name, digest),
                    )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                print(f"FAILED {name}: {exc}", file=sys.stderr)
                print(
                    "Rolled back this migration. Earlier migrations remain "
                    "applied; fix the cause and re-run.",
                    file=sys.stderr,
                )
                return 1
            print(f"  ok {name}")
        return 0
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="show migration order and pending state")
    sub.add_parser("verify", help="check manifest coverage and checksum drift")
    apply_parser = sub.add_parser("apply", help="apply pending migrations")
    apply_parser.add_argument(
        "--baseline",
        action="store_true",
        help="record migrations as applied without executing them (for a "
        "database already migrated by hand)",
    )

    args = parser.parse_args(argv)
    handlers = {"plan": cmd_plan, "verify": cmd_verify, "apply": cmd_apply}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())

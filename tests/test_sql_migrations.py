"""Guards for the ordered SQL migration runner in scripts/migrate.py.

The failure these tests exist to prevent: someone adds a .sql file to sql/ and
it silently never runs, or edits a migration that has already been applied in
production so environments diverge.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = REPO_ROOT / "sql"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "cutctx_migrate", REPO_ROOT / "scripts" / "migrate.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    return _load_runner()


def test_manifest_covers_every_sql_file(runner):
    """A new migration must be registered, or it would never run."""
    problems = runner.manifest_problems()
    assert problems == [], "\n".join(problems)


def test_manifest_has_no_duplicates(runner):
    assert len(runner.MIGRATIONS) == len(set(runner.MIGRATIONS))


def test_base_tables_precede_their_upgrades(runner):
    """`upgrade_*` files patch objects the `create_*` files build."""
    order = list(runner.MIGRATIONS)
    creates = [i for i, n in enumerate(order) if n.startswith("create_")]
    upgrades = [i for i, n in enumerate(order) if n.startswith("upgrade_")]
    assert creates and upgrades
    assert max(creates) < min(upgrades), f"create/upgrade interleaved: {order}"


def test_telemetry_table_precedes_dashboard_summary(runner):
    """create_dashboard_summary's refresh function queries proxy_telemetry_v2."""
    order = list(runner.MIGRATIONS)
    assert order.index("create_proxy_telemetry_v2.sql") < order.index(
        "create_dashboard_summary.sql"
    )


@pytest.mark.parametrize("name", _load_runner().MIGRATIONS)
def test_migration_file_exists_and_is_idempotent(name):
    """Re-running a migration must be safe — the runner relies on this to
    adopt a database that was previously migrated by hand."""
    path = SQL_DIR / name
    assert path.is_file(), f"{name} is registered but missing from sql/"
    body = path.read_text()

    # Every statement that creates or alters an object should be guarded.
    guards = (
        "IF NOT EXISTS",
        "IF EXISTS",
        "CREATE OR REPLACE",
    )
    assert any(g in body.upper() for g in guards), (
        f"{name} has no idempotency guard (IF NOT EXISTS / CREATE OR REPLACE); "
        "re-running it would fail"
    )

    # An unguarded bare CREATE TABLE would break re-runs.
    bare_creates = re.findall(r"CREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS)", body, flags=re.IGNORECASE)
    assert not bare_creates, f"{name} has an unguarded CREATE TABLE"


def test_checksum_is_stable_and_content_sensitive(runner, tmp_path):
    f = tmp_path / "m.sql"
    f.write_text("SELECT 1;")
    first = runner.checksum(f)
    assert first == runner.checksum(f), "checksum must be deterministic"
    f.write_text("SELECT 2;")
    assert runner.checksum(f) != first, "checksum must track content"


def test_plan_runs_without_a_database(runner, capsys, monkeypatch):
    """plan/verify must work with no driver and no connection configured."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    assert runner.cmd_plan(None) == 0
    out = capsys.readouterr().out
    for name in runner.MIGRATIONS:
        assert name in out
    assert "dry plan only" in out


def test_verify_reports_manifest_only_without_connection(runner, capsys, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    assert runner.cmd_verify(None) == 0
    assert "Manifest checked" in capsys.readouterr().out


def test_apply_refuses_without_connection(runner, capsys, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

    class Args:
        baseline = False

    assert runner.cmd_apply(Args()) == 2
    assert "Set DATABASE_URL" in capsys.readouterr().err


def test_unregistered_sql_file_is_reported(runner, monkeypatch):
    """The drift guard: an unregistered file must be flagged, not ignored."""
    monkeypatch.setattr(runner, "discover_sql_files", lambda: [*runner.MIGRATIONS, "zz_new.sql"])
    problems = runner.manifest_problems()
    assert any("zz_new.sql" in p and "not registered" in p for p in problems)


def test_missing_registered_file_is_reported(runner, monkeypatch):
    monkeypatch.setattr(runner, "discover_sql_files", lambda: list(runner.MIGRATIONS[1:]))
    problems = runner.manifest_problems()
    assert any(runner.MIGRATIONS[0] in p and "missing" in p for p in problems)

"""Smoke tests for the backup verification shell script."""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-backup.sh"


def _run_verify(*args: str, data_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if data_dir is not None:
        env["CUTCTX_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _create_sqlite_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE smoke(id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO smoke(value) VALUES ('ok')")


def test_verify_backup_accepts_valid_sqlite_file(tmp_path: Path) -> None:
    db_path = tmp_path / "cutctx.db"
    _create_sqlite_db(db_path)

    result = _run_verify(str(db_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "integrity check passed" in result.stdout
    assert "All checks passed" in result.stdout


def test_verify_backup_rejects_corrupt_sqlite_file(tmp_path: Path) -> None:
    db_path = tmp_path / "cutctx.db"
    db_path.write_bytes(b"not a sqlite database" * 16)

    result = _run_verify(str(db_path))

    assert result.returncode == 1
    assert "integrity check FAILED" in result.stderr
    assert "Some checks failed" in result.stdout


def test_verify_backup_strict_mode_fails_missing_default_dbs(tmp_path: Path) -> None:
    _create_sqlite_db(tmp_path / "cutctx.db")

    result = _run_verify("--strict", data_dir=tmp_path)

    assert result.returncode == 1
    assert "required file not found" in result.stderr
    assert "cutctx_memory.db" in result.stderr


def test_verify_backup_non_strict_mode_fails_when_nothing_verified(tmp_path: Path) -> None:
    result = _run_verify(data_dir=tmp_path)

    assert result.returncode == 1
    assert "No databases were verified" in result.stderr

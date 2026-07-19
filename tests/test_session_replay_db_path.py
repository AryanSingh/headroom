"""CUTCTX_REPLAY_DB_PATH resolution contract.

The env var is operator-supplied configuration (same trust boundary as the
admin key / license), so an explicit path is honored as given — operators
legitimately relocate the journal to another volume. It is NOT untrusted
request input, so no path confinement is applied; unset falls back to the
default under ~/.cutctx.
"""

from __future__ import annotations

from pathlib import Path

from cutctx.proxy import session_replay


def test_replay_db_path_default_when_unset(monkeypatch):
    monkeypatch.delenv("CUTCTX_REPLAY_DB_PATH", raising=False)
    assert session_replay._replay_db_path_from_env() == Path.home() / ".cutctx" / "replay.sqlite3"


def test_replay_db_path_honors_explicit_operator_path(monkeypatch, tmp_path):
    # A custom location on another volume must be honored, not redirected.
    target = tmp_path / "replay.sqlite3"
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(target))
    assert session_replay._replay_db_path_from_env() == target


def test_replay_db_path_expands_user(monkeypatch):
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", "~/.cutctx/custom/replay.sqlite3")
    assert session_replay._replay_db_path_from_env() == (
        Path.home() / ".cutctx" / "custom" / "replay.sqlite3"
    )

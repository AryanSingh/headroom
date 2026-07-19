"""The replay DB path env override must not escape the cutctx workspace.

CUTCTX_REPLAY_DB_PATH is operator-supplied; without validation a value like
'../../etc/cutctx.sqlite3' would let the journal write outside ~/.cutctx.
The proxy already creates parent dirs for this path, so an unbounded value
is a path-traversal write primitive. Validation confines it to the
workspace root and falls back to the default on violation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cutctx.proxy import session_replay


def test_replay_db_path_default_when_unset(monkeypatch):
    monkeypatch.delenv("CUTCTX_REPLAY_DB_PATH", raising=False)
    path = session_replay._replay_db_path_from_env()
    assert path == Path.home() / ".cutctx" / "replay.sqlite3"


def test_replay_db_path_accepts_value_inside_workspace(monkeypatch):
    inside = str(Path.home() / ".cutctx" / "custom" / "replay.sqlite3")
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", inside)
    path = session_replay._replay_db_path_from_env()
    assert path == Path(inside)


def test_replay_db_path_rejects_traversal(monkeypatch):
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", "../../../../tmp/evil.sqlite3")
    path = session_replay._replay_db_path_from_env()
    # Must not resolve outside the workspace; falls back to the safe default.
    assert path == Path.home() / ".cutctx" / "replay.sqlite3"
    assert "tmp/evil" not in str(path)

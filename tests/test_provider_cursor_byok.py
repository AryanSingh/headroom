"""Tests for Cursor app BYOK wiring.

BYOK is the only Cursor path the full proxy pipeline reaches, and the write
target is a live Electron state database holding the user's encrypted API
key — so these tests pin both the happy path and the safety rails.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from cutctx.providers.cursor import byok


def _make_state_db(tmp_path: Path, blob: dict) -> Path:
    db = tmp_path / "state.vscdb"
    conn = sqlite3.connect(db)
    with conn:
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value BLOB)")
        conn.execute(
            "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
            (byok.STATE_KEY, json.dumps(blob)),
        )
    conn.close()
    return db


def _read_blob(db: Path) -> dict:
    conn = sqlite3.connect(db)
    raw = conn.execute("SELECT value FROM ItemTable WHERE key = ?", (byok.STATE_KEY,)).fetchone()[0]
    conn.close()
    return json.loads(raw if isinstance(raw, str) else raw.decode())


# ----------------------------------------------------------------------
# URL shape
# ----------------------------------------------------------------------


def test_proxy_base_url_carries_v1_prefix() -> None:
    """Cursor appends OpenAI paths verbatim, so /v1 must be in the override."""
    assert byok.proxy_base_url(8787) == "http://127.0.0.1:8787/v1"


# ----------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------


def test_read_state_reports_configured_routing(tmp_path: Path) -> None:
    db = _make_state_db(
        tmp_path,
        {"openAIBaseUrl": "http://127.0.0.1:8787/v1", "useOpenAIKey": True, "encryptedKey": "xx"},
    )

    state = byok.read_byok_state(db)

    assert state is not None
    assert state.base_url == "http://127.0.0.1:8787/v1"
    assert state.use_openai_key is True
    assert state.has_api_key is True
    assert state.routes_to("http://127.0.0.1:8787/v1") is True


def test_routes_to_ignores_trailing_slash(tmp_path: Path) -> None:
    db = _make_state_db(
        tmp_path, {"openAIBaseUrl": "http://127.0.0.1:8787/v1/", "useOpenAIKey": True}
    )

    assert byok.read_byok_state(db).routes_to("http://127.0.0.1:8787/v1") is True


def test_routes_to_false_when_byok_disabled(tmp_path: Path) -> None:
    """A base URL with the toggle off routes nothing."""
    db = _make_state_db(
        tmp_path, {"openAIBaseUrl": "http://127.0.0.1:8787/v1", "useOpenAIKey": False}
    )

    assert byok.read_byok_state(db).routes_to("http://127.0.0.1:8787/v1") is False


def test_read_state_none_when_db_missing(tmp_path: Path) -> None:
    assert byok.read_byok_state(tmp_path / "nope.vscdb") is None


def test_read_state_survives_corrupt_blob(tmp_path: Path) -> None:
    db = tmp_path / "state.vscdb"
    conn = sqlite3.connect(db)
    with conn:
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value BLOB)")
        conn.execute(
            "INSERT INTO ItemTable (key, value) VALUES (?, ?)", (byok.STATE_KEY, "not json")
        )
    conn.close()

    assert byok.read_byok_state(db) is None


# ----------------------------------------------------------------------
# Writing
# ----------------------------------------------------------------------


def test_write_sets_base_url_and_enables_byok(tmp_path: Path) -> None:
    db = _make_state_db(tmp_path, {"openAIBaseUrl": "https://api.openai.com/v1", "other": 1})

    with patch.object(byok, "cursor_is_running", return_value=False):
        byok.write_byok_base_url("http://127.0.0.1:9000/v1", db=db, home=tmp_path)

    blob = _read_blob(db)
    assert blob["openAIBaseUrl"] == "http://127.0.0.1:9000/v1"
    assert blob["useOpenAIKey"] is True
    assert blob["other"] == 1  # unrelated state preserved


def test_write_never_touches_the_encrypted_api_key(tmp_path: Path) -> None:
    """The key is the user's secret; Cutctx must leave it exactly as found."""
    db = _make_state_db(tmp_path, {"encryptedKey": "SECRET", "useOpenAIKey": False})

    with patch.object(byok, "cursor_is_running", return_value=False):
        byok.write_byok_base_url("http://127.0.0.1:9000/v1", db=db, home=tmp_path)

    assert _read_blob(db)["encryptedKey"] == "SECRET"


def test_write_snapshots_previous_values(tmp_path: Path) -> None:
    db = _make_state_db(tmp_path, {"openAIBaseUrl": "https://old.example/v1", "useOpenAIKey": True})

    with patch.object(byok, "cursor_is_running", return_value=False):
        snapshot = byok.write_byok_base_url("http://127.0.0.1:9000/v1", db=db, home=tmp_path)

    assert snapshot is not None
    saved = json.loads(snapshot.read_text())
    assert saved["openAIBaseUrl"] == "https://old.example/v1"
    assert saved["useOpenAIKey"] is True


def test_write_is_noop_when_already_correct(tmp_path: Path) -> None:
    db = _make_state_db(
        tmp_path, {"openAIBaseUrl": "http://127.0.0.1:9000/v1", "useOpenAIKey": True}
    )

    with patch.object(byok, "cursor_is_running", return_value=False):
        assert byok.write_byok_base_url("http://127.0.0.1:9000/v1", db=db, home=tmp_path) is None


def test_write_refuses_while_cursor_is_running(tmp_path: Path) -> None:
    """Cursor rewrites state.vscdb on exit, so a live write would be lost."""
    db = _make_state_db(tmp_path, {"openAIBaseUrl": "https://old.example/v1"})

    with patch.object(byok, "cursor_is_running", return_value=True):
        with pytest.raises(byok.CursorRunningError):
            byok.write_byok_base_url("http://127.0.0.1:9000/v1", db=db, home=tmp_path)

    assert _read_blob(db)["openAIBaseUrl"] == "https://old.example/v1"


def test_write_raises_when_db_absent(tmp_path: Path) -> None:
    with patch.object(byok, "cursor_is_running", return_value=False):
        with pytest.raises(FileNotFoundError):
            byok.write_byok_base_url("http://x/v1", db=tmp_path / "none.vscdb", home=tmp_path)


def test_running_check_fails_safe_when_probe_errors() -> None:
    """If we cannot tell, assume running rather than write under a live app."""
    with patch.object(byok.subprocess, "run", side_effect=OSError("no pgrep")):
        assert byok.cursor_is_running() is True


# ----------------------------------------------------------------------
# settings.json hygiene
# ----------------------------------------------------------------------


def test_identifies_inert_byok_keys() -> None:
    settings = {
        "cursor.openai.baseUrl": "http://127.0.0.1:8787/v1",
        "openai.baseUrl": "http://127.0.0.1:8787/v1",
        "editor.fontSize": 12,
    }

    assert byok.ineffective_settings_keys(settings) == [
        "cursor.openai.baseUrl",
        "openai.baseUrl",
    ]


def test_prune_removes_inert_keys_and_keeps_real_ones(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "cursor.general.openAIBaseUrl": "http://127.0.0.1:8787/v1",
                "openai.baseUrl": "http://127.0.0.1:8787/v1",
                "editor.fontSize": 12,
            }
        )
    )

    removed = byok.prune_ineffective_settings(path)

    assert set(removed) == {"cursor.general.openAIBaseUrl", "openai.baseUrl"}
    assert json.loads(path.read_text()) == {"editor.fontSize": 12}


def test_prune_is_noop_without_inert_keys(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"editor.fontSize": 12}))

    assert byok.prune_ineffective_settings(path) == []
    assert json.loads(path.read_text()) == {"editor.fontSize": 12}


def test_prune_handles_missing_file(tmp_path: Path) -> None:
    assert byok.prune_ineffective_settings(tmp_path / "absent.json") == []

"""Cursor app BYOK wiring — the one Cursor path the full proxy pipeline reaches.

Cursor's subscription models (``auto``, ``composer``, and the rest of the
hosted lineup) talk to ``api2.cursor.sh`` over binary protobuf and can never
route through Cutctx. BYOK is the exception: when the user supplies their own
OpenAI key, Cursor sends ordinary OpenAI-format HTTP to a base URL of their
choosing, so pointing that at the local proxy gives compression *and* model
routing for those requests.

Where the setting actually lives
===============================
Not in ``settings.json``. Cursor keeps it inside a single large JSON blob in
its Electron state database::

    ~/Library/Application Support/Cursor/User/globalStorage/state.vscdb
      ItemTable[<STATE_KEY>] -> {..., "openAIBaseUrl": "...",
                                      "useOpenAIKey": true,
                                      "encryptedKey": "..."}

This matters because ``settings.json`` keys like ``cursor.openai.baseUrl`` are
widely passed around as the way to do this and are silently ignored — Cursor
registers no such setting. :func:`ineffective_settings_keys` exists to find
and clear those, since a user who believes one is working has no reason to
look further when savings never appear.

What this module deliberately does not do
=========================================
It never reads or writes ``encryptedKey``. The API key is the user's secret,
Cursor encrypts it with a machine-bound key, and Cutctx has no business
touching it — the user enters it in Cursor's own UI. This module writes only
the base URL and the ``useOpenAIKey`` toggle.

Writes require Cursor to be closed. Cursor holds ``state.vscdb`` open and
rewrites it wholesale on exit, so a write underneath a running app is either
lost or corrupting; Cursor's own import flow refuses for the same reason.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

#: ItemTable key holding Cursor's per-user application state blob.
STATE_KEY = (
    "src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl"
    ".persistentStorage.applicationUser"
)

#: Field inside that blob holding the OpenAI-compatible base URL override.
BASE_URL_FIELD = "openAIBaseUrl"

#: Field toggling "use my own OpenAI key" mode.
USE_KEY_FIELD = "useOpenAIKey"

#: Encrypted API key field. Named here only so it is explicitly never touched.
ENCRYPTED_KEY_FIELD = "encryptedKey"

#: settings.json keys that look like the override but are not registered
#: settings. Verified against Cursor's bundled JS: none of these resolve.
INEFFECTIVE_SETTINGS_KEYS = (
    "cursor.general.openAIBaseUrl",
    "cursor.openai.baseUrl",
    "openai.baseUrl",
    "cursor.openAIBaseUrl",
)


@dataclass(frozen=True)
class ByokState:
    """What Cursor currently believes about BYOK routing."""

    base_url: str | None
    use_openai_key: bool
    has_api_key: bool

    def routes_to(self, expected_url: str) -> bool:
        """True when Cursor would send BYOK traffic to ``expected_url``."""
        return self.use_openai_key and _normalize_url(self.base_url) == _normalize_url(expected_url)


def _normalize_url(url: str | None) -> str:
    return (url or "").strip().rstrip("/")


def proxy_base_url(port: int) -> str:
    """Return the value Cursor's override field should hold for ``port``.

    Cursor appends OpenAI paths to this verbatim, so it must carry the
    ``/v1`` prefix the OpenAI API expects.
    """
    return f"http://127.0.0.1:{port}/v1"


# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------


def app_support_dir(platform: str | None = None, home: Path | None = None) -> Path:
    """Return Cursor's per-user application-support directory."""
    plat = platform if platform is not None else sys.platform
    base = home if home is not None else Path.home()
    if plat == "darwin":
        return base / "Library" / "Application Support" / "Cursor"
    if plat.startswith("win"):
        import os

        appdata = os.environ.get("APPDATA")
        return (Path(appdata) if appdata else base / "AppData" / "Roaming") / "Cursor"
    return base / ".config" / "Cursor"


def state_db_path(platform: str | None = None, home: Path | None = None) -> Path:
    """Return the path to Cursor's Electron state database."""
    return app_support_dir(platform, home) / "User" / "globalStorage" / "state.vscdb"


def settings_path(platform: str | None = None, home: Path | None = None) -> Path:
    """Return the path to Cursor's ``settings.json``."""
    return app_support_dir(platform, home) / "User" / "settings.json"


# ----------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------


def _load_blob(db: Path) -> dict[str, Any] | None:
    if not db.exists():
        return None
    # Read-only URI so a running Cursor is never disturbed by an inspection.
    uri = f"file:{db.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
    except sqlite3.Error:
        return None
    try:
        row = conn.execute("SELECT value FROM ItemTable WHERE key = ?", (STATE_KEY,)).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    if row is None:
        return None
    raw = row[0]
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", "replace")
    try:
        blob = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return blob if isinstance(blob, dict) else None


def read_byok_state(db: Path | None = None) -> ByokState | None:
    """Read Cursor's current BYOK configuration.

    Returns ``None`` when Cursor is not installed or has never written state.
    """
    blob = _load_blob(db if db is not None else state_db_path())
    if blob is None:
        return None
    return ByokState(
        base_url=blob.get(BASE_URL_FIELD) or None,
        use_openai_key=bool(blob.get(USE_KEY_FIELD)),
        # Presence only — the value is the user's encrypted secret.
        has_api_key=bool(blob.get(ENCRYPTED_KEY_FIELD)),
    )


# ----------------------------------------------------------------------
# Writing
# ----------------------------------------------------------------------


class CursorRunningError(RuntimeError):
    """Raised when a write is attempted while Cursor holds the database."""


def cursor_is_running() -> bool:
    """True when the Cursor app appears to be running.

    Cursor rewrites ``state.vscdb`` wholesale on exit, so any write we make
    underneath a live app is silently discarded at best.
    """
    if sys.platform == "darwin":
        cmd = ["pgrep", "-x", "Cursor"]
    elif sys.platform.startswith("win"):
        cmd = ["tasklist", "/FI", "IMAGENAME eq Cursor.exe"]
    else:
        cmd = ["pgrep", "-x", "cursor"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        # Cannot tell — assume it is running so we fail safe rather than
        # writing into a database another process owns.
        return True
    if sys.platform.startswith("win"):
        return "Cursor.exe" in result.stdout
    return result.returncode == 0 and bool(result.stdout.strip())


def backup_dir(home: Path | None = None) -> Path:
    """Directory holding pre-write snapshots of the BYOK fields."""
    base = home if home is not None else Path.home()
    return base / ".cutctx" / "cursor-byok-backups"


def write_byok_base_url(
    base_url: str,
    *,
    db: Path | None = None,
    home: Path | None = None,
    force: bool = False,
) -> Path | None:
    """Point Cursor's BYOK override at ``base_url``.

    Writes only :data:`BASE_URL_FIELD` and :data:`USE_KEY_FIELD`; the
    encrypted API key is left untouched for the user to manage in Cursor's UI.

    Returns the path of the small JSON backup holding the previous values, or
    ``None`` when nothing needed changing.

    Raises:
        CursorRunningError: Cursor is running and ``force`` is False.
        FileNotFoundError: Cursor's state database does not exist.
        RuntimeError: the state blob is missing or unreadable.
    """
    database = db if db is not None else state_db_path()
    if not force and cursor_is_running():
        raise CursorRunningError(
            "Cursor is running. Quit Cursor and re-run — it rewrites its state "
            "database on exit, which would discard this change."
        )
    if not database.exists():
        raise FileNotFoundError(f"Cursor state database not found at {database}")

    blob = _load_blob(database)
    if blob is None:
        raise RuntimeError(f"Could not read Cursor application state from {database}")

    previous = {
        BASE_URL_FIELD: blob.get(BASE_URL_FIELD),
        USE_KEY_FIELD: blob.get(USE_KEY_FIELD),
    }
    if _normalize_url(previous[BASE_URL_FIELD]) == _normalize_url(base_url) and previous.get(
        USE_KEY_FIELD
    ):
        return None

    # Snapshot just the two fields rather than copying a multi-hundred-MB
    # database. That is enough to put the user back exactly where they were.
    snapshot_dir = backup_dir(home)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    snapshot = snapshot_dir / f"byok-{stamp}.json"
    snapshot.write_text(json.dumps(previous, indent=2) + "\n", encoding="utf-8")

    blob[BASE_URL_FIELD] = base_url
    blob[USE_KEY_FIELD] = True

    conn = sqlite3.connect(database, timeout=10)
    try:
        with conn:  # single transaction; rolls back on error
            conn.execute(
                "UPDATE ItemTable SET value = ? WHERE key = ?",
                (json.dumps(blob, separators=(",", ":")), STATE_KEY),
            )
    finally:
        conn.close()
    return snapshot


# ----------------------------------------------------------------------
# settings.json hygiene
# ----------------------------------------------------------------------


def ineffective_settings_keys(settings: dict[str, Any]) -> list[str]:
    """Return BYOK-looking keys present in ``settings`` that Cursor ignores."""
    return [key for key in INEFFECTIVE_SETTINGS_KEYS if key in settings]


def prune_ineffective_settings(path: Path | None = None) -> list[str]:
    """Remove no-op BYOK keys from Cursor's ``settings.json``.

    These keys are inert, so leaving them costs nothing functionally — but
    they read as a working configuration, which is exactly what makes an
    unproxied Cursor hard to debug. Returns the keys removed.
    """
    target = path if path is not None else settings_path()
    if not target.exists():
        return []
    try:
        settings = json.loads(target.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(settings, dict):
        return []

    stale = ineffective_settings_keys(settings)
    if not stale:
        return []
    for key in stale:
        del settings[key]
    try:
        target.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return []
    return stale


__all__ = [
    "BASE_URL_FIELD",
    "ENCRYPTED_KEY_FIELD",
    "INEFFECTIVE_SETTINGS_KEYS",
    "STATE_KEY",
    "USE_KEY_FIELD",
    "ByokState",
    "CursorRunningError",
    "app_support_dir",
    "backup_dir",
    "cursor_is_running",
    "ineffective_settings_keys",
    "proxy_base_url",
    "prune_ineffective_settings",
    "read_byok_state",
    "settings_path",
    "state_db_path",
    "write_byok_base_url",
]

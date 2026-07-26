"""Cursor native harness hooks for Cutctx."""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any

from cutctx.install.runtime import resolve_cutctx_command

_HOOK_MARKER = "cutctx-proxy"
_SESSION_START_COMMAND = "init hook ensure"


def project_hooks_path(cwd: Path | None = None) -> Path:
    """Return the project-level Cursor hooks file path."""
    return (cwd or Path.cwd()) / ".cursor" / "hooks.json"


def _command_string(parts: list[str]) -> str:
    if os.name == "nt":
        import subprocess

        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def _session_start_command() -> str:
    return _command_string([*resolve_cutctx_command(), *_SESSION_START_COMMAND.split()])


def build_hooks_payload() -> dict[str, Any]:
    """Build the Cursor hooks payload that ensures the local proxy is running."""
    return {
        "version": 1,
        "description": "Cutctx proxy lifecycle hooks for Cursor harness",
        "hooks": {
            "sessionStart": [
                {
                    "command": _session_start_command(),
                }
            ],
            "beforeShellExecution": [
                {
                    "command": _session_start_command(),
                }
            ],
        },
        _HOOK_MARKER: {"managed": True},
    }


def ensure_project_hooks(*, cwd: Path | None = None) -> Path:
    """Write or refresh Cutctx-managed hooks in ``.cursor/hooks.json``."""
    path = project_hooks_path(cwd)
    existing = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                existing = payload
        except (OSError, json.JSONDecodeError):
            existing = {}

    managed = existing.get(_HOOK_MARKER)
    if isinstance(managed, dict) and managed.get("managed"):
        payload = build_hooks_payload()
    elif not existing:
        payload = build_hooks_payload()
    else:
        payload = dict(existing)
        payload.setdefault("version", 1)
        hooks = payload.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            hooks = {}
            payload["hooks"] = hooks
        session_hooks = hooks.setdefault("sessionStart", [])
        if not isinstance(session_hooks, list):
            session_hooks = []
            hooks["sessionStart"] = session_hooks
        command = _session_start_command()
        if not any(
            isinstance(item, dict) and item.get("command") == command for item in session_hooks
        ):
            session_hooks.insert(0, {"command": command})
        payload[_HOOK_MARKER] = {"managed": True}

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def remove_project_hooks(*, cwd: Path | None = None) -> bool:
    """Remove Cutctx-managed hooks when we own the file."""
    path = project_hooks_path(cwd)
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    managed = payload.get(_HOOK_MARKER)
    if not isinstance(managed, dict) or not managed.get("managed"):
        return False
    path.unlink(missing_ok=True)
    return True


__all__ = [
    "build_hooks_payload",
    "ensure_project_hooks",
    "project_hooks_path",
    "remove_project_hooks",
]

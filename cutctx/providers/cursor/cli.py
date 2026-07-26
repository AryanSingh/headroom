"""Cursor CLI and IDE binary discovery helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from cutctx.proxy.project_context import with_project_prefix

CURSOR_AGENT_BIN_ENV = "CUTCTX_CURSOR_AGENT_BIN"
CURSOR_IDE_BIN_ENV = "CUTCTX_CURSOR_IDE_BIN"

_AGENT_SEARCH_PATHS = (
    Path.home() / ".local/bin/agent",
    Path.home() / ".cursor/bin/agent",
)

_IDE_SEARCH_PATHS = (
    Path("/Applications/Cursor.app/Contents/MacOS/Cursor"),
    Path.home() / ".local/bin/cursor",
)


def _render_probe_output(stdout: str, stderr: str) -> str:
    payload = (stdout or stderr or "").strip()
    if not payload:
        return ""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return payload.lower()
    return json.dumps(data).lower()


def _probe_cursor_agent(path: Path) -> bool:
    """Return True when ``path`` looks like Cursor's ``agent`` CLI."""
    commands = (
        [str(path), "about"],
        [str(path), "about", "--format", "json"],
    )
    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            continue
        rendered = _render_probe_output(
            result.stdout,
            getattr(result, "stderr", ""),
        )
        if rendered and "cursor" in rendered and "grok" not in rendered:
            return True
    return False


def find_agent_cli() -> Path | None:
    """Locate Cursor's terminal ``agent`` CLI, avoiding unrelated ``agent`` binaries."""
    override = os.environ.get(CURSOR_AGENT_BIN_ENV)
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    for name in ("cursor-agent", "agent"):
        found = shutil.which(name)
        if found:
            path = Path(found)
            if _probe_cursor_agent(path):
                return path

    for path in _AGENT_SEARCH_PATHS:
        if path.is_file() and os.access(path, os.X_OK) and _probe_cursor_agent(path):
            return path
    return None


def find_ide_cli() -> Path | None:
    """Locate the Cursor desktop app launcher, if installed."""
    override = os.environ.get(CURSOR_IDE_BIN_ENV)
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    found = shutil.which("cursor")
    if found:
        return Path(found)

    for path in _IDE_SEARCH_PATHS:
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def build_agent_header_args(project: str | None = None) -> list[str]:
    """Build ``-H`` flags so the proxy can attribute Cursor CLI traffic."""
    args = ["-H", "X-Client: cursor"]
    if project:
        args.extend(["-H", f"X-Cutctx-Project: {project}"])
    return args


def build_agent_endpoint_url(*, port: int, project: str | None = None) -> str:
    """Build the Cutctx proxy endpoint for Cursor Agent CLI traffic."""
    return with_project_prefix(f"http://127.0.0.1:{port}", project)


def build_agent_launch_args(
    *,
    port: int,
    project: str | None = None,
    extra_args: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Compose argv for launching Cursor Agent through Cutctx."""
    args = ["-e", build_agent_endpoint_url(port=port, project=project)]
    args.extend(build_agent_header_args(project))
    if extra_args:
        args.append("--print")
    args.extend(extra_args)
    return tuple(args)


__all__ = [
    "CURSOR_AGENT_BIN_ENV",
    "CURSOR_IDE_BIN_ENV",
    "build_agent_endpoint_url",
    "build_agent_header_args",
    "build_agent_launch_args",
    "find_agent_cli",
    "find_ide_cli",
]

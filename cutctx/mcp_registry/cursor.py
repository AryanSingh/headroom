"""Cursor MCP registrar — covers both the Cursor app and the Cursor CLI.

Cursor keeps one user-level MCP config at ``~/.cursor/mcp.json``, shared by
the desktop app and by ``cursor-agent`` (the CLI). Registering once therefore
serves both hosts, which is why this is a single registrar rather than an
app/CLI pair.

The non-obvious part is that writing ``mcp.json`` is **not sufficient for the
CLI**. Cursor keeps a separate local approval list, so a freshly written
entry reports::

    $ cursor-agent mcp list
    cutctx: not loaded (needs approval)

and none of its tools are available. ``cursor-agent mcp enable <name>`` moves
the server onto the approved list; only then does it report ``ready``. This
registrar runs that step automatically whenever the CLI is installed, so a
single ``cutctx mcp install`` leaves Cursor genuinely usable rather than
merely configured. The app prompts for approval in its own UI, so the CLI
call is a best-effort extra — a missing or failing ``cursor-agent`` never
fails the registration.

Project-scoped registration also writes ``.cursor/mcp.json`` in the working
tree so ``cutctx wrap cursor`` can wire a workspace without relying only on
the user-level file.

Scope note: Cursor's own model traffic never routes through the cutctx proxy.
The CLI speaks binary protobuf (Connect RPC) to ``api2.cursor.sh`` and the app
routes through Cursor's backend, so neither exposes a repointable model
endpoint. Compression reaches these hosts through MCP instead — the cutctx
tools, plus ``cutctx mcp gateway`` wrapping other servers' tool output. The
one exception is the app's BYOK mode, where an OpenAI base-URL override can
point at the proxy; ``cutctx wrap cursor`` prints that configuration.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from cutctx.providers.cursor.config import project_mcp_path

from .base import RegisterResult, RegisterStatus, ServerSpec
from .claude import (
    _diff_specs,
    _entry_to_spec,
    _read_json,
    _spec_to_entry,
    _specs_equivalent,
    _write_json,
)
from .json_registrar import JsonConfigRegistrar

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "mcp.json"

#: How long to wait on a ``cursor-agent mcp`` call before giving up. The
#: command is local bookkeeping, so anything slower than this is a hang.
_CLI_TIMEOUT_SECONDS = 20


def default_config_dir(home: Path | None = None) -> Path:
    """Return the Cursor user config directory.

    Cursor uses ``~/.cursor`` on every platform it ships for, unlike Claude
    Desktop's per-platform application-support paths.
    """
    base = home if home is not None else Path.home()
    return base / ".cursor"


class CursorRegistrar(JsonConfigRegistrar):
    """Register MCP servers with Cursor (app + ``cursor-agent`` CLI)."""

    name = "cursor"
    display_name = "Cursor"
    restart_hint = "restart Cursor to load"

    def __init__(
        self,
        *,
        config_dir: Path | None = None,
        home_dir: Path | None = None,
        cursor_agent_cli: str | None | object = ...,
    ) -> None:
        """Allow overrides for testing.

        ``cursor_agent_cli`` defaults to a :func:`shutil.which` lookup. Pass
        ``None`` to skip the CLI approval step entirely; pass a path to point
        at a specific binary.

        ``home_dir`` is accepted for older callers/tests that construct the
        registrar from a fake home containing ``.cursor/``.
        """
        if config_dir is not None:
            self._config_dir = config_dir
        elif home_dir is not None:
            self._config_dir = home_dir / ".cursor"
        else:
            self._config_dir = default_config_dir()
        super().__init__(self._config_dir / CONFIG_FILENAME)
        if cursor_agent_cli is ...:
            # ``...`` sentinel preserves "not set"; explicit None disables.
            self._cursor_agent = shutil.which("cursor-agent")
        else:
            self._cursor_agent = cursor_agent_cli  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # MCPRegistrar interface
    # ------------------------------------------------------------------

    def detect(self) -> bool:
        """True when either Cursor host is present.

        ``~/.cursor`` is created by both the app and the CLI on first run.
        The PATH lookups cover a CLI-only install whose config dir does not
        exist yet.
        """
        if self._config_dir.is_dir():
            return True
        if bool(self._cursor_agent) or shutil.which("cursor") is not None:
            return True
        try:
            from cutctx.providers.cursor.cli import find_agent_cli

            return find_agent_cli() is not None
        except Exception:
            return False

    def register_server_project(
        self,
        spec: ServerSpec,
        *,
        cwd: Path | None = None,
        force: bool = False,
    ) -> RegisterResult:
        """Register an MCP server in the project-scoped ``.cursor/mcp.json``."""
        path = project_mcp_path(cwd)
        existing = self._read_server_entry(path, spec.name)
        if existing is not None:
            if _specs_equivalent(existing, spec):
                return RegisterResult(RegisterStatus.ALREADY, f"matches {path}")
            if not force:
                return RegisterResult(RegisterStatus.MISMATCH, _diff_specs(existing, spec))
            self._remove_from_file(path, spec.name)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            config = _read_json(path)
            servers = config.setdefault("mcpServers", {})
            servers[spec.name] = _spec_to_entry(spec)
            _write_json(path, config)
        except OSError as exc:
            return RegisterResult(RegisterStatus.FAILED, f"could not write {path}: {exc}")
        return RegisterResult(RegisterStatus.REGISTERED, f"wrote to {path}")

    # ------------------------------------------------------------------
    # Subclass hooks — CLI approval
    # ------------------------------------------------------------------

    def _post_register(self, spec: ServerSpec) -> str | None:
        """Approve the server for ``cursor-agent`` after writing the config.

        Without this the CLI reports ``needs approval`` and loads no tools.
        Best-effort: the app has its own approval UI, so a missing or failing
        CLI leaves the registration successful.
        """
        return self._run_cli("enable", spec.name)

    def _pre_unregister(self, server_name: str) -> None:
        """Drop the server from the CLI's approved list before removing it."""
        self._run_cli("disable", server_name)

    def cli_server_state(self, server_name: str) -> str | None:
        """Return ``cursor-agent``'s own status word for a server.

        ``cursor-agent mcp list`` prints one ``<name>: <state>`` line per
        configured server (``ready``, ``not loaded (needs approval)``, ...).
        That state is the ground truth for whether the CLI will actually load
        our tools, so ``cutctx mcp status`` reports it rather than inferring
        readiness from the config file alone. Returns ``None`` when the CLI is
        absent, errored, or did not mention the server.
        """
        if not self._cursor_agent:
            return None
        try:
            result = subprocess.run(
                [str(self._cursor_agent), "mcp", "list"],
                capture_output=True,
                text=True,
                timeout=_CLI_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("cursor-agent mcp list failed: %s", exc)
            return None
        if result.returncode != 0:
            logger.debug("cursor-agent mcp list failed: %s", result.stderr.strip())
            return None
        prefix = f"{server_name}:"
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith(prefix):
                return stripped[len(prefix) :].strip() or None
        return None

    def _run_cli(self, action: str, server_name: str) -> str | None:
        """Run ``cursor-agent mcp <action> <server>``; never raise.

        Returns a short detail string on success, or ``None`` when the CLI is
        absent or the call failed (the failure is logged, not surfaced as a
        registration error — the config file write already succeeded).
        """
        if not self._cursor_agent:
            return None
        try:
            result = subprocess.run(
                [str(self._cursor_agent), "mcp", action, server_name],
                capture_output=True,
                text=True,
                timeout=_CLI_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("cursor-agent mcp %s failed: %s", action, exc)
            return None
        if result.returncode != 0:
            logger.debug("cursor-agent mcp %s failed: %s", action, result.stderr.strip())
            return None
        return f"approved for cursor-agent via `mcp {action}`"

    def _remove_from_file(self, path: Path, server_name: str) -> bool:
        if not path.exists():
            return False
        try:
            config = _read_json(path)
        except OSError:
            return False
        servers = config.get("mcpServers", {})
        if server_name not in servers:
            return False
        del servers[server_name]
        try:
            _write_json(path, config)
        except OSError:
            return False
        return True

    def _read_server_entry(self, path: Path, server_name: str) -> ServerSpec | None:
        if not path.exists():
            return None
        try:
            config = _read_json(path)
        except OSError:
            return None
        entry = config.get("mcpServers", {}).get(server_name)
        if not isinstance(entry, dict):
            return None
        return _entry_to_spec(server_name, entry)


__all__ = [
    "CONFIG_FILENAME",
    "CursorRegistrar",
    "default_config_dir",
]

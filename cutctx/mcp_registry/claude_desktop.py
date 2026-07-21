"""Claude Desktop app MCP registrar.

The Claude Desktop app reads MCP servers from ``claude_desktop_config.json``:

* macOS:   ``~/Library/Application Support/Claude/claude_desktop_config.json``
* Windows: ``%APPDATA%\\Claude\\claude_desktop_config.json``
* Linux:   ``$XDG_CONFIG_HOME/Claude/claude_desktop_config.json``

There is no CLI — the file is the only registration mechanism. Two quirks
distinguish Desktop from Claude Code:

1. **PATH.** Desktop is a GUI app, so on macOS/Linux it launches MCP servers
   with a minimal environment PATH (``/usr/bin:/bin:...``) that does not
   include Homebrew, pipx, pyenv, or venv bin dirs. A bare ``cutctx`` command
   therefore fails silently. This registrar resolves the command to an
   absolute path at registration time.
2. **Restart required.** Desktop only reads the config at launch, so changes
   take effect after the app is restarted.

Note that only on-demand MCP tools work in Desktop — the transparent proxy
pipeline can't apply because the app's model endpoint is not repointable.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .base import MCPRegistrar, RegisterResult, RegisterStatus, ServerSpec
from .claude import (
    _diff_specs,
    _entry_to_spec,
    _read_json,
    _spec_to_entry,
    _specs_equivalent,
    _write_json,
)

CONFIG_FILENAME = "claude_desktop_config.json"


def default_config_dir(platform: str | None = None, home: Path | None = None) -> Path:
    """Return the Claude Desktop config directory for a platform."""
    plat = platform if platform is not None else sys.platform
    base = home if home is not None else Path.home()
    if plat == "darwin":
        return base / "Library" / "Application Support" / "Claude"
    if plat.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Claude"
        return base / "AppData" / "Roaming" / "Claude"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "Claude"
    return base / ".config" / "Claude"


class ClaudeDesktopRegistrar(MCPRegistrar):
    """Register MCP servers with the Claude Desktop app."""

    name = "claude-desktop"
    display_name = "Claude Desktop"

    def __init__(self, *, config_dir: Path | None = None) -> None:
        """``config_dir`` overrides platform detection (test seam)."""
        self._config_dir = config_dir if config_dir is not None else default_config_dir()
        self._config_path = self._config_dir / CONFIG_FILENAME
        #: Path of the backup written by the most recent gateway wrap, if any.
        self.last_backup_path: Path | None = None

    # ------------------------------------------------------------------
    # MCPRegistrar interface
    # ------------------------------------------------------------------

    def detect(self) -> bool:
        # The config dir is created the first time the Desktop app runs.
        # Its presence (not the config file's — a fresh install has the dir
        # but no file) is the reliable install signal on every platform.
        return self._config_dir.is_dir()

    def get_server(self, server_name: str) -> ServerSpec | None:
        if not self._config_path.exists():
            return None
        config = _read_json(self._config_path)
        entry = config.get("mcpServers", {}).get(server_name)
        if not isinstance(entry, dict):
            return None
        return _entry_to_spec(server_name, entry)

    def register_server(self, spec: ServerSpec, *, force: bool = False) -> RegisterResult:
        spec = self._resolve_command(spec)

        existing = self.get_server(spec.name)
        if existing is not None:
            if _specs_equivalent(existing, spec):
                return RegisterResult(RegisterStatus.ALREADY, "matches current configuration")
            if not force:
                return RegisterResult(RegisterStatus.MISMATCH, _diff_specs(existing, spec))

        try:
            config = _read_json(self._config_path)
            servers = config.setdefault("mcpServers", {})
            servers[spec.name] = _spec_to_entry(spec)
            _write_json(self._config_path, config)
        except OSError as exc:
            return RegisterResult(
                RegisterStatus.FAILED, f"could not write {self._config_path}: {exc}"
            )
        return RegisterResult(
            RegisterStatus.REGISTERED,
            f"wrote to {self._config_path} — restart Claude Desktop to load",
        )

    def unregister_server(self, server_name: str) -> bool:
        if not self._config_path.exists():
            return False
        try:
            config = _read_json(self._config_path)
        except OSError:
            return False
        servers = config.get("mcpServers", {})
        if server_name not in servers:
            return False
        del servers[server_name]
        try:
            _write_json(self._config_path, config)
        except OSError:
            return False
        return True

    # ------------------------------------------------------------------
    # Gateway wrapping
    #
    # Desktop's model endpoint can't be proxied, so automatic compression
    # happens at the MCP layer instead: every *other* stdio server entry is
    # rewritten to launch through ``cutctx mcp gateway -- <original cmd>``,
    # which compresses tools/call results before they reach model context.
    # ------------------------------------------------------------------

    def wrap_servers_with_gateway(self, *, cutctx_command: str | None = None) -> dict[str, str]:
        """Route every other stdio server entry through the gateway.

        Returns ``{server_name: status}`` where status is one of
        ``wrapped``, ``already``, ``skipped (cutctx)``, ``skipped (not stdio)``.
        Idempotent; reversible via :meth:`unwrap_gateway_servers`.
        """
        cutctx_cmd = cutctx_command or shutil.which("cutctx") or "cutctx"
        config = _read_json(self._config_path)
        servers = config.get("mcpServers", {})
        statuses: dict[str, str] = {}
        changed = False
        for name, entry in servers.items():
            if not isinstance(entry, dict):
                continue
            if name == "cutctx":
                statuses[name] = "skipped (cutctx)"
                continue
            if "command" not in entry:
                statuses[name] = "skipped (not stdio)"
                continue
            if _is_gateway_entry(entry):
                statuses[name] = "already"
                continue
            servers[name] = _wrap_entry(entry, cutctx_cmd, name)
            statuses[name] = "wrapped"
            changed = True
        if changed:
            self.last_backup_path = self._backup_config()
            _write_json(self._config_path, config)
        return statuses

    def _backup_config(self) -> Path | None:
        """Copy the config next to itself with a timestamp before we edit it.

        Editing a user's live ``claude_desktop_config.json`` in place is
        risky; a backup makes the wrap trivially recoverable even without
        ``cutctx mcp uninstall``. Returns the backup path, or ``None`` if
        there was nothing to back up or the copy failed.
        """
        if not self._config_path.exists():
            return None
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup = self._config_path.with_name(f"{self._config_path.name}.bak-{stamp}")
        try:
            shutil.copy2(self._config_path, backup)
        except OSError:
            return None
        return backup

    def unwrap_gateway_servers(self) -> list[str]:
        """Restore original commands for every gateway-wrapped entry."""
        config = _read_json(self._config_path)
        servers = config.get("mcpServers", {})
        restored: list[str] = []
        for name, entry in servers.items():
            if isinstance(entry, dict) and _is_gateway_entry(entry):
                original = _unwrap_entry(entry)
                if original is not None:
                    servers[name] = original
                    restored.append(name)
        if restored:
            _write_json(self._config_path, config)
        return restored

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_command(spec: ServerSpec) -> ServerSpec:
        """Rewrite a bare command to an absolute path.

        Claude Desktop launches servers with a GUI-scoped PATH, so a bare
        ``cutctx`` (installed via pipx / Homebrew / venv) is typically not
        findable. Resolve it now, while we *do* have the user's shell PATH.
        Absolute or unresolvable commands are left untouched.
        """
        if os.path.isabs(spec.command) or os.sep in spec.command:
            return spec
        resolved = shutil.which(spec.command)
        if resolved is None:
            return spec
        return replace(spec, command=resolved)


# ----------------------------------------------------------------------
# Gateway entry helpers
# ----------------------------------------------------------------------

_GATEWAY_ARGS_PREFIX = ("mcp", "gateway")


def _is_gateway_entry(entry: dict) -> bool:
    args = entry.get("args")
    return (
        isinstance(args, list)
        and tuple(str(a) for a in args[:2]) == _GATEWAY_ARGS_PREFIX
        and "--" in args
    )


def _wrap_entry(entry: dict, cutctx_cmd: str, name: str) -> dict:
    """Rewrite ``{command, args, env}`` to launch through the gateway.

    The original invocation is preserved verbatim after ``--`` so unwrapping
    needs no side-channel state.
    """
    original_cmd = [str(entry["command"]), *(str(a) for a in entry.get("args", []))]
    wrapped: dict = {
        "command": cutctx_cmd,
        "args": ["mcp", "gateway", "--name", name, "--", *original_cmd],
    }
    if entry.get("env"):
        wrapped["env"] = entry["env"]
    return wrapped


def _unwrap_entry(entry: dict) -> dict | None:
    """Invert :func:`_wrap_entry`. Returns ``None`` for malformed entries."""
    args = [str(a) for a in entry.get("args", [])]
    try:
        sep = args.index("--")
    except ValueError:
        return None
    original = args[sep + 1 :]
    if not original:
        return None
    restored: dict = {"command": original[0]}
    if original[1:]:
        restored["args"] = original[1:]
    if entry.get("env"):
        restored["env"] = entry["env"]
    return restored

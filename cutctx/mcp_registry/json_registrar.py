"""Shared base for agents whose MCP mechanism is a single JSON config file.

Claude Desktop and Cursor both register MCP servers the same way: one JSON
file holding an ``mcpServers`` map of ``{command, args, env}`` entries, with
no CLI that owns the file. They also share the same two operational quirks,
which is why the logic lives here rather than being copied twice:

1. **GUI-scoped PATH.** Both hosts can be launched from the Finder/Dock, so
   their child processes inherit a minimal ``PATH`` that excludes Homebrew,
   pipx, pyenv, and venv bin dirs. A bare ``cutctx`` command therefore fails
   silently. Registration resolves the command to an absolute path while the
   user's shell ``PATH`` is still available.

2. **No proxiable model endpoint.** Neither host lets you repoint the model
   API, so cutctx cannot compress their model traffic. Compression instead
   happens one layer down: every *other* stdio server entry is rewritten to
   launch through ``cutctx mcp gateway -- <original cmd>``, which compresses
   ``tools/call`` results before they reach model context. That rewrite is
   the :meth:`JsonConfigRegistrar.wrap_servers_with_gateway` half of this
   module; :func:`_wrap_entry` keeps the original invocation verbatim after
   ``--`` so unwrapping needs no side-channel state.

Subclasses supply a config path and a display name; everything else is
inherited. :class:`~cutctx.mcp_registry.claude.ClaudeRegistrar` deliberately
does *not* use this base — Claude Code ships a CLI that owns its config, so
it has a genuinely different write path.
"""

from __future__ import annotations

import os
import shutil
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

# ----------------------------------------------------------------------
# Gateway entry helpers
# ----------------------------------------------------------------------

_GATEWAY_ARGS_PREFIX = ("mcp", "gateway")


def _is_gateway_entry(entry: dict) -> bool:
    """True when an ``mcpServers`` entry already launches via the gateway."""
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


class JsonConfigRegistrar(MCPRegistrar):
    """Registrar for agents backed by a single ``mcpServers`` JSON file.

    Subclasses set :attr:`name` / :attr:`display_name` and pass a config
    path to ``__init__``. Override :meth:`detect` and
    :meth:`_registered_detail` where an agent's behaviour differs.
    """

    #: Suffix appended to the "registered" message, e.g. a restart hint.
    restart_hint: str = ""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        #: Path of the backup written by the most recent gateway wrap, if any.
        self.last_backup_path: Path | None = None

    # ------------------------------------------------------------------
    # MCPRegistrar interface
    # ------------------------------------------------------------------

    @property
    def config_path(self) -> Path:
        """Config path, exposed for diagnostics and operator output."""
        return self._config_path

    def detect(self) -> bool:
        return self._config_path.parent.is_dir()

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
                # Already in the file, but the agent may still not have
                # approved it — give subclasses a chance to finish the job.
                detail = self._post_register(spec)
                return RegisterResult(
                    RegisterStatus.ALREADY,
                    _join_detail("matches current configuration", detail),
                )
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

        detail = self._post_register(spec)
        base = f"wrote to {self._config_path}"
        if self.restart_hint:
            base = f"{base} — {self.restart_hint}"
        return RegisterResult(RegisterStatus.REGISTERED, _join_detail(base, detail))

    def unregister_server(self, server_name: str) -> bool:
        self._pre_unregister(server_name)
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
    # Subclass hooks
    # ------------------------------------------------------------------

    def _post_register(self, spec: ServerSpec) -> str | None:
        """Run after the config file is written. Return an extra detail line.

        Cursor overrides this to run ``cursor-agent mcp enable``: writing
        ``mcp.json`` alone leaves the server ``not loaded (needs approval)``.
        """
        del spec
        return None

    def _pre_unregister(self, server_name: str) -> None:
        """Run before the entry is deleted from the config file."""

    # ------------------------------------------------------------------
    # Gateway wrapping
    # ------------------------------------------------------------------

    def gateway_wrapped_servers(self) -> list[str]:
        """Return names of stdio servers currently launching via the gateway."""
        if not self._config_path.exists():
            return []
        config = _read_json(self._config_path)
        return sorted(
            name
            for name, entry in config.get("mcpServers", {}).items()
            if isinstance(entry, dict) and _is_gateway_entry(entry)
        )

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

    def _backup_config(self) -> Path | None:
        """Copy the config next to itself with a timestamp before we edit it.

        Editing a user's live config in place is risky; a backup makes the
        wrap trivially recoverable even without ``cutctx mcp uninstall``.
        Returns the backup path, or ``None`` if there was nothing to back up
        or the copy failed.
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

    @staticmethod
    def _resolve_command(spec: ServerSpec) -> ServerSpec:
        """Rewrite a bare command to an absolute path.

        These hosts launch servers with a GUI-scoped PATH, so a bare
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


def _join_detail(base: str, extra: str | None) -> str:
    return f"{base}; {extra}" if extra else base


__all__ = [
    "JsonConfigRegistrar",
    "_is_gateway_entry",
    "_unwrap_entry",
    "_wrap_entry",
]

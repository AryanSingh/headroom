"""Cursor MCP registrar.

Cursor stores MCP server configuration in ``~/.cursor/mcp.json`` using the
same ``mcpServers`` JSON shape as Claude Desktop / VS Code MCP clients.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from cutctx.providers.cursor.config import project_mcp_path

from .base import MCPRegistrar, RegisterResult, RegisterStatus, ServerSpec
from .claude import (
    _diff_specs,
    _entry_to_spec,
    _read_json,
    _spec_to_entry,
    _specs_equivalent,
    _write_json,
)

logger = logging.getLogger(__name__)


class CursorRegistrar(MCPRegistrar):
    """Register MCP servers with Cursor."""

    name = "cursor"
    display_name = "Cursor"

    def __init__(self, *, home_dir: Path | None = None) -> None:
        home = home_dir if home_dir is not None else Path.home()
        self._cursor_dir = home / ".cursor"
        self._config_file = self._cursor_dir / "mcp.json"

    def detect(self) -> bool:
        if self._cursor_dir.is_dir():
            return True
        if shutil.which("cursor") is not None:
            return True
        from cutctx.providers.cursor.cli import find_agent_cli

        return find_agent_cli() is not None

    def get_server(self, server_name: str) -> ServerSpec | None:
        entry = self._read_server_entry(self._config_file, server_name)
        return entry

    def register_server(self, spec: ServerSpec, *, force: bool = False) -> RegisterResult:
        existing = self.get_server(spec.name)
        if existing is not None:
            if _specs_equivalent(existing, spec):
                return RegisterResult(RegisterStatus.ALREADY, "matches current configuration")
            if not force:
                return RegisterResult(RegisterStatus.MISMATCH, _diff_specs(existing, spec))
            self.unregister_server(spec.name)

        try:
            self._cursor_dir.mkdir(parents=True, exist_ok=True)
            config = _read_json(self._config_file)
            servers = config.setdefault("mcpServers", {})
            servers[spec.name] = _spec_to_entry(spec)
            _write_json(self._config_file, config)
        except OSError as exc:
            return RegisterResult(
                RegisterStatus.FAILED, f"could not write {self._config_file}: {exc}"
            )
        return RegisterResult(RegisterStatus.REGISTERED, f"wrote to {self._config_file}")

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

    def unregister_server(self, server_name: str) -> bool:
        if not self._config_file.exists():
            return False
        try:
            config = _read_json(self._config_file)
        except OSError:
            return False
        servers = config.get("mcpServers", {})
        if server_name not in servers:
            return False
        del servers[server_name]
        try:
            _write_json(self._config_file, config)
        except OSError:
            return False
        return True

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


__all__ = ["CursorRegistrar"]

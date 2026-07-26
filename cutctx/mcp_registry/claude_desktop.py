"""Claude Desktop app MCP registrar.

The Claude Desktop app reads MCP servers from ``claude_desktop_config.json``:

* macOS:   ``~/Library/Application Support/Claude/claude_desktop_config.json``
* Windows: ``%APPDATA%\\Claude\\claude_desktop_config.json``
* Linux:   ``$XDG_CONFIG_HOME/Claude/claude_desktop_config.json``

There is no CLI — the file is the only registration mechanism, so the shared
:class:`~cutctx.mcp_registry.json_registrar.JsonConfigRegistrar` supplies the
read/write, absolute-path resolution, and gateway-wrapping behaviour. Desktop
only reads its config at launch, so changes take effect after a restart.

Note that only on-demand MCP tools work in Desktop — the transparent proxy
pipeline can't apply because the app's model endpoint is not repointable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .json_registrar import (
    JsonConfigRegistrar,
    _is_gateway_entry,
    _unwrap_entry,
    _wrap_entry,
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


class ClaudeDesktopRegistrar(JsonConfigRegistrar):
    """Register MCP servers with the Claude Desktop app."""

    name = "claude-desktop"
    display_name = "Claude Desktop"
    restart_hint = "restart Claude Desktop to load"

    def __init__(self, *, config_dir: Path | None = None) -> None:
        """``config_dir`` overrides platform detection (test seam)."""
        self._config_dir = config_dir if config_dir is not None else default_config_dir()
        super().__init__(self._config_dir / CONFIG_FILENAME)

    def detect(self) -> bool:
        # The config dir is created the first time the Desktop app runs.
        # Its presence (not the config file's — a fresh install has the dir
        # but no file) is the reliable install signal on every platform.
        return self._config_dir.is_dir()


__all__ = [
    "CONFIG_FILENAME",
    "ClaudeDesktopRegistrar",
    "default_config_dir",
    # Re-exported for callers and tests that imported these from here before
    # the shared base was extracted.
    "_is_gateway_entry",
    "_unwrap_entry",
    "_wrap_entry",
]

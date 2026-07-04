"""Runtime helpers for Antigravity (Google VS Code fork) integrations.

Antigravity is Google's VS Code fork, available at
``/Applications/Antigravity.app``. It ships with the Claude Code for VS Code
extension pre-installed, which reads ``ANTHROPIC_BASE_URL`` from the
environment. This module supports two integration modes:

1. **Config-instructions** — start the proxy, inject RTK into
   ``.antigravityrules``, and print setup steps (default).
2. **CLI launch** — discover the ``antigravity`` binary and launch the app
   with ``ANTHROPIC_BASE_URL`` preset so all Claude Code API calls route
   through Cutctx.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from cutctx.providers.claude import proxy_base_url as claude_proxy_base_url
from cutctx.providers.codex import proxy_base_url as codex_proxy_base_url
from cutctx.proxy.project_context import with_project_prefix

#: Known locations to search for the antigravity CLI binary, in priority order.
_CLI_SEARCH_PATHS = [
    # Symlink managed by ~/.antigravity (often ~/.antigravity/antigravity/bin/)
    Path.home() / ".antigravity" / "antigravity" / "bin" / "antigravity",
    # Direct app-bundle entry point (macOS)
    Path("/Applications/Antigravity.app/Contents/MacOS/Antigravity"),
    # Alternative bundle name used in some releases
    Path("/Applications/Antigravity IDE.app/Contents/MacOS/Electron"),
]


def find_cli() -> Path | None:
    """Locate the ``antigravity`` CLI binary on this machine.

    Checks known install paths first, then falls back to ``PATH`` lookup.
    Returns ``None`` if the binary cannot be found.
    """
    for path in _CLI_SEARCH_PATHS:
        resolved = path.resolve()
        if resolved.is_file() and os.access(resolved, os.X_OK):
            return resolved

    # Fallback: scan PATH
    found = shutil.which("antigravity")
    if found:
        return Path(found)

    # No AGY alias too
    found = shutil.which("agy")
    if found:
        return Path(found)

    return None


def render_setup_lines(port: int, project: str | None = None) -> list[str]:
    """Render the Antigravity + Claude Code setup instructions.

    The Claude Code for VS Code extension reads ``ANTHROPIC_BASE_URL`` from
    the environment at startup. Users can either:

    * Set the env var in their shell profile
    * Launch Antigravity from a terminal where the var is already set
    """
    anthropic_base_url = with_project_prefix(claude_proxy_base_url(port), project)
    openai_base_url = with_project_prefix(codex_proxy_base_url(port), project)

    lines = [
        "  Cutctx proxy is running. Configure Antigravity:",
        "",
        "  Option 1 — Set environment variable before launching Antigravity:",
        f"    export ANTHROPIC_BASE_URL={anthropic_base_url}",
        f"    export OPENAI_BASE_URL={openai_base_url}",
        '    open -a "Antigravity"',
        "",
        "  Option 2 — Launch Antigravity CLI through Cutctx directly:",
        "    cutctx wrap antigravity --launch",
        "",
        "  Claude Code for VS Code will route all API calls through the",
        "  local Cutctx proxy at this point.",
    ]

    # Report if the CLI binary was found
    cli_path = find_cli()
    if cli_path:
        lines += [
            "",
            f"  Antigravity CLI found at: {cli_path}",
        ]

    if project:
        lines += [
            "",
            f"  Dashboard savings will be attributed to project '{project}'",
            "  (the directory this command was run from). Re-run from another",
            "  project directory to get that project's URL.",
        ]

    return lines

"""Install the Cutctx compression plugin into an opencode project.

The plugin source lives at ``plugins/cutctx-opencode/cutctx.ts`` in this
repo and is bundled (via esbuild, inlining the ``cutctx-ai`` SDK so it has
no relative-path dependency) to a single self-contained JS file checked
into ``cutctx/providers/opencode/plugin/cutctx.js``. That mirrors how
``cutctx/dashboard/assets/`` ships the built React dashboard inside the
``cutctx`` package tree — anything outside ``cutctx/`` is not present in an
installed package, so the built artifact must live here, not under the
repo-root ``plugins/`` directory.

opencode auto-loads any plugin file dropped into ``.opencode/plugin/`` at
the project root — no config entry required.
"""

from __future__ import annotations

import shutil
from pathlib import Path

_BUNDLED_PLUGIN = Path(__file__).resolve().parent / "plugin" / "cutctx.js"


def install_plugin(project_dir: Path) -> Path | None:
    """Copy the bundled opencode plugin into ``<project_dir>/.opencode/plugin/``.

    Idempotently overwrites on every call so plugin updates propagate.
    Returns the installed path, or ``None`` if the bundled plugin is
    missing (e.g. a dev checkout where the plugin hasn't been built yet).
    """
    if not _BUNDLED_PLUGIN.is_file():
        return None

    target_dir = project_dir / ".opencode" / "plugin"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "cutctx.js"
    shutil.copy2(_BUNDLED_PLUGIN, target_path)
    return target_path

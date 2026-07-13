"""Explicit, non-destructive loading of local Cutctx environment files.

The command-line proxy and configuration check support a local developer
workflow based on ``.env.local`` (or ``.env``).  Loading is deliberately
opt-in at the command boundary rather than at package import time: libraries
must not mutate their host application's environment, and exported secrets
always take precedence over files on disk.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, MutableMapping
from pathlib import Path


def load_local_env(
    *,
    cwd: Path | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> tuple[Path, ...]:
    """Load local env files without overriding already-exported variables.

    ``CUTCTX_ENV_FILE`` selects one explicit file.  Otherwise, the current
    working directory is checked for ``.env.local`` first and then ``.env``.
    The more specific ``.env.local`` wins when both contain the same key.
    Missing files and an unavailable optional ``python-dotenv`` dependency are
    handled without making the CLI unusable.
    """
    target_env = environ if environ is not None else os.environ
    root = (cwd or Path.cwd()).resolve()
    explicit_path = target_env.get("CUTCTX_ENV_FILE", "").strip()
    candidates = (Path(explicit_path).expanduser(),) if explicit_path else (
        root / ".env.local",
        root / ".env",
    )

    loaded: list[Path] = []
    for path in candidates:
        if not path.is_file():
            continue
        for key, value in _read_env_file(path).items():
            target_env.setdefault(key, value)
        loaded.append(path)
    return tuple(loaded)


def _read_env_file(path: Path) -> Mapping[str, str]:
    """Read dotenv syntax when available, with a small dependency-free fallback."""
    try:
        from dotenv import dotenv_values

        return {
            key: value
            for key, value in dotenv_values(path).items()
            if key and value is not None
        }
    except ImportError:
        values: dict[str, str] = {}
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key:
                values[key] = value.strip().strip('"').strip("'")
        return values

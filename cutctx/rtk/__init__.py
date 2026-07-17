"""rtk (Rust Token Killer) integration for Cutctx.

rtk compresses CLI output (test results, git diffs, log dumps) before it
enters the LLM context window. Cutctx downloads and manages the rtk binary.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from pathlib import Path

from cutctx import paths as _paths

RTK_VERSION = "v0.43.0"
RTK_BIN_DIR = _paths.bin_dir()
_RTK_NAME = "rtk.exe" if platform.system() == "Windows" else "rtk"
RTK_BIN_PATH = RTK_BIN_DIR / _RTK_NAME


def _managed_rtk_candidates() -> list[Path]:
    """Return known Cutctx-managed rtk binary paths."""
    candidates = [RTK_BIN_DIR / _RTK_NAME]
    for name in ("rtk", "rtk.exe"):
        path = RTK_BIN_DIR / name
        if path not in candidates:
            candidates.append(path)
    return candidates


def get_rtk_path() -> Path | None:
    """Get path to rtk binary — check PATH first, then ~/.cutctx/bin/."""
    # Check if rtk is already in PATH (e.g., installed via brew)
    system_rtk = shutil.which("rtk")
    if system_rtk:
        return Path(system_rtk)

    # Check Cutctx-managed install
    for candidate in _managed_rtk_candidates():
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


def is_rtk_installed() -> bool:
    """Check if rtk is available."""
    return get_rtk_path() is not None


def get_rtk_version(path: Path) -> str | None:
    """Return a normalized ``vX.Y.Z`` version without rejecting the binary."""
    try:
        result = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", result.stdout)
    return f"v{match.group(1)}" if match else None

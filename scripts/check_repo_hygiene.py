#!/usr/bin/env python3
"""Catch accidentally committed scratch and dependency artifacts.

This is intentionally narrow: it blocks the release-risk files this repo
explicitly treats as unowned or generated, without flagging legitimate long
docs or prose.
"""

from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

DISALLOWED_PATTERNS = (
    "node_modules/**",
    "**/node_modules/**",
    "tmp*.txt",
    "**/tmp*.txt",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "**/*.db",
    "**/*.sqlite",
    "**/*.sqlite3",
)


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def _is_disallowed(path: Path) -> bool:
    normalized = path.as_posix()
    if path.name.startswith("verify-report.") and len(path.parts) == 1:
        return True
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in DISALLOWED_PATTERNS)


def main(argv: list[str]) -> int:
    paths = [Path(arg) for arg in argv[1:]] if len(argv) > 1 else _tracked_files()
    offenders = [path.as_posix() for path in paths if _is_disallowed(path)]
    if offenders:
        print("Repo hygiene check failed:")
        for path in offenders:
            print(f"  {path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

"""Reject credential-shaped OpenAI project keys in files passed by pre-commit."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

OPENAI_PROJECT_KEY = re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}")


def _repository_files() -> list[str]:
    """Return tracked and untracked, nonignored files in the current repository."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode:
        return []
    return result.stdout.splitlines()


def main(paths: list[str]) -> int:
    findings: list[str] = []
    for raw_path in paths or _repository_files():
        path = Path(raw_path)
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if OPENAI_PROJECT_KEY.search(content):
            findings.append(str(path))
    if findings:
        print("credential-shaped OpenAI project key detected in: " + ", ".join(findings))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

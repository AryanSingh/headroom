"""Reject credential-shaped OpenAI project keys in files passed by pre-commit."""

from __future__ import annotations

import re
import sys
from pathlib import Path

OPENAI_PROJECT_KEY = re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}")


def main(paths: list[str]) -> int:
    findings: list[str] = []
    for raw_path in paths:
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

#!/usr/bin/env python3
"""
Baseline-and-ratchet mypy type checker: enforce no NEW type errors.

This script maintains a baseline of existing mypy errors and ensures that
new errors cannot be introduced. It:
  1. Runs mypy (same invocation as CI)
  2. Compares current errors against baseline
  3. Exits 0 if all errors are in the baseline (no NEW errors)
  4. Exits 1 if ANY NEW errors are detected (and reports them)

The baseline file (scripts/.mypy_baseline.txt) is version-controlled and
should be regenerated only when approved type-checking improvements reduce
the error count. Ratcheting prevents regression.
"""

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

#: Matches "path/to/file.py:123: error: message  [code]" so the line number can
#: be stripped. Comparing errors verbatim (including line numbers) made the
#: ratchet fail on any edit that shifted lines: adding 40 lines to a file
#: re-reported every pre-existing error below the insertion as "new". A gate
#: that cries wolf on ordinary refactors gets ignored, so identity is
#: (file, message) and the count per file is what's compared.
_LOCATION = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):(?P<rest>.*)$")


def get_baseline_path() -> Path:
    """Return path to the baseline error file."""
    return Path(__file__).parent / ".mypy_baseline.txt"


def run_mypy() -> list[str]:
    """Run mypy with CI settings and return sorted output lines."""
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "cutctx", "--ignore-missing-imports"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    # Combine stdout and stderr, split by line, and remove empty lines
    output = result.stdout + result.stderr
    lines = [line.rstrip() for line in output.split("\n") if line.strip()]
    return sorted(lines)


def load_baseline() -> list[str]:
    """Load and return the baseline error list (pre-sorted)."""
    baseline_path = get_baseline_path()
    if not baseline_path.exists():
        print(
            f"ERROR: Baseline file not found at {baseline_path}",
            file=sys.stderr,
        )
        sys.exit(2)
    with open(baseline_path) as f:
        return [line.rstrip() for line in f if line.strip()]


def _normalise(line: str) -> str:
    """Strip the line number so an error keeps its identity across edits."""
    match = _LOCATION.match(line)
    if not match:
        return line
    return f"{match.group('path')}:{match.group('rest')}"


def _is_noise(line: str) -> bool:
    """Summary/notes lines vary with the error count and carry no signal."""
    return line.startswith("Found ") or line.startswith("Success:") or ": note:" in line


def find_new_errors(current: list[str], baseline: list[str]) -> list[str]:
    """Return errors present more often now than in the baseline.

    Line numbers are ignored (see `_LOCATION`). Multiplicity still matters: if a
    file had two instances of an error and now has three, that third is new and
    is reported — so the count per (file, message) can never silently grow.
    """
    baseline_counts = Counter(_normalise(line) for line in baseline if not _is_noise(line))
    seen: Counter[str] = Counter()

    new_errors: list[str] = []
    for line in current:
        if _is_noise(line):
            continue
        key = _normalise(line)
        seen[key] += 1
        if seen[key] > baseline_counts.get(key, 0):
            new_errors.append(line)
    return new_errors


def main() -> int:
    """Run mypy, compare to baseline, report new errors, return exit code."""
    baseline = load_baseline()
    current = run_mypy()

    new_errors = find_new_errors(current, baseline)

    if new_errors:
        print(
            f"MYPY RATCHET FAILURE: {len(new_errors)} new type error(s) detected:\n",
            file=sys.stderr,
        )
        for error in new_errors:
            print(error, file=sys.stderr)
        print(
            "\nTo fix: resolve these type errors or update the baseline "
            "(scripts/.mypy_baseline.txt) only when approved.",
            file=sys.stderr,
        )
        return 1

    print("✓ mypy: all current errors are accounted for in baseline (no new errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

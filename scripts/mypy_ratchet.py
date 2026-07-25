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

import subprocess
import sys
from pathlib import Path


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


def find_new_errors(current: list[str], baseline: list[str]) -> list[str]:
    """Return errors in current but not in baseline (true NEW errors)."""
    baseline_set = set(baseline)
    # Filter out summary lines (they will differ with error count changes)
    summary_prefix = "Found "
    new_errors = [
        err for err in current if err not in baseline_set and not err.startswith(summary_prefix)
    ]
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

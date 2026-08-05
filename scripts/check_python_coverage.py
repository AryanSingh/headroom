#!/usr/bin/env python3
"""Enforce independent branch-coverage floors for core and EE packages."""

import argparse
import json
from pathlib import Path
from typing import Any


def package_coverage(report: dict[str, Any], prefix: str) -> float:
    covered = 0
    total = 0
    for name, payload in report.get("files", {}).items():
        if not name.startswith(prefix):
            continue
        summary = payload["summary"]
        covered += summary["covered_lines"] + summary.get("covered_branches", 0)
        total += summary["num_statements"] + summary.get("num_branches", 0)
    if total == 0:
        raise ValueError(f"coverage report contains no files under {prefix!r}")
    return round(covered * 100 / total, 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--core-min", type=float, default=70.0)
    parser.add_argument("--ee-min", type=float, default=60.0)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    measured = {
        "core": package_coverage(report, "cutctx/"),
        "ee": package_coverage(report, "cutctx_ee/"),
    }
    required = {"core": args.core_min, "ee": args.ee_min}
    failures = []
    for package in ("core", "ee"):
        print(f"{package}: {measured[package]:.2f}% (required {required[package]:.2f}%)")
        if measured[package] < required[package]:
            failures.append(package)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

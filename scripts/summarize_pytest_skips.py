"""Turn a pytest JUnit XML report into release-reviewable skip evidence.

Usage:
    pytest -q tests scripts/tests --junitxml=/tmp/pytest.xml
    python scripts/summarize_pytest_skips.py /tmp/pytest.xml --output artifacts/pytest-skips.json
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as element_tree
from collections import Counter
from pathlib import Path


def classify_reason(reason: str) -> str:
    """Classify a skip without concealing its original pytest reason."""
    normalized = reason.lower()
    if "retired" in normalized or normalized.startswith("pending:"):
        return "intentional-deprecation"
    if "gpu" in normalized or "windows" in normalized:
        return "platform-or-hardware"
    if "api_key" in normalized or "credentials" in normalized:
        return "external-credential"
    if (
        "not installed" in normalized
        or "requires extra package" in normalized
        or "is installed" in normalized
    ):
        return "optional-extra"
    if "not running" in normalized or "on path" in normalized or "live proxy" in normalized:
        return "network-service"
    return "uncategorized"


def summarize(report: Path) -> dict[str, object]:
    root = element_tree.parse(report).getroot()
    reasons: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    skipped: list[dict[str, str]] = []
    for case in root.iter("testcase"):
        node = case.find("skipped")
        if node is None:
            continue
        reason = (node.get("message") or node.text or "unspecified skip").strip()
        reasons[reason] += 1
        category = classify_reason(reason)
        categories[category] += 1
        skipped.append(
            {
                "test": f"{case.get('classname', '')}::{case.get('name', '')}",
                "reason": reason,
                "category": category,
            }
        )
    return {
        "schema_version": 1,
        "total_skipped": len(skipped),
        "category_totals": dict(sorted(categories.items())),
        "reasons": [
            {"reason": reason, "count": count, "category": classify_reason(reason)}
            for reason, count in reasons.most_common()
        ],
        "skipped": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="pytest JUnit XML input")
    parser.add_argument("--output", type=Path, help="write JSON evidence to this path")
    args = parser.parse_args()
    payload = summarize(args.report)
    rendered = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Skip evidence -> {args.output}")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()

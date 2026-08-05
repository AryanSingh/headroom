"""Export stable control and KPI catalog CSV files from canonical Markdown."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import yaml


CONTROL_COLUMNS = ("id", "title", "requirement", "applicability", "owner", "frequency", "standard")
KPI_COLUMNS = ("id", "name", "decision", "calculation", "source", "frequency", "owner", "target", "warning")


def _front_matter(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        return {}
    _, block, _ = content.split("---\n", 2)
    result = yaml.safe_load(block) or {}
    return result if isinstance(result, dict) else {}


def _manifest(root: Path) -> list[Path]:
    import re

    return [Path(item) for item in re.findall(r"\[[^\]]+\]\(([^)#]+)", (root / "SUMMARY.md").read_text(encoding="utf-8"))]


def export_catalogs(root: Path, output_dir: Path) -> dict[str, Path]:
    """Write deterministic control and KPI catalogs, returning their paths."""
    root, output_dir = root.resolve(), output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    controls: list[dict[str, str]] = []
    kpis: list[dict[str, str]] = []
    for relative in _manifest(root):
        path = root / relative
        if not path.is_file():
            continue
        metadata = _front_matter(path)
        for item in metadata.get("controls", []):
            if isinstance(item, dict):
                controls.append({
                    **{key: str(item.get(key, "")) for key in CONTROL_COLUMNS[:-1]},
                    "standard": "; ".join(str(value) for value in item.get("standards", [])),
                })
        for item in metadata.get("kpis", []):
            if isinstance(item, dict):
                kpis.append({key: str(item.get(key, "")) for key in KPI_COLUMNS})
    paths = {"controls": output_dir / "control-catalog.csv", "kpis": output_dir / "kpi-catalog.csv"}
    for name, columns, rows in (("controls", CONTROL_COLUMNS, controls), ("kpis", KPI_COLUMNS, kpis)):
        with paths[name].open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda item: item["id"]))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    export_catalogs(args.root, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

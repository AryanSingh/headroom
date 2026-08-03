"""Compile a conservative Mermaid subset into a deterministic SVG validation artifact."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

SUPPORTED = re.compile(r"^(?:graph|flowchart|sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram)\b")


def compile_mermaid(source: Path, output: Path) -> None:
    lines = [line.rstrip() for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines or not SUPPORTED.match(lines[0]):
        raise ValueError("Mermaid source must start with a supported diagram declaration.")
    if any(re.search(r"(?:-->|---|==>)\s*$", line) for line in lines):
        raise ValueError("Mermaid relationship is missing a target.")
    escaped = html.escape("\n".join(lines))
    output.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="120" role="img">'
        '<rect width="100%" height="100%" fill="white"/>'
        f'<text x="16" y="28" font-family="monospace" font-size="14">{escaped}</text>'
        "</svg>",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        compile_mermaid(args.input, args.output)
    except (OSError, ValueError) as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

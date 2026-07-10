"""Deterministic line-preserving compaction for verbatim benchmark fixtures."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class VerbatimCompactorConfig:
    """Configuration for deterministic line/block compaction."""

    context_radius: int = 1
    min_omission_span: int = 2
    omission_template: str = "... [{count} lines omitted] ..."


@dataclass(slots=True)
class VerbatimCompactionResult:
    """Compaction result."""

    compressed: str
    kept_lines: int
    omitted_lines: int


_PATHISH_PATTERN = re.compile(r"[A-Za-z0-9_./-]+(?::\d+)?")
_ERRORISH_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9]+(?:Error|Exception)\b")
_IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_.-]{2,}\b")
_BACKTICK_PATTERN = re.compile(r"`([^`]+)`")


class VerbatimCompactor:
    """Compact line-oriented text while preserving exact critical lines.

    This mode is intentionally simple and deterministic so it can serve as a
    benchmarkable deletion-style baseline separate from the broader pipeline.
    """

    def __init__(self, config: VerbatimCompactorConfig | None = None) -> None:
        self.config = config or VerbatimCompactorConfig()

    def compress(
        self,
        text: str,
        *,
        context: str = "",
        critical_items: list[str] | None = None,
    ) -> VerbatimCompactionResult:
        lines = text.splitlines()
        if len(lines) <= 4:
            return VerbatimCompactionResult(
                compressed=text,
                kept_lines=len(lines),
                omitted_lines=0,
            )

        needles = _dedupe_preserving_order(
            [item for item in (critical_items or []) if item and item.strip()]
            + _infer_needles(context=context, text=text)
        )

        keep = set()
        if lines:
            keep.add(0)
            keep.add(len(lines) - 1)

        for idx, line in enumerate(lines):
            if _line_matches(line, needles):
                start = max(0, idx - self.config.context_radius)
                end = min(len(lines), idx + self.config.context_radius + 1)
                keep.update(range(start, end))

        compressed_lines: list[str] = []
        omitted_lines = 0
        i = 0
        while i < len(lines):
            if i in keep:
                compressed_lines.append(lines[i])
                i += 1
                continue

            span_start = i
            while i < len(lines) and i not in keep:
                i += 1
            span_count = i - span_start
            if span_count >= self.config.min_omission_span:
                omitted_lines += span_count
                compressed_lines.append(self.config.omission_template.format(count=span_count))
                continue

            compressed_lines.extend(lines[span_start:i])

        compressed = "\n".join(compressed_lines)
        if text.endswith("\n"):
            compressed += "\n"

        return VerbatimCompactionResult(
            compressed=compressed,
            kept_lines=len(compressed_lines),
            omitted_lines=omitted_lines,
        )


def _line_matches(line: str, needles: list[str]) -> bool:
    if not line.strip():
        return False
    line_lower = line.lower()
    for needle in needles:
        if needle in line:
            return True
        needle_lower = needle.lower()
        if len(needle_lower) >= 5 and needle_lower in line_lower:
            return True
    return False


def _infer_needles(*, context: str, text: str) -> list[str]:
    candidates: list[str] = []
    for pattern in (_BACKTICK_PATTERN, _ERRORISH_PATTERN, _PATHISH_PATTERN, _IDENTIFIER_PATTERN):
        for match in pattern.findall(context):
            value = match if isinstance(match, str) else match[0]
            value = value.strip()
            if len(value) < 3:
                continue
            if value in text:
                candidates.append(value)
    return candidates


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped

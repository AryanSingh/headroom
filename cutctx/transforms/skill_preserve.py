"""Detect skill/instruction blocks and mark messages for preservation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_DEFAULT_MARKERS = (
    "---\nname:",
    "SKILL.md",
    "# AGENTS",
    "# CLAUDE.md",
)

_EXPLICIT_SKILL_MARKERS = (
    "SKILL.md",
    "# AGENTS",
    "# CLAUDE.md",
)


@dataclass(frozen=True)
class SkillPreserveConfig:
    enabled: bool = True
    markers: tuple[str, ...] = field(default_factory=lambda: _DEFAULT_MARKERS)


def _has_skill_frontmatter(text: str) -> bool:
    sample = text[:4000]
    return sample.lstrip().startswith("---") and "\nname:" in sample[:200].lower()


def _contains_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text[:4000].lower()
    return any(marker.lower() in lowered for marker in markers)


def is_skill_or_instruction_content(
    text: str, *, config: SkillPreserveConfig | None = None
) -> bool:
    cfg = config or SkillPreserveConfig()
    if not text or not cfg.enabled:
        return False
    if _has_skill_frontmatter(text):
        return True
    return _contains_marker(text, cfg.markers)


def _is_explicit_skill_block(text: str) -> bool:
    if not text:
        return False
    if _has_skill_frontmatter(text):
        return True
    return _contains_marker(text, _EXPLICIT_SKILL_MARKERS)


def annotate_messages_for_skill_preserve(
    messages: list[dict[str, Any]], *, config: SkillPreserveConfig | None = None
) -> list[dict[str, Any]]:
    cfg = config or SkillPreserveConfig()
    if not cfg.enabled:
        return messages
    annotated: list[dict[str, Any]] = []
    for msg in messages:
        item = dict(msg)
        content = item.get("content")
        text = content if isinstance(content, str) else ""
        role = item.get("role")
        if role == "system":
            protect = True
        elif role == "tool":
            protect = False
        else:
            protect = _is_explicit_skill_block(text)
        if protect:
            metadata = dict(item.get("metadata") or {})
            metadata["cutctx_skill_preserve"] = True
            item["metadata"] = metadata
        annotated.append(item)
    return annotated

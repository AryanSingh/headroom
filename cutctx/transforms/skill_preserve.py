"""Detect skill/instruction blocks and mark messages for preservation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_DEFAULT_MARKERS = (
    "---\nname:",
    "SKILL.md",
    "# AGENTS",
    "# CLAUDE.md",
    "Always prefix with `rtk`",
    "cutctx_compress",
    "cutctx_retrieve",
)


@dataclass(frozen=True)
class SkillPreserveConfig:
    enabled: bool = True
    markers: tuple[str, ...] = field(default_factory=lambda: _DEFAULT_MARKERS)


def is_skill_or_instruction_content(
    text: str, *, config: SkillPreserveConfig | None = None
) -> bool:
    cfg = config or SkillPreserveConfig()
    if not text or not cfg.enabled:
        return False
    sample = text[:4000]
    lowered = sample.lower()
    if sample.lstrip().startswith("---") and "\nname:" in sample[:200].lower():
        return True
    return any(marker.lower() in lowered for marker in cfg.markers)


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
        protect = role == "system" or is_skill_or_instruction_content(text, config=cfg)
        if protect:
            metadata = dict(item.get("metadata") or {})
            metadata["cutctx_skill_preserve"] = True
            item["metadata"] = metadata
        annotated.append(item)
    return annotated

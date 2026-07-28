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


def skill_preserve_indices(
    messages: list[dict[str, Any]], *, config: SkillPreserveConfig | None = None
) -> frozenset[int]:
    """Indices of messages that hold a skill/instruction body.

    This is the form the compression pipeline uses. Annotating the message
    dicts instead (see ``annotate_messages_for_skill_preserve``) adds a key
    that provider APIs reject on outbound requests, and makes an otherwise
    untouched body look structurally different from the client's bytes —
    which defeats byte-faithful forwarding and collapses prefix-cache hits.

    Role handling: ``tool`` messages are never protected (their payload is
    the bulky output we exist to compress). Every other role is protected
    only when its string content is an explicit skill/instruction block.
    System prompts are already protected by the router's ``skip_system``
    and the selective filter's ``protect_system``, so they get no special
    case here — that keeps an explicit ``compress_system_messages=True``
    meaningful.
    """
    cfg = config or SkillPreserveConfig()
    if not cfg.enabled:
        return frozenset()
    protected: set[int] = set()
    for i, msg in enumerate(messages):
        if msg.get("role") == "tool":
            continue
        content = msg.get("content")
        if not isinstance(content, str):
            continue
        if _is_explicit_skill_block(content):
            protected.add(i)
    return frozenset(protected)


def annotate_messages_for_skill_preserve(
    messages: list[dict[str, Any]], *, config: SkillPreserveConfig | None = None
) -> list[dict[str, Any]]:
    """Copy ``messages`` with ``metadata.cutctx_skill_preserve`` on skill blocks.

    For callers that own their own message plumbing and strip internal keys
    before an outbound request. The compression pipeline uses
    ``skill_preserve_indices`` instead — see the note there.
    """
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

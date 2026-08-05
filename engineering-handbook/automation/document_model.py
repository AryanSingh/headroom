"""Renderer-neutral document nodes for handbook publication."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Node:
    """A semantic unit rendered by DOCX and publication checks."""

    kind: str
    text: str = ""
    level: int = 0
    language: str = ""
    rows: list[list[str]] = field(default_factory=list)
    checked: bool | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def heading(text: str, level: int) -> Node:
    return Node(kind="heading", text=text, level=level)

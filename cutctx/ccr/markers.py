"""Shared CCR marker formatting and parsing helpers.

This module centralizes the marker contracts used across CCR and dedup:

- CCR retrieval tool name
- dedup reference pointer format
- compressed-content marker regexes
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

CCR_TOOL_NAME = "cutctx_retrieve"
DEDUP_REF_MARKER = "[cutctx:ref:{hash}]"

STANDARD_COMPRESSED_MARKER_RE = re.compile(
    r"\[(\d+) \w+ compressed to (\d+)\. Retrieve more: hash=([a-f0-9]{16})\]"
)
LEGACY_COMPRESSED_MARKER_RE = re.compile(r"\[(\d+) \w+ compressed\. hash=([a-f0-9]{16})\]")
OPAQUE_CCR_MARKER_RE = re.compile(r"<<ccr:([a-f0-9]{16})(?:,\w+,\d+(?:\.\d+)?[A-Z]+)?>>")
GENERIC_COMPRESSED_HASH_RE = re.compile(
    r"\[.*?compressed.*?hash=([a-f0-9]{16})\]",
    re.IGNORECASE,
)

MARKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    STANDARD_COMPRESSED_MARKER_RE,
    LEGACY_COMPRESSED_MARKER_RE,
    OPAQUE_CCR_MARKER_RE,
    GENERIC_COMPRESSED_HASH_RE,
)


def format_dedup_ref(hash_key: str) -> str:
    """Format the stable dedup pointer marker."""

    return DEDUP_REF_MARKER.format(hash=hash_key)


def extract_marker_hashes(
    text: str,
    *,
    patterns: tuple[re.Pattern[str], ...] = MARKER_PATTERNS,
) -> list[str]:
    """Extract unique CCR and dedup marker hashes in encounter order."""

    ordered_matches: list[tuple[int, str]] = []
    seen: set[str] = set()
    hashes: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            groups = match.groups()
            hash_key = groups[-1] if groups else match.group(0)
            if hash_key:
                ordered_matches.append((match.start(), hash_key))

    ordered_matches.sort(key=lambda item: item[0])
    for _, hash_key in ordered_matches:
        if hash_key not in seen:
            seen.add(hash_key)
            hashes.append(hash_key)
    return hashes


def extract_marker_hashes_from_payload(value: Any) -> list[str]:
    """Extract CCR marker hashes from nested provider-neutral payload data."""

    hashes: list[str] = []
    seen: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, str):
            for hash_key in extract_marker_hashes(item):
                if hash_key not in seen:
                    seen.add(hash_key)
                    hashes.append(hash_key)
        elif isinstance(item, Mapping):
            for nested in item.values():
                visit(nested)
        elif isinstance(item, Sequence) and not isinstance(item, bytes | bytearray):
            for nested in item:
                visit(nested)

    visit(value)
    return hashes


__all__ = [
    "CCR_TOOL_NAME",
    "DEDUP_REF_MARKER",
    "GENERIC_COMPRESSED_HASH_RE",
    "LEGACY_COMPRESSED_MARKER_RE",
    "MARKER_PATTERNS",
    "OPAQUE_CCR_MARKER_RE",
    "STANDARD_COMPRESSED_MARKER_RE",
    "extract_marker_hashes",
    "extract_marker_hashes_from_payload",
    "format_dedup_ref",
]

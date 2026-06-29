"""Conservative whitespace minification for code-like payloads."""

from __future__ import annotations

import re
from typing import Any


class Deblanker:
    """Minify whitespace without changing line ordering."""

    @staticmethod
    def deblank(text: str) -> tuple[str, dict[str, Any] | None]:
        if not text or not isinstance(text, str):
            return text, None

        normalized = text.replace("\r\n", "\n")
        normalized = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", normalized)
        lines = [line.rstrip() for line in normalized.split("\n")]
        minified = "\n".join(lines).strip()
        return minified, None

    @staticmethod
    def restore(minified_text: str, restore_map: dict[str, Any] | None) -> str:
        del restore_map
        return minified_text

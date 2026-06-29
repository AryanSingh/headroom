"""Helpers for trimming overly long shell-style outputs."""

from __future__ import annotations


class Snipper:
    """Trim middle sections from long line-oriented output."""

    @staticmethod
    def snip(
        text: str,
        max_lines: int = 150,
        head_lines: int = 50,
        tail_lines: int = 50,
    ) -> str:
        if not text:
            return text

        lines = text.split("\n")
        if len(lines) <= max_lines:
            return text
        if head_lines + tail_lines >= len(lines):
            return text

        head = lines[:head_lines]
        tail = lines[-tail_lines:] if tail_lines > 0 else []
        omitted = len(lines) - head_lines - tail_lines
        marker = f"... [snip: omitted {omitted} lines] ..."
        return "\n".join([*head, marker, *tail])

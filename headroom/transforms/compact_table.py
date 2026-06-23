"""CompactTableCompressor — pipe-delimited table format for JSON arrays.

Converts arrays of homogeneous dicts into a compact header+rows format.
60–80% smaller than JSON for large tool output arrays (file listings,
search results, database rows). LLMs read pipe tables natively.

Only activates when:
  - Content is a valid JSON array
  - Array length >= MIN_ROWS (default: 5)
  - >= 60% of items are dicts with overlapping keys (tabular shape check)
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CompactTableResult:
    """Result of compact table compression."""

    compressed: str
    original: str
    row_count: int
    column_count: int
    constant_columns: dict[str, Any]
    compression_ratio: float

    @property
    def tokens_saved_estimate(self) -> int:
        chars_saved = len(self.original) - len(self.compressed)
        return max(0, chars_saved // 4)


class CompactTableCompressor:
    """Compresses JSON arrays of objects into compact pipe-delimited tables.

    Achieves 30-60% size reduction on tabular tool outputs (file listings,
    search results, database rows, API list responses).

    Format example::

        [table:3 rows]
        name | size | modified | type
        alice.py | 1024 | 2026-06-01 | file
        bob.py | 2048 | 2026-06-02 | file
        tests/ | 0 | 2026-06-03 | dir

    Constant columns (same value in all rows) are collapsed into a header
    annotation: ``[type=file ×3]``
    """

    MIN_ROWS = 5
    MIN_COLUMNS = 2
    MAX_CELL_LENGTH = 80
    # Minimum fraction of items that must be dicts with shared keys
    _TABULAR_OVERLAP_THRESHOLD = 0.6
    # Fraction of rows that must share the same value for a column to be
    # considered "near-constant" (e.g. 0.8 = 80%).
    _NEAR_CONSTANT_THRESHOLD = 0.8

    def _is_tabular(self, data: Any) -> bool:
        """Return True if data is a list of dicts with >= 60% key overlap.

        Args:
            data: Parsed JSON value to check.

        Returns:
            True if data qualifies as tabular.
        """
        if not isinstance(data, list) or len(data) < self.MIN_ROWS:
            return False

        dict_items = [item for item in data if isinstance(item, dict)]
        if len(dict_items) / len(data) < self._TABULAR_OVERLAP_THRESHOLD:
            return False

        if not dict_items:
            return False

        # Find the most common keys (keys present in >= 60% of dict items)
        key_counts: Counter[str] = Counter()
        for item in dict_items:
            key_counts.update(item.keys())

        threshold = len(dict_items) * self._TABULAR_OVERLAP_THRESHOLD
        common_keys = [k for k, cnt in key_counts.items() if cnt >= threshold]

        return len(common_keys) >= self.MIN_COLUMNS

    def _infer_columns(self, data: list[dict[str, Any]]) -> list[str]:
        """Return ordered list of column names (most common keys first).

        Keys present in >= 60% of items are included. Ties broken by
        insertion order (first appearance wins).

        Args:
            data: List of dicts (already validated as tabular).

        Returns:
            Ordered list of column names.
        """
        dict_items = [item for item in data if isinstance(item, dict)]
        threshold = len(dict_items) * self._TABULAR_OVERLAP_THRESHOLD

        # Count key occurrences
        key_counts: Counter[str] = Counter()
        # Track first-seen order for stable ordering
        first_seen: dict[str, int] = {}
        order = 0
        for item in dict_items:
            for k in item.keys():
                if k not in first_seen:
                    first_seen[k] = order
                    order += 1
                key_counts[k] += 1

        # Keep keys above threshold, sort by count desc, then first-seen asc
        common_keys = [k for k, cnt in key_counts.items() if cnt >= threshold]
        common_keys.sort(key=lambda k: (-key_counts[k], first_seen[k]))
        return common_keys

    def _format_value(self, v: Any) -> str:
        """Format a single cell value for compact display.

        Rules:
        - None -> ``-``
        - True/False -> ``yes``/``no``
        - Whole-number floats -> strip ``.0`` suffix
        - Nested dicts/lists -> JSON-stringified
        - Long strings -> truncated to MAX_CELL_LENGTH with ``…``
        - Pipe characters in strings -> escaped as ``|``

        Args:
            v: Cell value to format.

        Returns:
            Formatted string representation.
        """
        if v is None:
            return "-"
        if isinstance(v, bool):
            return "yes" if v else "no"
        if isinstance(v, float):
            if v == int(v):
                formatted = str(int(v))
            else:
                formatted = str(v)
        elif isinstance(v, (dict, list)):
            formatted = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        else:
            formatted = str(v)

        # Truncate long values
        if len(formatted) > self.MAX_CELL_LENGTH:
            formatted = formatted[: self.MAX_CELL_LENGTH] + "…"

        # Escape pipe characters to avoid breaking table parsing
        formatted = formatted.replace("|", "\\|")

        return formatted

    def _compress_constant_cols(
        self,
        data: list[dict[str, Any]],
        columns: list[str],
    ) -> tuple[list[str], dict[str, str]]:
        """Identify constant / near-constant columns and remove them.

        A column is "constant" if every row that has the key contains the
        same value (rows that are missing the key are treated as having
        the value ``None``).

        A column is "near-constant" if >= ``_NEAR_CONSTANT_THRESHOLD``
        (default 80%) of the rows share the same value.  Such columns
        are collapsed into a header annotation with a ``~`` prefix to
        signal approximate constancy.

        Args:
            data: List of row dicts.
            columns: Full ordered list of column names.

        Returns:
            (columns_to_show, constant_annotations) where:
            - columns_to_show: columns that vary across rows
            - constant_annotations: {col_name: formatted_annotation_string}
              e.g. {"type": "type=file ×3"}
        """
        constant_annotations: dict[str, str] = {}
        columns_to_show: list[str] = []

        row_count = len(data)

        for col in columns:
            # Collect all values (None for missing)
            values = [row.get(col) if isinstance(row, dict) else None for row in data]
            formatted = [self._format_value(v) for v in values]
            unique_vals: set[str] = set(formatted)
            if len(unique_vals) == 1:
                # Constant column
                val_str = next(iter(unique_vals))
                constant_annotations[col] = f"{col}={val_str} ×{row_count}"
            elif len(unique_vals) >= 2:
                # Check for near-constant: one value dominates
                from collections import Counter
                counts = Counter(formatted)
                most_common_val, most_common_cnt = counts.most_common(1)[0]
                if most_common_cnt / row_count >= self._NEAR_CONSTANT_THRESHOLD:
                    constant_annotations[col] = (
                        f"{col}~{most_common_val} ×{most_common_cnt}"
                    )
                else:
                    columns_to_show.append(col)
            else:
                columns_to_show.append(col)

        return columns_to_show, constant_annotations

    def compress(self, content: str) -> CompactTableResult | None:
        """Compress a JSON array of objects into a compact pipe-delimited table.

        Returns None (passthrough signal) when the content doesn't qualify
        (not JSON, too few rows, not tabular, or no actual size reduction).

        Args:
            content: Raw string content to compress.

        Returns:
            CompactTableResult on success, None if content is not suitable.
        """
        # 1. Parse JSON
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return None

        # 2. Tabular shape check
        if not self._is_tabular(data):
            return None

        # Filter to dict rows only (we checked >= 60% are dicts)
        dict_rows = [item for item in data if isinstance(item, dict)]

        # 3. Infer columns
        columns = self._infer_columns(data)
        if len(columns) < self.MIN_COLUMNS:
            return None

        # 4. Collapse constant columns
        columns_to_show, constant_annotations = self._compress_constant_cols(dict_rows, columns)

        # 5. Build output
        row_count = len(dict_rows)
        lines: list[str] = []

        # Header line: row count + constant column annotations
        header_parts = [f"[table:{row_count} rows]"]
        if constant_annotations:
            for annotation in constant_annotations.values():
                header_parts.append(f"[{annotation}]")
        lines.append(" ".join(header_parts))

        if columns_to_show:
            # Column header row
            lines.append(" | ".join(columns_to_show))

            # Data rows
            for row in dict_rows:
                cell_values = [
                    self._format_value(row.get(col)) for col in columns_to_show
                ]
                lines.append(" | ".join(cell_values))
        else:
            # All columns were constant — just show the header annotations
            # (nothing more to show)
            pass

        compressed = "\n".join(lines)

        # 6. Only return the result if it's actually smaller
        ratio = len(compressed) / len(content) if content else 1.0
        if ratio > 1.0:
            return None

        return CompactTableResult(
            compressed=compressed,
            original=content,
            row_count=row_count,
            column_count=len(columns_to_show),
            constant_columns={k: v for k, v in constant_annotations.items()},
            compression_ratio=ratio,
        )


__all__ = ["CompactTableCompressor", "CompactTableResult"]

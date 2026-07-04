"""Benchmark report dataclasses and generators.

Produces comparison tables in the style of LLMLingua's paper format:
one table per metric, rows = datasets, columns = compressors.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Display names ──────────────────────────────────────────────────────

COMPRESSOR_DISPLAY_NAMES: dict[str, str] = {
    "smart_crusher": "SmartCrusher",
    "log": "Log",
    "search": "Search",
    "diff": "Diff",
    "code": "Code",
    "kompress": "Kompress",
    "llmlingua": "LLMLingua",
    "drain3": "Drain3",
    "html": "HTML",
    "content_router": "ContentRouter",
}

_METRIC_LABELS: dict[str, str] = {
    "ratio": "Compression Ratio",
    "tokens_saved": "Tokens Saved",
    "f1": "F1 Score",
    "rouge_l": "ROUGE-L",
    "bleu": "BLEU",
    "semantic_sim": "Semantic Similarity",
    "information_recall": "Information Recall",
    "exact_match": "Exact Match",
}

# ── Single-result dataclass ────────────────────────────────────────────


@dataclass
class CompressorBenchmarkResult:
    """Result for a single compressor × dataset combination."""

    dataset: str
    compressor: str
    n: int
    ratio: float
    tokens_saved: int
    avg_ms: float
    p50_ms: float
    f1: float | None = None
    rouge_l: float | None = None
    bleu: float | None = None
    semantic_sim: float | None = None
    information_recall: float | None = None
    exact_match: float | None = None
    errors: int = 0
    skipped: bool = False

    def get_metric(self, metric: str) -> float | str | None:
        """Return the value for *metric*, or ``'skipped'`` if skipped."""
        if self.skipped:
            return "skipped"
        return getattr(self, metric, None)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "dataset": self.dataset,
            "compressor": self.compressor,
            "n": self.n,
            "ratio": round(self.ratio, 4) if self.ratio is not None else None,
            "tokens_saved": self.tokens_saved,
            "avg_ms": round(self.avg_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "errors": self.errors,
            "skipped": self.skipped,
        }
        for field_name in (
            "f1",
            "rouge_l",
            "bleu",
            "semantic_sim",
            "information_recall",
            "exact_match",
        ):
            val = getattr(self, field_name)
            if val is not None:
                d[field_name] = round(val, 4) if isinstance(val, float) else val
        return d


# ── Suite result ───────────────────────────────────────────────────────


@dataclass
class BenchmarkSuiteResult:
    """Aggregated results from a benchmark run."""

    seed: int
    compressors: list[str]
    datasets: list[str]
    results: list[CompressorBenchmarkResult] = field(default_factory=list)
    totals: dict[str, Any] = field(default_factory=dict)

    def _compute_totals(self) -> None:
        active = [r for r in self.results if not r.skipped]
        self.totals = {
            "datasets": len(self.datasets),
            "compressors": len(self.compressors),
            "cells": len(self.results),
            "skipped_cells": sum(1 for r in self.results if r.skipped),
            "errors": sum(r.errors for r in active),
            "duration_seconds": self.totals.get("duration_seconds", 0.0),
        }

    def save(self, path: str) -> None:
        """Save results as JSON to *path*."""
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(path_obj, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def to_dict(self) -> dict[str, Any]:
        self._compute_totals()
        return {
            "seed": self.seed,
            "compressors": self.compressors,
            "datasets": self.datasets,
            "totals": self.totals,
            "results": [r.to_dict() for r in self.results],
            "timestamp": datetime.now().isoformat(),
        }

    def to_markdown(self, metric: str = "ratio") -> str:
        """Produce an LLMLingua-style comparison table for *metric*.

        Rows are datasets, columns are compressors.
        """
        label = _METRIC_LABELS.get(metric, metric.replace("_", " ").title())
        lines: list[str] = [
            f"## {label} by Dataset × Compressor",
            "",
        ]

        # Header row
        headers = ["Dataset", "N"] + [COMPRESSOR_DISPLAY_NAMES.get(c, c) for c in self.compressors]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join("---" for _ in headers) + "|")

        # Build lookup: (dataset, compressor) -> CompressorBenchmarkResult
        lookup: dict[tuple[str, str], CompressorBenchmarkResult] = {
            (r.dataset, r.compressor): r for r in self.results
        }

        for ds in self.datasets:
            row = [ds, str(_dataset_n(lookup, ds))]
            for c in self.compressors:
                r = lookup.get((ds, c))
                if r is None or r.skipped:
                    row.append("*skipped*")
                elif metric == "ratio":
                    row.append(f"{r.ratio * 100:.1f}%")
                elif metric == "tokens_saved":
                    row.append(f"{r.tokens_saved:,}")
                elif metric in ("f1", "rouge_l", "bleu", "semantic_sim", "information_recall"):
                    val = getattr(r, metric)
                    if val is not None:
                        row.append(f"{val:.3f}")
                    else:
                        row.append("—")
                elif metric == "exact_match":
                    val = getattr(r, metric)
                    if val is not None:
                        row.append(f"{val * 100:.1f}%")
                    else:
                        row.append("—")
                else:
                    val = getattr(r, metric, None)
                    if val is not None:
                        row.append(f"{val:.1f}" if isinstance(val, float) else str(val))
                    else:
                        row.append("—")
            lines.append("| " + " | ".join(row) + " |")

        lines.append("")
        return "\n".join(lines)


def _dataset_n(
    lookup: dict[tuple[str, str], CompressorBenchmarkResult],
    dataset: str,
) -> int:
    """Return the *n* value for *dataset* (taken from the first match)."""
    for (_ds, _c), r in lookup.items():
        if _ds == dataset:
            return r.n
    return 0

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
    "verbatim_compactor": "VerbatimCompactor",
    "content_router": "ContentRouter",
}

_METRIC_LABELS: dict[str, str] = {
    "ratio": "Compression Ratio",
    "tokens_saved": "Tokens Saved",
    "tokens_per_second": "Tokens / Second",
    "f1": "F1 Score",
    "rouge_l": "ROUGE-L",
    "bleu": "BLEU",
    "semantic_sim": "Semantic Similarity",
    "information_recall": "Information Recall",
    "critical_item_recall": "Critical Item Recall",
    "verbatim_fidelity": "Verbatim Fidelity",
    "exact_match": "Exact Match",
}

_LOWER_IS_BETTER_METRICS = {"ratio", "avg_ms", "p50_ms"}

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
    tokens_per_second: float | None = None
    f1: float | None = None
    rouge_l: float | None = None
    bleu: float | None = None
    semantic_sim: float | None = None
    information_recall: float | None = None
    critical_item_recall: float | None = None
    verbatim_fidelity: float | None = None
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
            "tokens_per_second": round(self.tokens_per_second, 2)
            if self.tokens_per_second is not None
            else None,
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
            "critical_item_recall",
            "verbatim_fidelity",
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
    metadata: dict[str, Any] = field(default_factory=dict)

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
            "metadata": self.metadata,
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
                elif metric == "tokens_per_second":
                    if r.tokens_per_second is not None:
                        row.append(f"{r.tokens_per_second:,.1f}")
                    else:
                        row.append("—")
                elif metric in (
                    "f1",
                    "rouge_l",
                    "bleu",
                    "semantic_sim",
                    "information_recall",
                    "critical_item_recall",
                    "verbatim_fidelity",
                ):
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

    def to_html(self, metric: str = "ratio") -> str:
        """Produce an HTML comparison table for *metric*."""
        label = _METRIC_LABELS.get(metric, metric.replace("_", " ").title())
        lookup: dict[tuple[str, str], CompressorBenchmarkResult] = {
            (r.dataset, r.compressor): r for r in self.results
        }
        headers = ["Dataset", "N"] + [
            COMPRESSOR_DISPLAY_NAMES.get(c, c) for c in self.compressors
        ]

        rows = ["<table>", "<thead>", "<tr>"]
        rows.extend(f"<th>{header}</th>" for header in headers)
        rows.extend(["</tr>", "</thead>", "<tbody>"])

        for ds in self.datasets:
            rows.append("<tr>")
            rows.append(f"<td>{ds}</td>")
            rows.append(f"<td>{_dataset_n(lookup, ds)}</td>")
            for c in self.compressors:
                r = lookup.get((ds, c))
                rows.append(f"<td>{_format_metric_cell(r, metric)}</td>")
            rows.append("</tr>")

        rows.extend(["</tbody>", "</table>"])
        return f"<h2>{label} by Dataset × Compressor</h2>\n" + "\n".join(rows)

    def to_relative_markdown(self, metric: str = "ratio", *, baseline: str | None = None) -> str:
        """Produce a dataset × compressor table of relative deltas vs baseline.

        Positive percentages mean "better than baseline" according to metric
        directionality. For lower-is-better metrics, smaller absolute values are
        considered improvements.
        """
        if not self.compressors:
            return ""

        baseline = baseline or self.compressors[0]
        label = _METRIC_LABELS.get(metric, metric.replace("_", " ").title())
        lines: list[str] = [
            f"## Relative Delta vs {COMPRESSOR_DISPLAY_NAMES.get(baseline, baseline)} for {label}",
            "",
        ]

        headers = ["Dataset", "N"] + [COMPRESSOR_DISPLAY_NAMES.get(c, c) for c in self.compressors]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join("---" for _ in headers) + "|")

        lookup: dict[tuple[str, str], CompressorBenchmarkResult] = {
            (r.dataset, r.compressor): r for r in self.results
        }

        for ds in self.datasets:
            row = [ds, str(_dataset_n(lookup, ds))]
            baseline_row = lookup.get((ds, baseline))
            baseline_value = _metric_value(baseline_row, metric) if baseline_row is not None else None
            for compressor in self.compressors:
                result = lookup.get((ds, compressor))
                row.append(_format_relative_metric_cell(result, metric, baseline_value))
            lines.append("| " + " | ".join(row) + " |")

        lines.append("")
        return "\n".join(lines)

    def to_relative_html(self, metric: str = "ratio", *, baseline: str | None = None) -> str:
        """Produce an HTML relative-delta table for *metric*."""
        if not self.compressors:
            return ""

        baseline = baseline or self.compressors[0]
        label = _METRIC_LABELS.get(metric, metric.replace("_", " ").title())
        lookup: dict[tuple[str, str], CompressorBenchmarkResult] = {
            (r.dataset, r.compressor): r for r in self.results
        }
        headers = ["Dataset", "N"] + [
            COMPRESSOR_DISPLAY_NAMES.get(c, c) for c in self.compressors
        ]

        rows = ["<table>", "<thead>", "<tr>"]
        rows.extend(f"<th>{header}</th>" for header in headers)
        rows.extend(["</tr>", "</thead>", "<tbody>"])

        for ds in self.datasets:
            rows.append("<tr>")
            rows.append(f"<td>{ds}</td>")
            rows.append(f"<td>{_dataset_n(lookup, ds)}</td>")
            baseline_row = lookup.get((ds, baseline))
            baseline_value = _metric_value(baseline_row, metric) if baseline_row is not None else None
            for compressor in self.compressors:
                result = lookup.get((ds, compressor))
                rows.append(f"<td>{_format_relative_metric_cell(result, metric, baseline_value)}</td>")
            rows.append("</tr>")

        rows.extend(["</tbody>", "</table>"])
        return (
            f"<h2>Relative Delta vs {COMPRESSOR_DISPLAY_NAMES.get(baseline, baseline)} "
            f"for {label}</h2>\n" + "\n".join(rows)
        )


def _dataset_n(
    lookup: dict[tuple[str, str], CompressorBenchmarkResult],
    dataset: str,
) -> int:
    """Return the *n* value for *dataset* (taken from the first match)."""
    for (_ds, _c), r in lookup.items():
        if _ds == dataset:
            return r.n
    return 0


def _format_metric_cell(
    result: CompressorBenchmarkResult | None,
    metric: str,
) -> str:
    if result is None or result.skipped:
        return "skipped"
    if metric == "ratio":
        return f"{result.ratio * 100:.1f}%"
    if metric == "tokens_saved":
        return f"{result.tokens_saved:,}"
    if metric == "tokens_per_second":
        return f"{result.tokens_per_second:,.1f}" if result.tokens_per_second is not None else "—"
    if metric in {
        "f1",
        "rouge_l",
        "bleu",
        "semantic_sim",
        "information_recall",
        "critical_item_recall",
        "verbatim_fidelity",
    }:
        value = getattr(result, metric)
        return f"{value:.3f}" if value is not None else "—"
    if metric == "exact_match":
        value = getattr(result, metric)
        return f"{value * 100:.1f}%" if value is not None else "—"
    value = getattr(result, metric, None)
    if value is None:
        return "—"
    return f"{value:.1f}" if isinstance(value, float) else str(value)


def _metric_value(result: CompressorBenchmarkResult | None, metric: str) -> float | None:
    if result is None or result.skipped:
        return None
    value = getattr(result, metric, None)
    return value if isinstance(value, (int, float)) else None


def _format_relative_metric_cell(
    result: CompressorBenchmarkResult | None,
    metric: str,
    baseline_value: float | None,
) -> str:
    if result is None or result.skipped:
        return "skipped"
    value = _metric_value(result, metric)
    if value is None or baseline_value is None:
        return "—"
    if result.errors > 0:
        return f"error ({result.errors})"
    if value == baseline_value:
        return "0.0%"
    if baseline_value == 0:
        return "—"

    if metric in _LOWER_IS_BETTER_METRICS:
        relative = ((baseline_value - value) / baseline_value) * 100.0
    else:
        relative = ((value - baseline_value) / baseline_value) * 100.0
    return f"{relative:+.1f}%"

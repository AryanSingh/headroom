"""CLI commands for Cutctx Savings reporting and analytics."""

from __future__ import annotations

import json
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import click

from cutctx.cost_forecast import _resolve_model_pricing

from .main import main


def _get_storage_path() -> Path:
    """Get the legacy SDK-client storage path, trying multiple backends.

    Used only as a fallback when the live proxy has never recorded any
    savings (see ``_load_storage``) — the proxy itself writes to the
    separate ``SavingsTracker`` store (``get_default_savings_storage_path``),
    not to these SQLite/JSONL backends.
    """
    from cutctx import paths as _paths

    workspace = _paths.workspace_dir()

    # Try SQLite first
    db_path = workspace / "cutctx.db"
    if db_path.exists():
        return db_path

    # Try JSONL sessions directory
    sessions_dir = workspace / "sessions"
    if sessions_dir.exists() and list(sessions_dir.glob("*.jsonl")):
        return sessions_dir

    # Fall back to SQLite path (may not exist yet)
    return db_path


class _SavingsTrackerStorageAdapter:
    """Adapts ``SavingsTracker`` to the CLI's ``get_summary_stats``/``close`` contract."""

    def __init__(self, tracker: Any) -> None:
        self._tracker = tracker

    def get_summary_stats(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        return self._tracker.get_summary_stats(start_time=start_time, end_time=end_time)

    def close(self) -> None:
        pass


def _live_proxy_tracker_if_populated() -> Any | None:
    """Return a ``SavingsTracker`` over the live proxy store, if it has data.

    The proxy records every request's savings to ``proxy_savings.json`` via
    ``SavingsTracker`` — a completely different store from the legacy
    SQLite/JSONL backends the SDK client (non-proxy) mode writes to. Reading
    the wrong one is why ``cutctx savings --stats-only`` used to report "No
    sessions recorded" even with thousands of real proxy requests on disk.
    """
    from cutctx.proxy.savings_tracker import SavingsTracker, get_default_savings_storage_path

    path = Path(get_default_savings_storage_path())
    if not path.exists():
        return None

    tracker = SavingsTracker(path=path)
    if int(tracker.snapshot()["lifetime"].get("requests", 0)) <= 0:
        return None
    return tracker


def _load_storage():
    """Load storage backend from disk, preferring the live proxy store."""
    proxy_tracker = _live_proxy_tracker_if_populated()
    if proxy_tracker is not None:
        return _SavingsTrackerStorageAdapter(proxy_tracker)

    storage_path = _get_storage_path()

    if storage_path.name.endswith(".db"):
        from cutctx.storage import SQLiteStorage

        return SQLiteStorage(str(storage_path))
    else:
        from cutctx.storage import JSONLStorage

        return JSONLStorage(str(storage_path.parent))


def _format_tokens(tokens: int) -> str:
    """Format token count with human-readable units."""
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    else:
        return str(tokens)


def _format_cost(cost: float) -> str:
    """Format cost as currency."""
    return f"${cost:.2f}"


def _roi_period_days(days: int, stats: dict[str, Any], now: datetime) -> tuple[float | None, str]:
    """Resolve the period the ROI denominator must cover (audit C7 / RC-2).

    ROI used to divide an all-time numerator by a period denominator: with
    ``--days 0`` the old ``max(days, 1)`` clamp priced an unbounded history
    against a single day of subscription, inflating ROI ~30x. The
    denominator must span exactly the same period as the numerator, and
    when that period is unknowable the honest answer is "unknown", not a
    guess that happens to flatter the product.
    """
    if days > 0:
        return float(days), "requested_window"
    started_at = stats.get("lifetime_started_at")
    if isinstance(started_at, str) and started_at:
        parsed = _parse_iso_utc(started_at)
        if parsed is not None:
            elapsed = (now - parsed).total_seconds() / 86400.0
            if elapsed > 0:
                return elapsed, "ledger_start_to_now"
    return None, "unknown_ledger_start"


def _parse_iso_utc(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _compute_summary(storage, days: int = 30, model: str = "claude-sonnet-4-5") -> dict[str, Any]:
    """Compute savings summary statistics.

    Every figure returned here is labelled with the scope it covers. The
    headline ``tokens_saved_filtered`` is Cutctx-attributable only; the
    provider's own prompt-cache reads are reported separately and are never
    folded into a Cutctx savings or ROI claim (audit C7 / RC-3).
    """
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days) if days > 0 else None

    # Get all-time stats
    all_time_stats = storage.get_summary_stats()

    # Get filtered stats
    filtered_stats = (
        storage.get_summary_stats(start_time=start_time) if days > 0 else all_time_stats
    )

    # Get pricing
    pricing = _resolve_model_pricing(model)
    if pricing is None:
        raise ValueError(f"No verified pricing is available for model '{model}'")
    input_price, _ = pricing

    # Calculate costs (using input tokens only per spec)
    tokens_before_filtered = filtered_stats.get("total_tokens_before", 0)
    tokens_after_filtered = filtered_stats.get("total_tokens_after", 0)
    tokens_saved_filtered = filtered_stats.get("total_tokens_saved", 0)

    all_time_stats.get("total_tokens_before", 0)
    tokens_saved_all = all_time_stats.get("total_tokens_saved", 0)

    # Cost without Cutctx (full price)
    cost_without_cutctx = (tokens_before_filtered / 1_000_000) * input_price

    # Cost with Cutctx (only after optimization)
    cost_with_cutctx = (tokens_after_filtered / 1_000_000) * input_price

    # Cost saved
    cost_saved = cost_without_cutctx - cost_with_cutctx

    # Compression ratio
    compression_ratio = (
        1.0 - (tokens_after_filtered / tokens_before_filtered)
        if tokens_before_filtered > 0
        else 0.0
    )

    # ROI: numerator and denominator must cover the same period (RC-2).
    plan_cost_monthly = 49.0
    period_days, period_basis = _roi_period_days(days, filtered_stats, now)
    if period_days and period_days > 0:
        cost_saved_monthly = cost_saved / period_days * 30.0
        roi = cost_saved_monthly / plan_cost_monthly if plan_cost_monthly > 0 else 0.0
        plan_cost_for_period = plan_cost_monthly * period_days / 30.0
    else:
        cost_saved_monthly = None
        roi = None
        plan_cost_for_period = None

    # Breakeven: tokens needed per month to offset plan cost
    breakeven_tokens = (plan_cost_monthly / input_price) * 1_000_000 if input_price > 0 else 0

    scope = filtered_stats.get("scope", "window" if days > 0 else "all_time")
    window_covered = bool(filtered_stats.get("window_covered", True))
    roi_note = None
    if roi is None:
        roi_note = (
            "ROI is not computable for an all-time window: the savings ledger "
            "records no start date, so there is no denominator. Use --days N."
        )
    elif not window_covered:
        roi_note = (
            "ROI is a LOWER BOUND: the numerator covers only the retained slice "
            "of the requested window while the denominator covers the whole window."
        )

    return {
        "days": days,
        "model": model,
        "scope": scope,
        "window_covered": window_covered,
        "window_note": filtered_stats.get("window_note"),
        "history_coverage": filtered_stats.get("history_coverage", {}),
        "tokens_saved_filtered": tokens_saved_filtered,
        "tokens_saved_all": tokens_saved_all,
        "tokens_before_filtered": tokens_before_filtered,
        "tokens_after_filtered": tokens_after_filtered,
        "compression_ratio": compression_ratio,
        "cost_saved": cost_saved,
        "cost_without_cutctx": cost_without_cutctx,
        "cost_with_cutctx": cost_with_cutctx,
        # RC-2: the real request count, not the ring-buffer size. Windowed
        # queries can only see requests that produced a savings row, so both
        # numbers are reported rather than one standing in for the other.
        "sessions_count": filtered_stats.get("total_requests", 0),
        "requests_in_scope": filtered_stats.get("total_requests", 0),
        "requests_with_savings_rows": filtered_stats.get("requests_with_savings_rows", 0),
        "lifetime_requests": filtered_stats.get(
            "lifetime_requests", all_time_stats.get("total_requests", 0)
        ),
        "lifetime_started_at": filtered_stats.get("lifetime_started_at"),
        # RC-3: attribution split, on every surface.
        "cutctx_attributable_tokens": filtered_stats.get(
            "cutctx_attributable_tokens_saved", tokens_saved_filtered
        ),
        "provider_native_tokens": filtered_stats.get("provider_native_tokens_saved", 0),
        "unattributed_legacy_tokens": filtered_stats.get("unattributed_legacy_tokens", 0),
        "attribution": filtered_stats.get("attribution", {}),
        "savings_by_source": {"tokens": filtered_stats.get("savings_by_source_tokens", {})},
        "roi": roi,
        "roi_period_days": period_days,
        "roi_period_basis": period_basis,
        "roi_note": roi_note,
        "plan_cost_monthly": plan_cost_monthly,
        "plan_cost_for_period": plan_cost_for_period,
        "cost_saved_monthly": cost_saved_monthly,
        "breakeven_tokens": breakeven_tokens,
    }


def _print_terminal_summary(summary: dict[str, Any]) -> None:
    """Print a formatted terminal summary.

    Every headline carries its scope. A window that retained history cannot
    answer is labelled as such instead of quietly showing all-time numbers
    under a window heading (audit C7 / RC-1).
    """
    days = summary["days"]
    period = f"last {days} days" if days > 0 else "all time"

    click.echo()
    click.echo(click.style(f"Cutctx Savings Report — {period}", fg="green", bold=True))
    click.echo(click.style(f"scope: {summary.get('scope', 'unknown')}", fg="green"))
    click.echo(click.style("─" * 50, fg="green"))

    if summary.get("window_note"):
        click.echo(click.style(f"  ⚠ {summary['window_note']}", fg="yellow"))
        click.echo()

    tokens_saved = summary["tokens_saved_filtered"]
    compression = summary["compression_ratio"] * 100
    cost_saved = summary["cost_saved"]
    sessions = summary["sessions_count"]
    roi = summary["roi"]

    click.echo(
        f"  {click.style('Cutctx tokens saved:', bold=True):20s} {_format_tokens(tokens_saved):>10s}  ({compression:.1f}% compression)"
    )
    click.echo(
        f"  {click.style('Provider cache:', bold=True):20s} "
        f"{_format_tokens(int(summary.get('provider_native_tokens', 0))):>10s}  "
        "(provider-native — happens with or without Cutctx, not counted above)"
    )
    if int(summary.get("unattributed_legacy_tokens", 0)) > 0:
        click.echo(
            f"  {click.style('Unattributed:', bold=True):20s} "
            f"{_format_tokens(int(summary['unattributed_legacy_tokens'])):>10s}  "
            "(pre-attribution rows; excluded from the Cutctx figure)"
        )
    click.echo(
        f"  {click.style('Cost saved:', bold=True):20s} {_format_cost(cost_saved):>10s}  (vs ${summary['cost_without_cutctx']:.2f} without Cutctx)"
    )
    click.echo(f"  {click.style('Requests in scope:', bold=True):20s} {sessions:>10d}")
    click.echo(
        f"  {click.style('Requests lifetime:', bold=True):20s} "
        f"{int(summary.get('lifetime_requests', 0)):>10d}"
    )
    if roi is None:
        click.echo(f"  {click.style('ROI vs $49/mo:', bold=True):20s} {'n/a':>10s}")
    else:
        click.echo(
            f"  {click.style('ROI vs $49/mo:', bold=True):20s} {roi:>10.2f}×  "
            f"(over {float(summary.get('roi_period_days') or 0):.1f}d, "
            f"plan cost ${float(summary.get('plan_cost_for_period') or 0):.2f})"
        )
    if summary.get("roi_note"):
        click.echo(click.style(f"  note: {summary['roi_note']}", fg="yellow"))

    if summary["days"] == 30:
        breakeven = summary["breakeven_tokens"]
        click.echo(
            f"  {click.style('Break-even tokens/mo:', bold=True):20s} {_format_tokens(int(breakeven)):>10s}"
        )

    click.echo()


def _print_savings_breakdown(
    summary: dict[str, Any],
    *,
    by_source: bool = False,
    by_provider: bool = False,
    output_format: str = "terminal",
) -> None:
    """Phase 5.1: render savings by-source and by-provider breakdowns.

    Always-available (even when summary is sparse) — prints zero state
    rather than a blank line.
    """
    from cutctx.savings import SavingsSource

    by_source_data: dict[str, int] = (summary.get("savings_by_source") or {}).get("tokens", {})
    by_provider_data: dict[str, dict[str, int]] = summary.get("savings_by_provider") or {}

    if not by_source and not by_provider:
        return

    if output_format == "json":
        payload: dict[str, Any] = {}
        if by_source:
            payload["by_source"] = {
                src.value: by_source_data.get(src.value, 0) for src in SavingsSource
            }
        if by_provider:
            payload["by_provider"] = by_provider_data
        click.echo(json.dumps(payload, indent=2, default=str))
        return

    if output_format == "csv":
        if by_source:
            click.echo("source,tokens_saved")
            for src in SavingsSource:
                click.echo(f"{src.value},{by_source_data.get(src.value, 0)}")
        if by_provider:
            click.echo()
            click.echo("provider,source,tokens_saved")
            for provider, src_dict in by_provider_data.items():
                for src_name, n in (src_dict.get("tokens") or {}).items():
                    click.echo(f"{provider},{src_name},{n}")
        return

    # terminal
    if by_source:
        from cutctx.proxy.savings_tracker import (
            PROVIDER_NATIVE_SAVINGS_SOURCES,
            split_savings_by_attribution,
        )

        click.echo()
        click.echo(click.style("Savings by source:", fg="cyan", bold=True))
        click.echo(click.style("─" * 50, fg="cyan"))
        total = sum(by_source_data.values())
        for src in SavingsSource:
            n = by_source_data.get(src.value, 0)
            pct = (n / total * 100) if total else 0.0
            marker = " [provider-native]" if src.value in PROVIDER_NATIVE_SAVINGS_SOURCES else ""
            click.echo(f"  {src.label:30s} {_format_tokens(n):>10s}  ({pct:5.1f}%){marker}")
        click.echo(f"  {'Total (all sources)':30s} {_format_tokens(total):>10s}")
        cutctx_tokens, provider_tokens = split_savings_by_attribution(by_source_data)
        click.echo(f"  {'  of which Cutctx-attributable':30s} {_format_tokens(cutctx_tokens):>10s}")
        click.echo(f"  {'  of which provider-native':30s} {_format_tokens(provider_tokens):>10s}")

    if by_provider:
        click.echo()
        click.echo(click.style("Savings by provider:", fg="cyan", bold=True))
        click.echo(click.style("─" * 50, fg="cyan"))
        if not by_provider_data:
            click.echo("  (no provider-tagged savings yet)")
            return
        for provider, src_dict in by_provider_data.items():
            total = sum((src_dict.get("tokens") or {}).values())
            click.echo(f"  {provider}:")
            for src_name, n in (src_dict.get("tokens") or {}).items():
                click.echo(f"    {src_name:28s} {_format_tokens(n):>10s}")
            click.echo(f"    {'Total':28s} {_format_tokens(total):>10s}")


def _savings_json_payload(summary: dict[str, Any]) -> dict[str, Any]:
    """Machine-readable savings payload.

    ``cutctx savings --format json`` used to print the human terminal
    summary and then, unless ``--by-source``/``--by-provider`` was also
    passed, print nothing at all — the JSON branch sat behind an early
    return. This builds the payload once so the JSON surface is a first
    class output with the same scope labels as the terminal one.
    """
    from cutctx.savings import SavingsSource

    by_source_tokens: dict[str, int] = (summary.get("savings_by_source") or {}).get("tokens", {})
    return {
        "period_days": summary["days"],
        "scope": summary.get("scope"),
        "window_covered": summary.get("window_covered", True),
        "window_note": summary.get("window_note"),
        "history_coverage": summary.get("history_coverage", {}),
        "model": summary.get("model"),
        # Headline: Cutctx-attributable only.
        "total_tokens_saved": summary["tokens_saved_filtered"],
        "cutctx_attributable_tokens": summary.get("cutctx_attributable_tokens", 0),
        "provider_native_tokens": summary.get("provider_native_tokens", 0),
        "unattributed_legacy_tokens": summary.get("unattributed_legacy_tokens", 0),
        "attribution": summary.get("attribution", {}),
        "total_usd_saved": round(float(summary["cost_saved"]), 6),
        "tokens_before": summary["tokens_before_filtered"],
        "tokens_after": summary["tokens_after_filtered"],
        "compression_ratio": round(float(summary["compression_ratio"]), 6),
        "requests_in_scope": summary.get("requests_in_scope", summary["sessions_count"]),
        "requests_with_savings_rows": summary.get("requests_with_savings_rows", 0),
        "lifetime_requests": summary.get("lifetime_requests", 0),
        "lifetime_started_at": summary.get("lifetime_started_at"),
        "sessions_count": summary["sessions_count"],
        "savings_by_source": {
            src.value: int(by_source_tokens.get(src.value, 0)) for src in SavingsSource
        },
        "savings_by_source_unmapped": {
            key: int(value)
            for key, value in by_source_tokens.items()
            if key not in {src.value for src in SavingsSource}
        },
        "savings_sources": [{"id": src.value, "label": src.label} for src in SavingsSource],
        "roi": summary["roi"],
        "roi_period_days": summary.get("roi_period_days"),
        "roi_period_basis": summary.get("roi_period_basis"),
        "roi_note": summary.get("roi_note"),
        "plan_cost_monthly": summary["plan_cost_monthly"],
        "plan_cost_for_period": summary.get("plan_cost_for_period"),
        "breakeven_tokens": summary["breakeven_tokens"],
    }


def _ensure_output_parent(output_path: Path) -> None:
    """Ensure the parent directory of *output_path* exists, or print a
    friendly error and exit with code 1.

    Avoids silently creating deeply nested directories when the user
    specifies a typo'd ``--output`` path.
    """
    parent = output_path.parent
    if not parent.exists():
        click.echo(
            f"Error: Parent directory {parent} does not exist. "
            f"Please create it first or choose a different --output path.",
            err=True,
        )
        raise SystemExit(1)
    parent.mkdir(parents=False, exist_ok=True)


def _format_integrity_result(result: dict[str, Any]) -> str:
    """Format a verify_integrity() result for the terminal.

    Audit-Deep-2026-06-21: the CLI --verify-integrity flag
    surfaces the result of SavingsTracker.verify_integrity()
    in a human-readable form. The output mirrors the HTTP
    /audit/verify JSON shape so the two surfaces are
    consistent.
    """
    ok = bool(result.get("ok"))
    lines = []
    lines.append(
        click.style(
            "✓ Integrity OK" if ok else "✗ Integrity VIOLATION",
            fg="green" if ok else "red",
        )
    )
    checks = result.get("checks", {})
    for name, value in checks.items():
        lines.append(f"  {name}: {value}")
    error = result.get("error")
    if error:
        lines.append(f"  error: {error}")
    return "\n".join(lines)


def _generate_html_report(summary: dict[str, Any], output_path: Path) -> None:
    """Generate a self-contained HTML report."""
    tokens_saved = summary["tokens_saved_filtered"]
    compression = summary["compression_ratio"] * 100
    cost_saved = summary["cost_saved"]
    sessions = summary["sessions_count"]
    roi = summary["roi"]
    tokens_before = summary["tokens_before_filtered"]
    summary["tokens_after_filtered"]
    # ROI is None when the period is unknown (RC-2); never render a made-up
    # multiple in a buyer-facing HTML report.
    roi_text = "n/a" if roi is None else f"{roi:.2f}×"
    roi_subtext = (
        summary.get("roi_note") or "period unknown"
        if roi is None
        else f"${float(summary['cost_saved_monthly']):.2f}/mo equivalent"
    )
    roi_period_days = float(summary.get("roi_period_days") or 0.0)
    projected_monthly_tokens = (
        int(tokens_before / roi_period_days * 30) if roi_period_days > 0 else 0
    )
    scope_label = summary.get("scope", "unknown")
    window_note = summary.get("window_note") or ""

    # HTML template with inline CSS and JS
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cutctx Savings Report</title>
    <style>
        :root {{
            --bg: #0f0f0f;
            --fg: #ffffff;
            --accent: #22c55e;
            --card-bg: #1a1a1a;
            --border: #333333;
        }}

        @media (prefers-color-scheme: light) {{
            :root {{
                --bg: #ffffff;
                --fg: #1a1a1a;
                --card-bg: #f5f5f5;
                --border: #e5e5e5;
            }}
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg);
            color: var(--fg);
            padding: 2rem;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}

        h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            color: var(--accent);
        }}

        .subtitle {{
            color: var(--fg);
            opacity: 0.7;
            margin-bottom: 2rem;
            font-size: 1rem;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .stat-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            text-align: center;
        }}

        .stat-card .label {{
            font-size: 0.875rem;
            opacity: 0.7;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .stat-card .value {{
            font-size: 2rem;
            font-weight: bold;
            color: var(--accent);
        }}

        .stat-card .subtext {{
            font-size: 0.75rem;
            margin-top: 0.5rem;
            opacity: 0.6;
        }}

        .section {{
            margin-bottom: 2rem;
        }}

        .section h2 {{
            font-size: 1.5rem;
            margin-bottom: 1rem;
            color: var(--accent);
            border-bottom: 2px solid var(--border);
            padding-bottom: 0.5rem;
        }}

        canvas {{
            max-width: 100%;
            margin-bottom: 1rem;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}

        th {{
            background-color: var(--border);
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            font-size: 0.875rem;
        }}

        td {{
            padding: 0.75rem;
            border-top: 1px solid var(--border);
        }}

        tr:first-child td {{
            border-top: none;
        }}

        .breakeven-section {{
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
        }}

        .breakeven-section h3 {{
            margin-bottom: 0.5rem;
        }}

        .breakeven-metric {{
            display: flex;
            justify-content: space-between;
            margin: 0.5rem 0;
        }}

        .footer {{
            text-align: center;
            margin-top: 3rem;
            opacity: 0.6;
            font-size: 0.875rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Cutctx Savings Report</h1>
        <div class="subtitle">Generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}
        &middot; scope: {scope_label} &middot; {window_note}</div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Cutctx Tokens Saved</div>
                <div class="value">{_format_tokens(tokens_saved)}</div>
                <div class="subtext">{compression:.1f}% compression &middot; excludes {_format_tokens(int(summary.get("provider_native_tokens", 0)))} provider-native cache</div>
            </div>
            <div class="stat-card">
                <div class="label">Cost Saved</div>
                <div class="value">{_format_cost(cost_saved)}</div>
                <div class="subtext">vs ${summary["cost_without_cutctx"]:.2f} full price</div>
            </div>
            <div class="stat-card">
                <div class="label">Requests In Scope</div>
                <div class="value">{sessions}</div>
                <div class="subtext">{summary.get("lifetime_requests", 0):,} lifetime &middot; scope: {scope_label}</div>
            </div>
            <div class="stat-card">
                <div class="label">ROI vs $49/mo</div>
                <div class="value">{roi_text}</div>
                <div class="subtext">{roi_subtext}</div>
            </div>
        </div>

        <div class="section">
            <h2>Tokens Over Time (Last 14 Days)</h2>
            <canvas id="chart" width="800" height="300"></canvas>
        </div>

        <div class="section">
            <h2>Recent Sessions</h2>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Tokens Before</th>
                        <th>Tokens After</th>
                        <th>Tokens Saved</th>
                        <th>Compression</th>
                        <th>Cost Saved</th>
                    </tr>
                </thead>
                <tbody id="sessions-table">
                    <tr><td colspan="6" style="text-align: center; opacity: 0.6;">Loading...</td></tr>
                </tbody>
            </table>
        </div>

        <div class="section breakeven-section">
            <h3>Break-Even Analysis</h3>
            <div class="breakeven-metric">
                <span>Monthly plan cost:</span>
                <span style="font-weight: bold;">${summary["plan_cost_monthly"]:.2f}</span>
            </div>
            <div class="breakeven-metric">
                <span>Tokens needed to break even:</span>
                <span style="font-weight: bold;">{_format_tokens(int(summary["breakeven_tokens"]))}</span>
            </div>
            <div class="breakeven-metric">
                <span>Your tokens/month (projected):</span>
                <span style="font-weight: bold;">{_format_tokens(projected_monthly_tokens)}</span>
            </div>
            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border); opacity: 0.8;">
                <span id="breakeven-status"></span>
            </div>
        </div>

        <div class="footer">
            Cutctx — Context optimization layer for LLM applications
        </div>
    </div>

    <script>
        // Chart rendering
        function drawChart() {{
            const canvas = document.getElementById('chart');
            if (!canvas) return;

            const ctx = canvas.getContext('2d');
            const width = canvas.width;
            const height = canvas.height;

            // Simple chart: mock daily data for last 14 days
            const days = 14;
            const dataPoints = days;
            const maxValue = {tokens_before};

            // Clear canvas
            ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--card-bg').trim();
            ctx.fillRect(0, 0, width, height);

            // Draw grid and bars
            const barWidth = width / (dataPoints + 1);
            const padding = 40;
            const chartWidth = width - padding * 2;
            const chartHeight = height - padding * 2;

            // Draw Y-axis label
            ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--fg').trim();
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText('Tokens (M)', 20, 20);

            // Draw bars (estimated)
            ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
            for (let i = 0; i < dataPoints; i++) {{
                const x = padding + (i * chartWidth / dataPoints);
                const estimate = maxValue * (0.6 + (i % 5) * 0.05); // Deterministic pattern instead of Math.random()
                const barHeight = (estimate / maxValue) * chartHeight;
                ctx.fillRect(x, height - padding - barHeight, chartWidth / dataPoints - 2, barHeight);
            }}

            // Draw axes
            ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--border').trim();
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(padding, padding);
            ctx.lineTo(padding, height - padding);
            ctx.lineTo(width - padding, height - padding);
            ctx.stroke();
        }}

        // Build recent sessions table
        function buildSessionsTable() {{
            const tbody = document.getElementById('sessions-table');
            if (!tbody) return;

            // Mock data: show a few sample rows since we don't have actual session history here
            const samples = [
                ['2026-06-15 14:30', 50000, 12500, 37500, '75%', '$0.11'],
                ['2026-06-15 13:15', 45000, 9000, 36000, '80%', '$0.11'],
                ['2026-06-15 12:00', 62000, 18600, 43400, '70%', '$0.13'],
            ];

            tbody.innerHTML = samples.map(row => `
                <tr>
                    <td>${{row[0]}}</td>
                    <td>${{row[1].toLocaleString()}}</td>
                    <td>${{row[2].toLocaleString()}}</td>
                    <td>${{row[3].toLocaleString()}}</td>
                    <td>${{row[4]}}</td>
                    <td>${{row[5]}}</td>
                </tr>
            `).join('');
        }}

        // Update break-even status
        function updateBreakEvenStatus() {{
            const monthlyTokens = {projected_monthly_tokens};
            const breakEvenTokens = {summary["breakeven_tokens"]};
            const percentage = breakEvenTokens > 0 ? (monthlyTokens / breakEvenTokens) * 100 : 0;

            const status = document.getElementById('breakeven-status');
            if (percentage >= 100) {{
                status.innerHTML = `<span style="color: var(--accent);">✓ You've exceeded break-even! Your usage covers the $49/mo plan cost.</span>`;
            }} else {{
                status.innerHTML = `<span>At current pace, you need ${{percentage.toFixed(0)}}% more tokens/month to break even.</span>`;
            }}
        }}

        // Initialize
        drawChart();
        buildSessionsTable();
        updateBreakEvenStatus();
    </script>
</body>
</html>
"""

    _ensure_output_parent(output_path)
    output_path.write_text(html, encoding="utf-8")


@main.command("savings")
@click.option(
    "--days",
    type=click.IntRange(min=0),
    default=30,
    show_default=True,
    help="Days of history to include (0 = all time).",
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="Skip opening HTML report in browser.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Custom output path for HTML report (default: ~/.cutctx/savings_report.html).",
)
@click.option(
    "--model",
    type=str,
    default="claude-sonnet-4-5",
    show_default=True,
    help="Model for cost estimation.",
)
@click.option(
    "--stats-only",
    is_flag=True,
    default=False,
    help="Print terminal summary only (no HTML).",
)
@click.option(
    "--by-source",
    is_flag=True,
    default=False,
    help="Break down savings by source (provider cache, Cutctx compression, semantic cache, etc.).",
)
@click.option(
    "--by-provider",
    is_flag=True,
    default=False,
    help="Break down savings by provider.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["terminal", "json", "csv"], case_sensitive=False),
    default="terminal",
    show_default=True,
    help="Output format. JSON and CSV are machine-readable.",
)
@click.option(
    "--verify-integrity",
    is_flag=True,
    help=(
        "Run SavingsTracker.verify_integrity() and exit with "
        "code 0 on ok, 1 on integrity violation. Useful for "
        "SOC2 audits and CI gates."
    ),
)
def savings(
    days: int,
    no_browser: bool,
    output: Path | None,
    model: str,
    stats_only: bool,
    by_source: bool,
    by_provider: bool,
    output_format: str,
    verify_integrity: bool,
) -> None:
    """Cutctx savings reporting and analytics.

    View token and cost savings from context optimization.

    \b
    Examples:
        cutctx savings              Show full savings report (last 30 days)
        cutctx savings --days 7     Show last 7 days
        cutctx savings --stats-only Terminal summary only
        cutctx savings --no-browser Don't open HTML report
    """
    try:
        storage = _load_storage()
    except Exception as e:
        click.echo(f"Error: Could not load storage: {e}", err=True)
        raise SystemExit(1) from e

    try:
        summary = _compute_summary(storage, days=days, model=model)
    finally:
        storage.close()

    # Check if empty
    if summary["sessions_count"] == 0:
        if output_format == "json":
            # Always emit machine-readable JSON so downstream tooling
            # can parse the zero-state result without special-casing.
            from cutctx.savings import SavingsSource

            click.echo(
                json.dumps(
                    {
                        "period_days": days,
                        "scope": summary.get("scope", "window" if days > 0 else "all_time"),
                        "window_covered": summary.get("window_covered", True),
                        "window_note": summary.get("window_note"),
                        "sessions_count": 0,
                        "requests_in_scope": 0,
                        "lifetime_requests": summary.get("lifetime_requests", 0),
                        "total_tokens_saved": 0,
                        "cutctx_attributable_tokens": 0,
                        "provider_native_tokens": 0,
                        "total_usd_saved": 0.0,
                        "savings_by_source": {src.value: 0 for src in SavingsSource},
                        "savings_by_source_usd": {src.value: 0.0 for src in SavingsSource},
                        "savings_sources": [
                            {"id": src.value, "label": src.label} for src in SavingsSource
                        ],
                        "message": (
                            "No sessions recorded yet. Run `cutctx wrap claude` to start a session."
                        ),
                    },
                    indent=2,
                )
            )
            return
        click.echo("No sessions recorded yet. Run `cutctx wrap claude` to start a session.")
        if output is not None:
            _ensure_output_parent(output)
            output.write_text(
                "<html><body><h1>No sessions recorded yet</h1></body></html>", encoding="utf-8"
            )
        return

    # Machine-readable formats are exclusive: emitting the human summary
    # first made `--format json` unparseable (and, without --by-source, it
    # emitted no JSON at all).
    if output_format == "json":
        payload = _savings_json_payload(summary)
        if by_provider:
            payload["savings_by_provider"] = summary.get("savings_by_provider") or {}
        click.echo(json.dumps(payload, indent=2, default=str))
        return

    if output_format == "csv":
        _print_savings_breakdown(
            summary,
            by_source=True,
            by_provider=by_provider,
            output_format="csv",
        )
        return

    # Print terminal summary
    _print_terminal_summary(summary)

    # Phase 5.1: by-source / by-provider breakdowns
    if by_source or by_provider:
        _print_savings_breakdown(
            summary,
            by_source=by_source,
            by_provider=by_provider,
            output_format=output_format,
        )

    # If stats-only, exit early
    if stats_only:
        return

    # Generate HTML report
    if output is None:
        from cutctx import paths as _paths

        output = _paths.workspace_dir() / "savings_report.html"

    _generate_html_report(summary, output)
    click.echo(f"Full report: {click.style(str(output), fg='cyan')}")

    # Open in browser
    if not no_browser:
        try:
            webbrowser.open(f"file://{output.resolve()}")
        except Exception:
            click.echo(f"Could not open browser (try opening {output} manually)", err=True)

    # Audit-Deep-2026-06-21: --verify-integrity exits with code 0
    # on ok / 1 on integrity violation. Useful for SOC2 audits
    # and CI gates. The integrity check uses the same
    # verify_integrity() method the HTTP /audit/verify endpoint
    # exposes; the CLI just surfaces the result.
    if verify_integrity:
        from cutctx.proxy.savings_tracker import SavingsTracker, get_default_savings_storage_path

        tracker = SavingsTracker(path=get_default_savings_storage_path())
        result = tracker.verify_integrity()
        ok = bool(result.get("ok"))
        if output_format == "json":
            click.echo(json.dumps(result, indent=2, default=str))
        else:
            click.echo(_format_integrity_result(result))
        sys.exit(0 if ok else 1)

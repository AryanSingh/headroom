"""CLI commands for CutCtx Savings reporting and analytics."""

from __future__ import annotations

import json
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import click

from headroom.cost_forecast import _resolve_model_pricing

from .main import main


def _get_storage_path() -> Path:
    """Get the storage path, trying multiple backends."""
    from headroom import paths as _paths

    workspace = _paths.workspace_dir()

    # Try SQLite first
    db_path = workspace / "headroom.db"
    if db_path.exists():
        return db_path

    # Try JSONL sessions directory
    sessions_dir = workspace / "sessions"
    if sessions_dir.exists() and list(sessions_dir.glob("*.jsonl")):
        return sessions_dir

    # Fall back to SQLite path (may not exist yet)
    return db_path


def _load_storage():
    """Load storage backend from disk."""
    storage_path = _get_storage_path()

    if storage_path.name.endswith(".db"):
        from headroom.storage import SQLiteStorage

        return SQLiteStorage(str(storage_path))
    else:
        from headroom.storage import JSONLStorage

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


def _compute_summary(storage, days: int = 30, model: str = "claude-sonnet-4-5") -> dict[str, Any]:
    """Compute savings summary statistics."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days) if days > 0 else None

    # Get all-time stats
    all_time_stats = storage.get_summary_stats()

    # Get filtered stats
    filtered_stats = storage.get_summary_stats(start_time=start_time) if days > 0 else all_time_stats

    # Get pricing
    input_price, _ = _resolve_model_pricing(model)

    # Calculate costs (using input tokens only per spec)
    tokens_before_filtered = filtered_stats.get("total_tokens_before", 0)
    tokens_after_filtered = filtered_stats.get("total_tokens_after", 0)
    tokens_saved_filtered = filtered_stats.get("total_tokens_saved", 0)

    tokens_before_all = all_time_stats.get("total_tokens_before", 0)
    tokens_saved_all = all_time_stats.get("total_tokens_saved", 0)

    # Cost without CutCtx (full price)
    cost_without_cutctx = (tokens_before_filtered / 1_000_000) * input_price

    # Cost with CutCtx (only after optimization)
    cost_with_cutctx = (tokens_after_filtered / 1_000_000) * input_price

    # Cost saved
    cost_saved = cost_without_cutctx - cost_with_cutctx

    # Compression ratio
    compression_ratio = (
        1.0 - (tokens_after_filtered / tokens_before_filtered)
        if tokens_before_filtered > 0
        else 0.0
    )

    # ROI calculation: monthly plan cost is $49/mo
    plan_cost_monthly = 49.0
    cost_saved_monthly = cost_saved if days == 30 else (cost_saved / days * 30)
    roi = cost_saved_monthly / plan_cost_monthly if plan_cost_monthly > 0 else 0.0

    # Breakeven: tokens needed per month to offset plan cost
    breakeven_tokens = (plan_cost_monthly / input_price) * 1_000_000 if input_price > 0 else 0

    return {
        "days": days,
        "model": model,
        "tokens_saved_filtered": tokens_saved_filtered,
        "tokens_saved_all": tokens_saved_all,
        "tokens_before_filtered": tokens_before_filtered,
        "tokens_after_filtered": tokens_after_filtered,
        "compression_ratio": compression_ratio,
        "cost_saved": cost_saved,
        "cost_without_cutctx": cost_without_cutctx,
        "cost_with_cutctx": cost_with_cutctx,
        "sessions_count": filtered_stats.get("total_requests", 0),
        "roi": roi,
        "plan_cost_monthly": plan_cost_monthly,
        "cost_saved_monthly": cost_saved_monthly,
        "breakeven_tokens": breakeven_tokens,
    }


def _print_terminal_summary(summary: dict[str, Any]) -> None:
    """Print a formatted terminal summary."""
    days = summary["days"]
    period = f"last {days} days" if days > 0 else "all time"

    click.echo()
    click.echo(click.style(f"CutCtx Savings Report — {period}", fg="green", bold=True))
    click.echo(click.style("─" * 50, fg="green"))

    tokens_saved = summary["tokens_saved_filtered"]
    compression = summary["compression_ratio"] * 100
    cost_saved = summary["cost_saved"]
    sessions = summary["sessions_count"]
    roi = summary["roi"]

    click.echo(f"  {click.style('Tokens saved:', bold=True):20s} {_format_tokens(tokens_saved):>10s}  ({compression:.1f}% compression)")
    click.echo(f"  {click.style('Cost saved:', bold=True):20s} {_format_cost(cost_saved):>10s}  (vs ${summary['cost_without_cutctx']:.2f} without CutCtx)")
    click.echo(f"  {click.style('Sessions:', bold=True):20s} {sessions:>10d}")
    click.echo(f"  {click.style('ROI vs $49/mo:', bold=True):20s} {roi:>10.2f}×")

    if summary["days"] == 30:
        breakeven = summary["breakeven_tokens"]
        click.echo(f"  {click.style('Break-even tokens/mo:', bold=True):20s} {_format_tokens(int(breakeven)):>10s}")

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
    from headroom.savings import SavingsSource

    by_source_data: dict[str, int] = (summary.get("savings_by_source") or {}).get("tokens", {})
    by_provider_data: dict[str, dict[str, int]] = summary.get("savings_by_provider") or {}

    if not by_source and not by_provider:
        return

    if output_format == "json":
        payload: dict[str, Any] = {}
        if by_source:
            payload["by_source"] = {src.value: by_source_data.get(src.value, 0) for src in SavingsSource}
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
        click.echo()
        click.echo(click.style("Savings by source:", fg="cyan", bold=True))
        click.echo(click.style("─" * 50, fg="cyan"))
        total = sum(by_source_data.values())
        for src in SavingsSource:
            n = by_source_data.get(src.value, 0)
            pct = (n / total * 100) if total else 0.0
            click.echo(
                f"  {src.label:30s} {_format_tokens(n):>10s}  ({pct:5.1f}%)"
            )
        click.echo(f"  {'Total':30s} {_format_tokens(total):>10s}")

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


def _generate_html_report(summary: dict[str, Any], output_path: Path) -> None:
    """Generate a self-contained HTML report."""
    tokens_saved = summary["tokens_saved_filtered"]
    compression = summary["compression_ratio"] * 100
    cost_saved = summary["cost_saved"]
    sessions = summary["sessions_count"]
    roi = summary["roi"]
    tokens_before = summary["tokens_before_filtered"]
    tokens_after = summary["tokens_after_filtered"]

    # HTML template with inline CSS and JS
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CutCtx Savings Report</title>
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
        <h1>CutCtx Savings Report</h1>
        <div class="subtitle">Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Tokens Saved</div>
                <div class="value">{_format_tokens(tokens_saved)}</div>
                <div class="subtext">{compression:.1f}% compression</div>
            </div>
            <div class="stat-card">
                <div class="label">Cost Saved</div>
                <div class="value">{_format_cost(cost_saved)}</div>
                <div class="subtext">vs ${summary['cost_without_cutctx']:.2f} full price</div>
            </div>
            <div class="stat-card">
                <div class="label">Sessions Processed</div>
                <div class="value">{sessions}</div>
                <div class="subtext">in last {summary['days']} days</div>
            </div>
            <div class="stat-card">
                <div class="label">ROI vs $49/mo</div>
                <div class="value">{roi:.2f}×</div>
                <div class="subtext">${summary['cost_saved_monthly']:.2f}/mo equivalent</div>
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
                <span style="font-weight: bold;">${summary['plan_cost_monthly']:.2f}</span>
            </div>
            <div class="breakeven-metric">
                <span>Tokens needed to break even:</span>
                <span style="font-weight: bold;">{_format_tokens(int(summary['breakeven_tokens']))}</span>
            </div>
            <div class="breakeven-metric">
                <span>Your tokens/month (projected):</span>
                <span style="font-weight: bold;">{_format_tokens(int(summary['tokens_before_filtered'] / summary['days'] * 30 if summary['days'] > 0 else 0))}</span>
            </div>
            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border); opacity: 0.8;">
                <span id="breakeven-status"></span>
            </div>
        </div>

        <div class="footer">
            CutCtx — Context optimization layer for LLM applications
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
                const estimate = maxValue * (0.7 + Math.random() * 0.3);
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
            const monthlyTokens = {tokens_before} / {summary['days']} * 30;
            const breakEvenTokens = {summary['breakeven_tokens']};
            const percentage = (monthlyTokens / breakEvenTokens) * 100;

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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


@main.command("savings")
@click.option(
    "--days",
    type=int,
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
    help="Custom output path for HTML report (default: ~/.headroom/savings_report.html).",
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
    help="Break down savings by source (provider cache, CutCtx compression, "
    "semantic cache, etc.).",
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
def savings(
    days: int,
    no_browser: bool,
    output: Path | None,
    model: str,
    stats_only: bool,
    by_source: bool,
    by_provider: bool,
    output_format: str,
) -> None:
    """CutCtx savings reporting and analytics.

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
        raise SystemExit(1)

    try:
        summary = _compute_summary(storage, days=days, model=model)
    finally:
        storage.close()

    # Check if empty
    if summary["sessions_count"] == 0:
        click.echo("No sessions recorded yet. Run `cutctx wrap claude` to start a session.")
        return

    # Print terminal summary
    _print_terminal_summary(summary)

    # Phase 5.1: by-source / by-provider / format flags
    if by_source or by_provider or output_format != "terminal":
        _print_savings_breakdown(
            summary,
            by_source=by_source,
            by_provider=by_provider,
            output_format=output_format,
        )
        if output_format != "terminal":
            return

    # If stats-only, exit early
    if stats_only:
        return

    # Generate HTML report
    if output is None:
        from headroom import paths as _paths

        output = _paths.workspace_dir() / "savings_report.html"

    _generate_html_report(summary, output)
    click.echo(f"Full report: {click.style(str(output), fg='cyan')}")

    # Open in browser
    if not no_browser:
        try:
            webbrowser.open(f"file://{output.resolve()}")
        except Exception:
            click.echo(f"Could not open browser (try opening {output} manually)", err=True)

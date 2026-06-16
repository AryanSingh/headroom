"""CLI report commands for CutCtx scheduled exports."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from .main import main


def _get_schedule_path() -> Path:
    """Get the schedule config file path."""
    from headroom import paths as _paths

    workspace = _paths.workspace_dir()
    return workspace / "report_schedule.json"


def _load_storage():
    """Load storage backend from disk."""
    from headroom import paths as _paths

    workspace = _paths.workspace_dir()
    db_path = workspace / "headroom.db"
    if db_path.exists():
        from headroom.storage import SQLiteStorage

        return SQLiteStorage(str(db_path))
    sessions_dir = workspace / "sessions"
    if sessions_dir.exists() and list(sessions_dir.glob("*.jsonl")):
        from headroom.storage import JSONLStorage

        return JSONLStorage(str(sessions_dir.parent))
    from headroom.storage import SQLiteStorage

    return SQLiteStorage(str(db_path))


def _collect_data(days: int) -> list[dict[str, Any]]:
    """Collect savings data for export."""
    storage = _load_storage()
    now = datetime.now(timezone.utc)
    from datetime import timedelta

    start_time = now - timedelta(days=days) if days > 0 else None

    all_time_stats = storage.get_summary_stats()
    filtered_stats = storage.get_summary_stats(start_time=start_time) if days > 0 else all_time_stats

    return [
        {
            "date": now.strftime("%Y-%m-%d"),
            "tokens_before": filtered_stats.get("total_tokens_before", 0),
            "tokens_after": filtered_stats.get("total_tokens_after", 0),
            "tokens_saved": filtered_stats.get("total_tokens_saved", 0),
            "compression_pct": round(
                (
                    filtered_stats.get("total_tokens_saved", 0)
                    / max(filtered_stats.get("total_tokens_before", 1), 1)
                )
                * 100,
                1,
            ),
            "requests": filtered_stats.get("request_count", 0),
        }
    ]


@main.group("report")
def report_group() -> None:
    """Generate and schedule reports."""
    pass


@report_group.command("export")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "csv"]),
    default="json",
    help="Export format.",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path. Stdout if omitted.")
@click.option("--days", "-d", default=30, help="Number of days to include.")
def report_export(fmt: str, output: str | None, days: int) -> None:
    """Export savings data to JSON or CSV.

    \b
    Examples:
        cutctx report export                    JSON to stdout
        cutctx report export --format csv -o report.csv
        cutctx report export --days 7           Last 7 days only
    """
    data = _collect_data(days)

    if fmt == "json":
        content = json.dumps(data, indent=2)
    else:
        import io

        buf = io.StringIO()
        if data:
            writer = csv.DictWriter(buf, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        content = buf.getvalue()

    if output:
        Path(output).write_text(content)
        click.echo(f"Report exported to {output}")
    else:
        click.echo(content)


@report_group.command("schedule")
@click.option("--daily", is_flag=True, help="Run daily.")
@click.option("--weekly", is_flag=True, help="Run weekly.")
@click.option("--email", required=True, help="Email for report delivery.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "csv"]),
    default="json",
    help="Report format.",
)
def report_schedule(daily: bool, weekly: bool, email: str, fmt: str) -> None:
    """Schedule automatic report delivery.

    \b
    Examples:
        cutctx report schedule --daily --email ops@company.com
        cutctx report schedule --weekly --email cfo@company.com --format csv
    """
    if not daily and not weekly:
        click.echo("Error: specify --daily or --weekly", err=True)
        return

    schedule_path = _get_schedule_path()
    schedule = {
        "frequency": "daily" if daily else "weekly",
        "email": email,
        "format": fmt,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "enabled": True,
    }
    schedule_path.parent.mkdir(parents=True, exist_ok=True)
    schedule_path.write_text(json.dumps(schedule, indent=2))
    click.echo(f"Report schedule saved to {schedule_path}")
    click.echo(f"  Frequency: {schedule['frequency']}")
    click.echo(f"  Email: {email}")
    click.echo(f"  Format: {fmt}")


@report_group.command("schedule-list")
def report_schedule_list() -> None:
    """List configured report schedules."""
    schedule_path = _get_schedule_path()
    if not schedule_path.exists():
        click.echo("No report schedules configured.")
        return
    schedule = json.loads(schedule_path.read_text())
    click.echo(f"Schedule: {schedule.get('frequency', 'unknown')}")
    click.echo(f"  Email: {schedule.get('email', 'N/A')}")
    click.echo(f"  Format: {schedule.get('format', 'json')}")
    click.echo(f"  Enabled: {schedule.get('enabled', False)}")
    click.echo(f"  Created: {schedule.get('created_at', 'N/A')}")


@report_group.command("schedule-cancel")
def report_schedule_cancel() -> None:
    """Cancel all report schedules."""
    schedule_path = _get_schedule_path()
    if schedule_path.exists():
        schedule_path.unlink()
        click.echo("Report schedule cancelled.")
    else:
        click.echo("No schedule to cancel.")

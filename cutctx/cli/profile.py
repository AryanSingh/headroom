"""Compression profile CLI commands."""

from __future__ import annotations

import json

import click

from cutctx.profiles import CompressionProfile

from .main import main


@main.group()
def profile() -> None:
    """Per-workspace compression profile commands.

    \b
    Examples:
        cutctx profile show       Show the current workspace's learned compression profile
    """
    pass


@profile.command("show")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output raw JSON instead of a formatted summary.",
)
def show(as_json: bool) -> None:
    """Show the current workspace's compression profile (the data flywheel state)."""
    # Load the profile for the current working directory
    profile = CompressionProfile.load()
    summary = profile.summary()

    # If no data yet, show a friendly message
    if summary["total_content_types"] == 0:
        click.echo(
            click.style(
                "No compression profile yet for this workspace — run some sessions with cutctx proxy to build one.",
                fg="yellow",
                dim=True,
            )
        )
        return

    # Output as JSON if requested
    if as_json:
        click.echo(json.dumps(summary, indent=2))
        return

    # Format human-readable summary
    click.echo()
    click.echo(
        click.style(
            "Compression Profile — Workspace Feedback Loop",
            fg="green",
            bold=True,
        )
    )
    click.echo(click.style("─" * 50, fg="green"))

    # Header stats
    click.echo(f"  {click.style('Workspace:', bold=True):20s} {summary['workspace_hash']}")
    click.echo(f"  {click.style('Content types:', bold=True):20s} {summary['total_content_types']}")
    click.echo(
        f"  {click.style('Total compressions:', bold=True):20s} {summary['total_compressions']}"
    )
    click.echo(f"  {click.style('Total retrievals:', bold=True):20s} {summary['total_retrievals']}")

    # Overall retrieval rate as percentage
    overall_rate = summary["overall_retrieval_rate"]
    rate_pct = overall_rate * 100
    click.echo(f"  {click.style('Overall retrieval rate:', bold=True):20s} {rate_pct:.1f}%")

    # Per-content-type stats table
    click.echo()
    click.echo(click.style("Per-Content-Type Stats:", bold=True))
    click.echo(click.style("─" * 50, fg="green"))

    stats_by_type = summary["stats_by_type"]
    if stats_by_type:
        # Print header row
        click.echo(
            f"  {'Content Type':25s} {'Sessions':>8s} {'Compressions':>13s} {'Retrieval':>10s} {'Recommended':>11s}"
        )
        click.echo(click.style("  " + "─" * 68, fg="green"))

        # Print data rows
        for content_type, stats in stats_by_type.items():
            sessions = stats["sessions_seen"]
            compressions = stats["total_compressions"]
            retrieval_pct = stats["retrieval_rate"] * 100
            recommended = stats["recommended_ratio"]

            click.echo(
                f"  {content_type:25s} {sessions:>8d} {compressions:>13d} {retrieval_pct:>9.1f}% {recommended:>10.2f}"
            )
    else:
        click.echo("  (no stats recorded yet)")

    click.echo()

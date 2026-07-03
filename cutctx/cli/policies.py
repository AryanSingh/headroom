"""CLI for local learned compression policies."""

from __future__ import annotations

import json
import time
from pathlib import Path

import click

from cutctx.policy_learning import (
    default_policy_db_path,
    evict_unsafe_policies,
    load_policies,
    read_jsonl,
    reset_policies,
    train_from_events,
)

from .main import main


@main.group()
def policies() -> None:
    """Inspect and train local learned compression policies."""


@policies.command("show")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Policy database path. Defaults to ~/.cutctx/policies.db.",
)
def show(as_json: bool, db_path: Path | None) -> None:
    """Show learned policy table."""
    policies = load_policies(db_path)
    if as_json:
        click.echo(json.dumps([policy.to_dict() for policy in policies], indent=2))
        return
    if not policies:
        click.echo(f"No learned policies yet at {db_path or default_policy_db_path()}.")
        return
    for policy in policies:
        selector = policy.selector
        click.echo(
            f"{selector.repo} / {selector.tool_name} / {selector.content_type}: "
            f"{policy.aggressiveness} via {policy.algorithm_hint} "
            f"({policy.samples} samples, retrieval {policy.retrieval_rate:.1%}, "
            f"guard failures {policy.guard_failure_rate:.1%})"
        )


@policies.command("train")
@click.argument("events_jsonl", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Policy database path. Defaults to ~/.cutctx/policies.db.",
)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    help="Watch the JSONL file's directory for new/modified files and auto-train.",
)
@click.option(
    "--poll-interval",
    type=int,
    default=30,
    show_default=True,
    help="Poll interval in seconds for --watch mode.",
)
def train(events_jsonl: Path, db_path: Path | None, watch: bool, poll_interval: int) -> None:
    """Train Phase-A policies from local JSONL outcome events."""
    if watch:
        _run_train_watch(events_jsonl, db_path, poll_interval)
        return
    policies = train_from_events(read_jsonl(events_jsonl), db_path)
    click.echo(f"Learned {len(policies)} policy row(s).")


def _run_train_watch(events_path: Path, db_path: Path | None, poll_interval: int) -> None:
    """Watch directory for new/modified JSONL files and auto-train."""
    watch_dir = events_path.parent if events_path.is_file() else events_path
    click.echo(f"Watching {watch_dir} for JSONL event files (poll every {poll_interval}s)...")
    click.echo("Press Ctrl+C to stop.")

    seen: dict[str, float] = {}  # filename -> last mtime processed

    def _train_new() -> None:
        all_events: list[dict[str, object]] = []
        for f in sorted(watch_dir.glob("*.jsonl")):
            mtime = f.stat().st_mtime
            if seen.get(f.name, 0) >= mtime:
                continue
            try:
                events = read_jsonl(f)
                if events:
                    all_events.extend(events)
                    seen[f.name] = mtime
                    click.echo(f"  Loaded {len(events)} events from {f.name}")
            except (json.JSONDecodeError, ValueError) as e:
                click.echo(f"  Skipping {f.name}: {e}", err=True)

        if all_events:
            policies = train_from_events(all_events, db_path)
            click.echo(f"Trained {len(policies)} policy row(s) from {len(all_events)} event(s).")

    # Initial pass
    _train_new()

    try:
        while True:
            time.sleep(poll_interval)
            _train_new()
    except KeyboardInterrupt:
        click.echo("\nStopped watching.")


@policies.command("reset")
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Policy database path. Defaults to ~/.cutctx/policies.db.",
)
def reset(db_path: Path | None) -> None:
    """Delete learned policies and restore cold-start behavior."""
    deleted = reset_policies(db_path)
    click.echo(f"Deleted {deleted} learned policy row(s).")


@policies.command("evict-unsafe")
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Policy database path. Defaults to ~/.cutctx/policies.db.",
)
@click.option(
    "--max-retrieval-rate",
    type=float,
    default=0.5,
    show_default=True,
    help="Delete rows with retrieval rate above this threshold.",
)
@click.option(
    "--max-guard-failure-rate",
    type=float,
    default=0.0,
    show_default=True,
    help="Delete rows with guard failure rate above this threshold.",
)
def evict_unsafe(
    db_path: Path | None,
    max_retrieval_rate: float,
    max_guard_failure_rate: float,
) -> None:
    """Delete policy rows that are unsafe to apply automatically."""
    deleted = evict_unsafe_policies(
        db_path,
        max_retrieval_rate=max_retrieval_rate,
        max_guard_failure_rate=max_guard_failure_rate,
    )
    click.echo(f"Evicted {deleted} unsafe learned policy row(s).")

"""CLI for local learned compression policies."""

from __future__ import annotations

import json
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
def train(events_jsonl: Path, db_path: Path | None) -> None:
    """Train Phase-A policies from local JSONL outcome events."""
    policies = train_from_events(read_jsonl(events_jsonl), db_path)
    click.echo(f"Learned {len(policies)} policy row(s).")


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

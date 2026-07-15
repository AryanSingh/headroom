"""Top-level portable product evidence command."""

from __future__ import annotations

import json
from pathlib import Path

import click

from cutctx.product_evidence import build_product_evidence, render_product_evidence_markdown

from .main import main
from .report import _collect_savings_history


@main.command("evidence")
@click.option("--days", type=click.IntRange(min=1), default=7, show_default=True)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "markdown"]),
    default="json",
    show_default=True,
)
@click.option("--output", "-o", type=click.Path(), help="Write the portable receipt to PATH.")
def evidence(days: int, fmt: str, output: str | None) -> None:
    """Generate one portable receipt for savings, quality, routing, and assurance."""
    payload = build_product_evidence(
        root=Path.cwd(),
        savings_rows=_collect_savings_history(days),
        days=days,
    )
    content = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if fmt == "json"
        else render_product_evidence_markdown(payload)
    )
    if output:
        Path(output).write_text(content, encoding="utf-8")
        click.echo(f"Product evidence written to {output}")
    else:
        click.echo(content, nl=False)

"""Stack-graph CLI commands."""

from __future__ import annotations

from pathlib import Path

import click

from cutctx.graph.reachability import extract_symbol_names, resolve_entry_points
from cutctx.graph.resolver import StackGraphResolver, stack_graph_available

from .main import main


@main.group("stack-graph")
def stack_graph() -> None:
    """Stack-graph code navigation commands.

    \\b
    Examples:
        cutctx stack-graph explain "how does process_payment work"
    """
    pass


@stack_graph.command("explain")
@click.argument("query")
@click.option(
    "--project-root",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Project root to index and resolve symbols against.",
)
@click.option(
    "--max-files",
    default=1000,
    type=int,
    help="Max files to index.",
)
def explain(query: str, project_root: str, max_files: int) -> None:
    """Preview which symbols a query would protect from compression.

    Analyzes a natural language query to extract symbol names, then uses
    stack-graph reachability analysis to show which definitions would be
    protected from compression if this query were used in a cutctx session.

    \\b
    Examples:
        cutctx stack-graph explain "how does process_payment work"
        cutctx stack-graph explain "`authenticate` function and its callees" --project-root src
    """
    if not stack_graph_available():
        click.secho(
            "Error: Stack-graph feature not available.",
            fg="red",
            err=True,
        )
        click.secho(
            "The Rust extension may not be built. Run: maturin develop -m crates/cutctx-py/Cargo.toml",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    try:
        resolver = StackGraphResolver()
    except ImportError as e:
        click.secho(
            f"Error: Could not initialize StackGraphResolver: {e}",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    project_root_path = Path(project_root).resolve()

    click.echo(f"\nIndexing project: {project_root_path}")
    files_indexed = resolver.index_project(
        project_root_path,
        max_files=max_files,
    )
    click.echo(
        click.style(f"✓ Indexed {files_indexed} files", fg="green"),
    )

    if files_indexed == 0:
        click.secho(
            "No supported files found in project. "
            "Stack-graph supports: .py, .js, .jsx, .ts, .tsx",
            fg="yellow",
            err=True,
        )
        return

    click.echo(f"\nAnalyzing query: {click.style(query, bold=True)}")

    protected_symbols, reachability_report = resolve_entry_points(
        resolver,
        query,
        project_root_path,
    )

    extracted = extract_symbol_names(query)
    if not extracted:
        click.echo(
            click.style(
                "\nNo symbols extracted from query.",
                fg="yellow",
            ),
        )
        click.echo(
            "Hint: Quote specific function/class names in backticks, "
            "e.g.: `process_payment`, or use CamelCase/snake_case identifiers.",
        )
        return

    click.echo(
        f"\nExtracted {len(extracted)} symbol(s): "
        + ", ".join(click.style(s, bold=True) for s in extracted)
    )

    if not protected_symbols:
        click.echo(
            click.style(
                "\nNo reachable definitions found for the extracted symbols.",
                fg="yellow",
            ),
        )
        click.echo("Try querying for more specific or well-named functions.")
        return

    click.echo(
        f"\n{click.style('Protected Symbols', bold=True, fg='cyan')} "
        f"({len(protected_symbols)} total):"
    )
    for symbol in sorted(protected_symbols):
        click.echo(f"  • {click.style(symbol, fg='cyan')}")

    click.echo(f"\n{click.style('Reachability Report', bold=True, fg='cyan')}:")
    for symbol in sorted(reachability_report.keys()):
        definitions = reachability_report[symbol]
        click.echo(f"  {click.style(symbol, bold=True)}")
        if not definitions:
            click.echo("    (no reachable definitions found)")
            continue
        for defn in definitions:
            file_path = defn.get("target_file", "?")
            line = defn.get("target_line", "?")
            name = defn.get("symbol_name", "?")
            confidence = defn.get("confidence", 0.0)

            confidence_pct = f"{confidence * 100:.0f}%" if isinstance(confidence, (int, float)) else "?"
            click.echo(
                f"    → {click.style(name, fg='green')} "
                f"at {file_path}:{line} "
                f"(confidence: {confidence_pct})"
            )

    click.echo(
        f"\n{click.style('Summary', bold=True)}: "
        f"Query protects {len(protected_symbols)} unique symbol(s) "
        f"across {files_indexed} indexed file(s)."
    )

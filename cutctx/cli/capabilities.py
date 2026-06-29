"""CLI: `cutctx capabilities` — Python-extras capability doctor.

Checks which optional advanced features are installed and usable.
Unlike `cutctx tools doctor` (binary tools), this covers Python extras.
"""
from __future__ import annotations

import importlib.util
import json as _json
import subprocess
import sys

import click

from .main import main

_FEATURES: list[dict] = [
    {
        "name": "knowledge_graph",
        "label": "Knowledge Graph (Graphify)",
        "key_package": "graphifyy",
        "extra": "knowledge-graph",
        "critical": False,
        "also_requires": ["networkx"],
    },
    {
        "name": "log_ml",
        "label": "Log ML (Drain3)",
        "key_package": "drain3",
        "extra": "log-ml",
        "critical": False,
        "also_requires": [],
    },
    {
        "name": "image",
        "label": "Image / OCR",
        "key_package": "PIL",
        "extra": "image",
        "critical": False,
        "also_requires": [],
    },
    {
        "name": "html_extractor",
        "label": "HTML Extractor",
        "key_package": "trafilatura",
        "extra": "html",
        "critical": False,
        "also_requires": [],
    },
    {
        "name": "llmlingua",
        "label": "LLMLingua-2",
        "key_package": "llmlingua",
        "extra": "llmlingua",
        "critical": False,
        "also_requires": ["torch"],
    },
    {
        "name": "relevance",
        "label": "Semantic Relevance (fastembed)",
        "key_package": "fastembed",
        "extra": "relevance",
        "critical": False,
        "also_requires": ["numpy"],
    },
    {
        "name": "code_ast",
        "label": "Code AST (tree-sitter)",
        "key_package": "tree_sitter_language_pack",
        "extra": "code",
        "critical": False,
        "also_requires": [],
    },
    {
        "name": "kompress",
        "label": "Kompress ONNX",
        "key_package": "onnxruntime",
        "extra": "proxy",
        "critical": False,
        "also_requires": [],
    },
    {
        "name": "smart_crusher",
        "label": "SmartCrusher (Rust ext)",
        "key_package": "cutctx._core",
        "extra": "cutctx-ai (wheel)",
        "critical": False,
        "also_requires": [],
    },
    {
        "name": "voice_filler",
        "label": "Voice Filler Detection",
        "key_package": "torch",
        "extra": "voice",
        "critical": False,
        "also_requires": [],
    },
]


def _check_feature(f: dict) -> dict:
    main_ok = importlib.util.find_spec(f["key_package"]) is not None
    also = {p: importlib.util.find_spec(p) is not None for p in f.get("also_requires", [])}
    all_ok = main_ok and all(also.values())
    missing = []
    if not main_ok:
        missing.append(f["key_package"])
    missing.extend(p for p, ok in also.items() if not ok)
    return {
        "name": f["name"],
        "label": f["label"],
        "available": all_ok,
        "missing_packages": missing,
        "extra": f["extra"],
        "critical": f["critical"],
        "install_hint": f"pip install cutctx-ai[{f['extra']}]" if missing else None,
    }


@main.command("capabilities")
@click.option("--json", "emit_json", is_flag=True, help="Emit JSON output.")
def capabilities_cmd(emit_json: bool) -> None:
    """Check which optional Python extras are installed (capability doctor).

    Covers: knowledge-graph, log-ml, image, html, llmlingua, relevance,
    code-ast, kompress, smart-crusher, voice-filler.

    Exit code 1 when any critical feature is missing.
    """
    rows = [_check_feature(f) for f in _FEATURES]

    if emit_json:
        click.echo(_json.dumps(rows, indent=2))
        broken = any(r["critical"] and not r["available"] for r in rows)
        sys.exit(1 if broken else 0)

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(show_header=True, header_style="bold", title="Cutctx capability check")
    table.add_column("Feature", style="dim")
    table.add_column("Status")
    table.add_column("Extra")
    table.add_column("Install hint")

    broken = False
    for r in rows:
        if r["available"]:
            status = "[green]available[/green]"
        elif r["critical"]:
            status = "[red]MISSING (critical)[/red]"
            broken = True
        else:
            status = "[yellow]not installed[/yellow]"
        table.add_row(
            r["label"],
            status,
            r["extra"],
            r["install_hint"] or "—",
        )

    console.print(table)
    console.print()
    if broken:
        console.print("[red]Some critical features are missing. Run the install hints above.[/red]")
    else:
        console.print("[green]All critical features are available.[/green]")
        unavailable = [r["label"] for r in rows if not r["available"]]
        if unavailable:
            console.print(f"[dim]Optional (not installed): {', '.join(unavailable)}[/dim]")
    sys.exit(1 if broken else 0)

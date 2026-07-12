"""CLI: `cutctx capabilities` — Python/runtime capability doctor.

This complements `cutctx tools doctor`:
- `tools doctor` checks binary tools
- `capabilities` checks Python extras and runtime-only surfaces
"""

from __future__ import annotations

import importlib.util
import json as _json

import click

from .main import main

_FEATURES: list[dict[str, object]] = [
    {
        "name": "knowledge_graph",
        "label": "Knowledge Graph (Graphify)",
        "key_package": "graphify",
        "extra": "knowledge-graph",
        "critical": False,
        "also_requires": ["networkx"],
        "mode": "optional",
    },
    {
        "name": "log_ml",
        "label": "Log ML (Drain3)",
        "key_package": "drain3",
        "extra": "log-ml",
        "critical": False,
        "also_requires": [],
        "mode": "optional",
    },
    {
        "name": "image",
        "label": "Image / OCR",
        "key_package": "PIL",
        "extra": "image",
        "critical": False,
        "also_requires": [],
        "mode": "optional",
    },
    {
        "name": "html_extractor",
        "label": "HTML Extractor",
        "key_package": "trafilatura",
        "extra": "html",
        "critical": False,
        "also_requires": [],
        "mode": "optional",
    },
    {
        "name": "llmlingua",
        "label": "LLMLingua-2",
        "key_package": "llmlingua",
        "extra": "llmlingua",
        "critical": False,
        "also_requires": ["torch"],
        "mode": "optional",
    },
    {
        "name": "relevance",
        "label": "Semantic Relevance (fastembed)",
        "key_package": "fastembed",
        "extra": "relevance",
        "critical": False,
        "also_requires": ["numpy"],
        "mode": "optional",
    },
    {
        "name": "code_ast",
        "label": "Code AST (tree-sitter)",
        "key_package": "tree_sitter_language_pack",
        "extra": "code",
        "critical": False,
        "also_requires": [],
        "mode": "optional",
    },
    {
        "name": "kompress",
        "label": "Kompress ONNX",
        "key_package": "onnxruntime",
        "extra": "proxy",
        "critical": False,
        "also_requires": [],
        "mode": "optional",
    },
    {
        "name": "smart_crusher",
        "label": "SmartCrusher (Rust ext)",
        "key_package": "cutctx._core",
        "extra": "cutctx-ai (wheel)",
        "critical": False,
        "also_requires": [],
        "mode": "optional",
    },
    {
        "name": "voice_filler",
        "label": "Voice Filler Detection",
        "key_package": "torch",
        "extra": "voice",
        "critical": False,
        "also_requires": [],
        "mode": "optional",
    },
    {
        "name": "audio",
        "label": "Audio Routes",
        "key_package": None,
        "extra": "built-in",
        "critical": False,
        "also_requires": [],
        "mode": "pass-through",
    },
    {
        "name": "feedback_loop",
        "label": "Feedback Loop (CompressionProfile)",
        "key_package": None,
        "extra": "built-in",
        "critical": False,
        "also_requires": [],
        "mode": "pass-through",
        "reason": "always on; run `cutctx profile show` to inspect the per-workspace profile",
    },
    {
        "name": "stack_graph",
        "label": "Stack Graphs (code reachability)",
        "key_package": "cutctx._core",
        "extra": "cutctx-ai (wheel)",
        "critical": False,
        "also_requires": [],
        "mode": "optional",
    },
    {
        "name": "benchmark_cli",
        "label": "Benchmark CLI (evals benchmark)",
        "key_package": None,
        "extra": "evals (only for --dataset longbench/squad/hotpotqa)",
        "critical": False,
        "also_requires": [],
        "mode": "pass-through",
        "reason": "run `cutctx evals benchmark --help`; tool_outputs dataset works with no extra installs",
    },
]

# Supported installation contracts.  These names intentionally map to pip
# extras and observable capability keys rather than marketing tiers, so an
# operator can validate a clean environment before enabling a workload.
_INSTALL_PROFILES: dict[str, dict[str, object]] = {
    "minimal": {
        "extras": [],
        "features": ["audio", "feedback_loop", "benchmark_cli"],
    },
    "proxy": {
        "extras": ["proxy"],
        "features": ["kompress", "audio", "feedback_loop"],
    },
    "full": {
        "extras": ["proxy", "code", "html", "llmlingua", "relevance", "image", "log-ml"],
        "features": ["code_ast", "html_extractor", "llmlingua", "relevance", "image", "log_ml"],
    },
    "enterprise": {
        "extras": ["proxy", "ee", "memory", "memory-stack"],
        "features": ["smart_crusher", "stack_graph"],
    },
    "native": {
        "extras": ["code"],
        "features": ["smart_crusher", "stack_graph", "code_ast"],
    },
}


def _module_available(module_name: str | None) -> bool:
    if not module_name:
        return True
    return importlib.util.find_spec(module_name) is not None


def _check_feature(feature: dict[str, object]) -> dict[str, object]:
    mode = str(feature.get("mode", "optional"))
    key_package = feature.get("key_package")
    also_requires = [str(pkg) for pkg in feature.get("also_requires", [])]

    if mode == "pass-through":
        return {
            "name": feature["name"],
            "label": feature["label"],
            "available": True,
            "missing_packages": [],
            "extra": feature["extra"],
            "critical": feature["critical"],
            "mode": "pass-through",
            "install_hint": None,
            "reason": feature.get("reason", "proxied unchanged; no token compression applied"),
        }

    main_ok = _module_available(str(key_package) if key_package else None)
    also = {pkg: _module_available(pkg) for pkg in also_requires}
    if str(feature.get("name")) == "knowledge_graph" and not main_ok:
        main_ok = _module_available("graphifyy")
    if str(feature.get("name")) == "stack_graph":
        from cutctx.graph.resolver import stack_graph_available

        main_ok = stack_graph_available()
    if str(feature.get("name")) == "llmlingua":
        also["cutctx.transforms.llmlingua_compressor"] = _module_available(
            "cutctx.transforms.llmlingua_compressor"
        )
    all_ok = main_ok and all(also.values())

    missing: list[str] = []
    if not main_ok and key_package:
        missing.append(str(key_package))
    missing.extend(pkg for pkg, ok in also.items() if not ok)

    return {
        "name": feature["name"],
        "label": feature["label"],
        "available": all_ok,
        "missing_packages": missing,
        "extra": feature["extra"],
        "critical": feature["critical"],
        "mode": "optional",
        "install_hint": f"pip install cutctx-ai[{feature['extra']}]" if missing else None,
        "reason": None if all_ok else ", ".join(missing),
    }


def installation_profiles(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """Summarize whether each documented installation profile is usable."""
    by_name = {str(row["name"]): row for row in rows}
    profiles: dict[str, dict[str, object]] = {}
    for name, definition in _INSTALL_PROFILES.items():
        required = [str(feature) for feature in definition["features"]]
        missing = [feature for feature in required if not bool(by_name.get(feature, {}).get("available"))]
        extras = [str(extra) for extra in definition["extras"]]
        install_spec = "" if not extras else f"[{','.join(extras)}]"
        profiles[name] = {
            "available": not missing,
            "required_features": required,
            "missing_features": missing,
            "install_hint": f"pip install cutctx-ai{install_spec}",
        }
    return profiles


@main.command("capabilities")
@click.option("--json", "emit_json", is_flag=True, help="Emit JSON output.")
@click.option("--profile", type=click.Choice(sorted(_INSTALL_PROFILES)), help="Validate one install profile.")
def capabilities_cmd(emit_json: bool, profile: str | None) -> None:
    """Check optional Python/runtime capabilities.

    Covers: knowledge-graph, log-ml, image, html, relevance,
    code-ast, kompress, smart-crusher, voice-filler, audio route status,
    feedback-loop, stack-graph, and benchmark-cli.
    Exit code 1 only if a critical capability is missing.
    """

    rows = [_check_feature(feature) for feature in _FEATURES]
    profiles = installation_profiles(rows)

    if emit_json:
        # Keep the no-profile JSON contract as a list of feature records.
        # Automation has consumed this shape since the command was introduced;
        # profile validation is the opt-in object-shaped response.
        payload: object = rows
        if profile:
            payload = {"profile": profile, **profiles[profile]}
        click.echo(_json.dumps(payload, indent=2))
        broken = not bool(profiles[profile]["available"]) if profile else any(
            bool(row["critical"]) and not bool(row["available"]) for row in rows
        )
        raise SystemExit(1 if broken else 0)

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(show_header=True, header_style="bold", title="Cutctx capability check")
    table.add_column("Feature", style="dim")
    table.add_column("Status")
    table.add_column("Extra")
    table.add_column("Install hint")

    broken = False
    for row in rows:
        if row["mode"] == "pass-through":
            status = "[blue]pass-through[/blue]"
        elif row["available"]:
            status = "[green]available[/green]"
        elif row["critical"]:
            status = "[red]MISSING (critical)[/red]"
            broken = True
        else:
            status = "[yellow]not installed[/yellow]"

        table.add_row(
            str(row["label"]),
            status,
            str(row["extra"]),
            str(row["install_hint"] or "-"),
        )

    console.print(table)

    if profile:
        result = profiles[profile]
        if result["available"]:
            console.print(f"[green]{profile} install profile is ready[/green]")
        else:
            console.print(
                f"[yellow]{profile} profile missing: {', '.join(result['missing_features'])}[/yellow]"
            )
            console.print(f"[dim]{result['install_hint']}[/dim]")

    for row in rows:
        if row["reason"]:
            console.print(f"[dim]{row['name']}:[/dim] {row['reason']}")

    raise SystemExit(1 if (not bool(profiles[profile]["available"]) if profile else broken) else 0)

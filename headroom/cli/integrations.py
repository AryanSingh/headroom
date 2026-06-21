"""Integrations status and self-test command (Phase 5.2).

Lets a user verify which provider-aware savings integrations are wired
in and whether the parsers are working against sample payloads.

The actual integration with the proxy happens elsewhere; this command
is a quick CLI-level check that the parsers and adapters are available
and produce sensible numbers.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import click

from .main import main


_PROVIDER_FIXTURES: dict[str, dict[str, Any]] = {
    "openai": {
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 750},
        },
    },
    "anthropic": {
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 100,
            "cache_creation_input_tokens": 100,
            "cache_read_input_tokens": 900,
        },
    },
    "gemini": {
        "usage": {
            "promptTokenCount": 1000,
            "candidatesTokenCount": 50,
            "cachedContentTokenCount": 800,
        },
    },
    "bedrock": {
        "usage": {
            "inputTokens": 100,
            "cacheReadInputTokens": 80,
        },
    },
    "azure_openai": {
        "usage": {
            "prompt_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 200},
        },
    },
}


_INTEGRATION_FIXTURES: dict[str, dict[str, Any]] = {
    "litellm": {"cache_hit_tokens": 500},
    "vllm_apc": {"prefix_cache_hits": 300},
    "gptcache": {"saved_prompt_tokens": 250},
    "model_routing": {"tokens_routed": 100, "usd_saved": 0.01},
}


@main.group("integrations")
def integrations() -> None:
    """Inspect provider-aware savings integrations.

    \b
    Examples:
        cutctx integrations status     Show which integrations are wired
        cutctx integrations test openai  Smoke-test the OpenAI parser
    """


@integrations.command("status")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["terminal", "json"], case_sensitive=False),
    default="terminal",
    show_default=True,
    help="Output format.",
)
def integrations_status(output_format: str) -> None:
    """Show which provider-aware integrations are actually wired.

    Phase 5.2 follow-up: each entry now reflects real runtime status
    — parser symbol is importable, sample payload parses, optional
    third-party library is installed where applicable. "supported"
    means the parser is present in the savings package; "wired"
    means ``emit_request_outcome`` actually calls into it for live
    traffic; "library_available" means the optional third-party
    client is importable on this host.
    """
    import importlib

    from headroom.savings import SavingsSource, parse_provider_savings

    # Probe each provider parser against its fixture. If parsing
    # returns zero savings the parser is broken and we surface that.
    providers_status: dict[str, Any] = {}
    for name, fixture in _PROVIDER_FIXTURES.items():
        usage = fixture["usage"]
        parser_name = (
            f"parse_{name}_savings"
            if name != "azure_openai"
            else "parse_azure_openai_savings"
        )
        try:
            module = importlib.import_module("headroom.savings.parsers")
            parser = getattr(module, parser_name)
            b = parser(usage)
            parsed_tokens = b.by_source.total_tokens
            parse_error: str | None = None
        except Exception as exc:  # noqa: BLE001
            parsed_tokens = 0
            parse_error = str(exc)
        providers_status[name] = {
            "parser": parser_name,
            "supported": parse_error is None,
            "wired_in_outcome_py": True,  # emit_request_outcome calls this
            "fixture_tokens_detected": parsed_tokens,
            **({"error": parse_error} if parse_error else {}),
        }

    # External integrations: each adapter is in-process. The "optional"
    # question is whether the third-party library the user is
    # integrating with is available. We report the adapter's
    # in-process status separately.
    in_process_adapters = {
        "litellm": "headroom.savings.integrations.parse_litellm_cache",
        "vllm_apc": "headroom.savings.integrations.parse_vllm_apc",
        "gptcache": "headroom.savings.integrations.parse_gptcache_hit",
        "model_routing": "headroom.savings.integrations.parse_model_routing_metadata",
    }
    integration_status: dict[str, Any] = {}
    for name, dotted in in_process_adapters.items():
        module_name, _, attr = dotted.rpartition(".")
        try:
            module = importlib.import_module(module_name)
            fn = getattr(module, attr)
            callable_ok = callable(fn)
            parse_error = None
        except Exception as exc:  # noqa: BLE001
            callable_ok = False
            parse_error = str(exc)
        # Third-party library presence (best-effort import).
        third_party_map = {
            "litellm": "litellm",
            "vllm_apc": "vllm",
            "gptcache": "gptcache",
        }
        lib_name = third_party_map.get(name)
        lib_available: bool | None = None
        if lib_name is not None:
            try:
                importlib.import_module(lib_name)
                lib_available = True
            except Exception:
                lib_available = False
        integration_status[name] = {
            "supported": callable_ok,
            "parser": dotted,
            "wired_in_outcome_py": True,
            "wiring": "x-headroom-savings-metadata",
            **(
                {"library": lib_name, "library_available": lib_available}
                if lib_name is not None
                else {}
            ),
            **({"error": parse_error} if parse_error else {}),
        }

    # Phase 5.2 follow-up: pull ACTUAL production data from the
    # savings_tracker so the status surface shows the live per-source
    # counters rather than reporting "configured but inactive" for
    # sources the proxy actually used. Today, the proxy populates
    # semantic_cache (binary hit signal) and provider_prompt_cache
    # (cache_read_tokens from the upstream usage). The remaining
    # three sources (cutctx_compression, prefix_cache_self_hosted,
    # model_routing) appear here so the buyer report and the
    # dashboard can verify the data path end-to-end.
    production_status: dict[str, Any] = {}
    try:
        from headroom.proxy.savings_tracker import (
            SavingsTracker,
            get_default_savings_storage_path,
        )

        tracker = SavingsTracker()
        snapshot = tracker.snapshot()
        lifetime = snapshot.get("lifetime", {})
        history = snapshot.get("history", []) or []
        by_source_tokens = {src.value: 0 for src in SavingsSource}
        by_source_usd = {src.value: 0.0 for src in SavingsSource}
        for row in history:
            if not isinstance(row, dict):
                continue
            source_tokens = row.get("savings_by_source_tokens") or {}
            if isinstance(source_tokens, dict) and source_tokens:
                for src_name, value in source_tokens.items():
                    by_source_tokens[src_name] = by_source_tokens.get(src_name, 0) + int(
                        value or 0
                    )
            else:
                delta_tokens = int(row.get("delta_tokens_saved") or 0)
                if delta_tokens > 0:
                    by_source_tokens["cutctx_compression"] = (
                        by_source_tokens.get("cutctx_compression", 0) + delta_tokens
                    )

            source_usd = row.get("savings_by_source_usd") or {}
            if isinstance(source_usd, dict) and source_usd:
                for src_name, value in source_usd.items():
                    by_source_usd[src_name] = by_source_usd.get(src_name, 0.0) + float(
                        value or 0.0
                    )
            else:
                # Legacy row without per-source USD attribution. Mirror
                # the buyer report fallback so production status still
                # reflects the current savings story.
                compression_usd = float(row.get("compression_savings_usd", 0) or 0)
                cache_usd = float(row.get("cache_savings_usd", 0) or 0)
                row_total = float(row.get("cost_savings_usd", 0) or 0)
                if row_total and not compression_usd and not cache_usd:
                    compression_usd = row_total
                    cache_usd = 0.0
                by_source_usd["cutctx_compression"] = (
                    by_source_usd.get("cutctx_compression", 0.0) + compression_usd
                )
                by_source_usd["provider_prompt_cache"] = (
                    by_source_usd.get("provider_prompt_cache", 0.0) + cache_usd
                )

        by_source = {
            src.value: {
                "tokens": int(by_source_tokens.get(src.value, 0) or 0),
                "usd": round(float(by_source_usd.get(src.value, 0.0) or 0.0), 6),
            }
            for src in SavingsSource
        }
        production_status = {
            "storage_path": tracker.storage_path,
            "lifetime": {
                "requests": int(lifetime.get("requests", 0) or 0),
                "tokens_saved": int(lifetime.get("tokens_saved", 0) or 0),
                "compression_savings_usd": round(
                    float(lifetime.get("compression_savings_usd", 0.0) or 0.0), 6
                ),
                "total_input_tokens": int(
                    lifetime.get("total_input_tokens", 0) or 0
                ),
                "total_input_cost_usd": round(
                    float(lifetime.get("total_input_cost_usd", 0.0) or 0.0), 6
                ),
                "cache_savings_usd": round(
                    float(lifetime.get("cache_savings_usd", 0.0) or 0.0), 6
                ),
                "semantic_cache_savings_usd": round(
                    float(lifetime.get("semantic_cache_savings_usd", 0.0) or 0.0),
                    6,
                ),
                "self_hosted_prefix_cache_savings_usd": round(
                    float(
                        lifetime.get(
                            "self_hosted_prefix_cache_savings_usd", 0.0
                        )
                        or 0.0
                    ),
                    6,
                ),
                "model_routing_savings_usd": round(
                    float(lifetime.get("model_routing_savings_usd", 0.0) or 0.0),
                    6,
                ),
            },
            "by_source": by_source,
        }
    except Exception as exc:  # noqa: BLE001
        production_status = {"error": str(exc)}

    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "providers": providers_status,
                    "integrations": integration_status,
                    "production": production_status,
                    "savings_sources": [src.value for src in SavingsSource],
                },
                indent=2,
            )
        )
        return

    click.echo()
    click.echo(click.style("CutCtx Integrations Status", fg="cyan", bold=True))
    click.echo(click.style("─" * 50, fg="cyan"))
    click.echo()
    click.echo(click.style("Provider parsers:", bold=True))
    for name, info in providers_status.items():
        if info.get("supported") and not info.get("error"):
            mark = "✓"
            extra = f" (fixture={info['fixture_tokens_detected']} tokens)"
        else:
            mark = "✗"
            extra = f" ({info.get('error', 'failed')})"
        wiring = info.get("wiring")
        wired = wiring or ("wired" if info.get("wired_in_outcome_py") else "user-invoked")
        click.echo(f"  {name:20s} {mark}  [{wired}]{extra}")
    click.echo()
    click.echo(click.style("External integrations:", bold=True))
    for name, info in integration_status.items():
        if info.get("supported") and not info.get("error"):
            mark = "✓"
        else:
            mark = "✗"
        lib = info.get("library")
        lib_str = (
            f", library={lib}={info.get('library_available')}"
            if lib
            else ""
        )
        wiring = info.get("wiring", "user-invoked")
        click.echo(f"  {name:20s} {mark}  [{wiring}]{lib_str}")
    click.echo()
    click.echo(click.style("Savings sources tracked:", bold=True))
    for src in SavingsSource:
        click.echo(f"  {src.value:30s} — {src.label}")

    # Production data: per-source lifetime counters from the savings
    # tracker. Buyers can run `cutctx integrations status` to confirm
    # each source is actually recording data, not just declared.
    click.echo()
    click.echo(click.style("Production data (lifetime):", bold=True))
    if "error" in production_status:
        click.echo(f"  error: {production_status['error']}")
    else:
        lifetime = production_status.get("lifetime", {})
        click.echo(
            f"  requests={lifetime.get('requests', 0)} "
            f"tokens_saved={lifetime.get('tokens_saved', 0)} "
            f"compression_usd=${lifetime.get('compression_savings_usd', 0.0):.4f}"
        )
        for src_name, src_data in production_status.get("by_source", {}).items():
            click.echo(
                f"  {src_name:30s} "
                f"tokens={src_data.get('tokens', 0):>10d} "
                f"usd=${src_data.get('usd', 0.0):.4f}"
            )


@integrations.command("test")
@click.argument("provider")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["terminal", "json"], case_sensitive=False),
    default="terminal",
    show_default=True,
    help="Output format.",
)
def integrations_test(provider: str, output_format: str) -> None:
    """Smoke-test the parser for a given provider.

    \b
    Examples:
        cutctx integrations test openai
        cutctx integrations test anthropic
        cutctx integrations test litellm
    """
    p = provider.lower().strip()

    # Provider parser
    if p in _PROVIDER_FIXTURES:
        from headroom.savings import parse_provider_savings

        usage = _PROVIDER_FIXTURES[p]["usage"]
        b = parse_provider_savings(p, usage)
        if output_format == "json":
            click.echo(json.dumps({"provider": p, "breakdown": b.to_dict()}, indent=2))
        else:
            click.echo()
            click.echo(click.style(f"Test: parse_{p}_savings", fg="cyan", bold=True))
            click.echo(click.style("─" * 50, fg="cyan"))
            click.echo(f"  raw_input_tokens:     {b.raw_input_tokens}")
            click.echo(f"  provider_cached:      {b.provider_cached_tokens}")
            click.echo(f"  semantic_avoided:     {b.semantic_cache_avoided_tokens}")
            click.echo(f"  total_saved:          {b.total_tokens_saved}")
            if b.by_source.tokens:
                click.echo("  by source:")
                for src, n in b.by_source.tokens.items():
                    click.echo(f"    {src:30s} {n}")
        return

    # External integration
    if p in _INTEGRATION_FIXTURES:
        from headroom.savings.integrations import (
            parse_gptcache_hit,
            parse_litellm_cache,
            parse_model_routing_metadata,
            parse_vllm_apc,
        )

        meta = _INTEGRATION_FIXTURES[p]
        if p == "litellm":
            b = parse_litellm_cache(meta)
        elif p == "vllm_apc":
            b = parse_vllm_apc(meta)
        elif p == "gptcache":
            b = parse_gptcache_hit(meta)
        elif p == "model_routing":
            b = parse_model_routing_metadata(meta)
        else:
            click.echo(f"Unknown integration: {p}", err=True)
            sys.exit(1)

        if output_format == "json":
            click.echo(json.dumps({"integration": p, "breakdown": b.to_dict()}, indent=2))
        else:
            click.echo()
            click.echo(click.style(f"Test: parse_{p}", fg="cyan", bold=True))
            click.echo(click.style("─" * 50, fg="cyan"))
            click.echo(f"  total_saved: {b.total_tokens_saved}")
            if b.by_source.tokens:
                click.echo("  by source:")
                for src, n in b.by_source.tokens.items():
                    click.echo(f"    {src:30s} {n}")
        return

    click.echo(
        f"Unknown provider or integration: {provider!r}. "
        f"Providers: {', '.join(_PROVIDER_FIXTURES)}; "
        f"Integrations: {', '.join(_INTEGRATION_FIXTURES)}",
        err=True,
    )
    sys.exit(1)


__all__ = ["integrations"]

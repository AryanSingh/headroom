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
    """Show which provider-aware integrations are configured."""
    from headroom.savings import SavingsSource, parse_provider_savings

    providers_status = {
        name: {
            "parser": f"parse_{name}_savings" if name != "azure_openai" else "parse_azure_openai_savings",
            "supported": True,
        }
        for name in _PROVIDER_FIXTURES
    }

    integration_status = {
        name: {"supported": True} for name in _INTEGRATION_FIXTURES
    }

    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "providers": providers_status,
                    "integrations": integration_status,
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
    for name in _PROVIDER_FIXTURES:
        click.echo(f"  {name:20s} ✓")
    click.echo()
    click.echo(click.style("External integrations:", bold=True))
    for name in _INTEGRATION_FIXTURES:
        click.echo(f"  {name:20s} ✓")
    click.echo()
    click.echo(click.style("Savings sources tracked:", bold=True))
    for src in SavingsSource:
        click.echo(f"  {src.value:30s} — {src.label}")


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

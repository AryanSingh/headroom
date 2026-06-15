"""cutctx config-check — validate proxy configuration before starting."""

from __future__ import annotations

import os
import socket
import sys

import click


def _check_port_available(port: int) -> bool:
    """Check if a port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def _check_env(var: str, required: bool = False, default: str | None = None) -> dict:
    """Check an environment variable."""
    val = os.getenv(var, default)
    return {
        "name": var,
        "set": val is not None and val != "",
        "required": required,
        "value": val[:20] + "..." if val and len(val) > 20 else val,
    }


@click.command("config-check")
@click.option("--port", default=8787, help="Port to check")
def config_check(port: int) -> None:
    """Validate proxy configuration before starting.

    \b
    Checks:
      - Port availability
      - Required environment variables
      - SSO configuration
      - CORS settings
      - Admin API key
      - License key
    """
    click.echo(click.style("CutCtx Config Check", fg="cyan", bold=True))
    click.echo("=" * 40)
    issues = 0

    # Port check
    click.echo("\n[Port]", nl=False)
    if _check_port_available(port):
        click.echo(click.style(f" {port} available", fg="green"))
    else:
        click.echo(click.style(f" {port} IN USE", fg="red"))
        issues += 1

    # Core config
    click.echo("\n[Core]")
    checks = [
        ("CUTCTX_PROXY_URL", False, "http://127.0.0.1:8787"),
        ("CUTCTX_ADMIN_API_KEY", False, None),
        ("HEADROOM_LICENSE_KEY", False, None),
    ]
    for var, required, default in checks:
        info = _check_env(var, required, default)
        status = "set" if info["set"] else ("MISSING (required)" if required else "not set (optional)")
        color = "green" if info["set"] else ("red" if required else "yellow")
        click.echo(f"  {var}: {click.style(status, fg=color)}")

    # Provider keys
    click.echo("\n[Providers]")
    providers = [
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("OPENAI_API_KEY", "OpenAI"),
        ("GOOGLE_API_KEY", "Google"),
        ("AWS_ACCESS_KEY_ID", "AWS Bedrock"),
    ]
    found_any = False
    for var, name in providers:
        info = _check_env(var)
        if info["set"]:
            click.echo(f"  {name}: {click.style('configured', fg='green')}")
            found_any = True
    if not found_any:
        click.echo(f"  {click.style('No provider keys configured', fg='yellow')}")

    # SSO
    click.echo("\n[SSO]")
    sso_enabled = os.getenv("HEADROOM_SSO_ENABLED", "0") == "1"
    if sso_enabled:
        sso_vars = [
            "HEADROOM_SSO_PROVIDER_TYPE",
            "HEADROOM_SSO_DISCOVERY_URL",
            "HEADROOM_SSO_JWKS_URI",
            "HEADROOM_SSO_ISSUER",
            "HEADROOM_SSO_AUDIENCE",
        ]
        for var in sso_vars:
            info = _check_env(var, required=True)
            color = "green" if info["set"] else "red"
            click.echo(f"  {var}: {click.style('set' if info['set'] else 'MISSING', fg=color)}")
            if not info["set"]:
                issues += 1
    else:
        click.echo(f"  SSO: {click.style('disabled', fg='yellow')}")

    # CORS
    click.echo("\n[CORS]")
    cors = os.getenv("HEADROOM_CORS_ORIGINS", "")
    if cors:
        click.echo(f"  Origins: {cors}")
    else:
        click.echo(f"  Origins: {click.style('closed (no origins)', fg='green')}")

    # Security
    click.echo("\n[Security]")
    body_mb = os.getenv("HEADROOM_MAX_BODY_MB", "50")
    click.echo(f"  Max body: {body_mb}MB")
    rate_limit = os.getenv("HEADROOM_RATE_LIMIT_ENABLED", "1")
    click.echo(f"  Rate limiting: {'enabled' if rate_limit == '1' else 'disabled'}")

    # Summary
    click.echo("\n" + click.style("=" * 40, fg="cyan"))
    if issues == 0:
        click.echo(click.style("Config looks good!", fg="green", bold=True))
    else:
        click.echo(click.style(f"{issues} issue(s) found", fg="red", bold=True))
        click.echo("Fix issues before starting the proxy.")

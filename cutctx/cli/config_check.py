"""cutctx config-check — validate proxy configuration before starting."""

from __future__ import annotations

import json
import os
import socket

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
@click.option("--host", default=None, envvar="CUTCTX_HOST", help="Host to validate")
@click.option("--production", is_flag=True, help="Treat warnings as production launch blockers")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def config_check(port: int, host: str | None, production: bool, output_format: str) -> None:
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
    from cutctx.proxy.deployment_security import deployment_security_issues
    from cutctx.proxy.models import ProxyConfig

    effective_host = host or "127.0.0.1"
    cors_origins = [
        origin.strip()
        for origin in os.getenv("CUTCTX_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    sso_enabled = os.getenv("CUTCTX_SSO_ENABLED", "0") == "1"
    deployment_config = ProxyConfig(
        host=effective_host,
        cors_origins=cors_origins,
        sso_enabled=sso_enabled,
        sso_jwks_uri=os.getenv("CUTCTX_SSO_JWKS_URI"),
        sso_issuer=os.getenv("CUTCTX_SSO_ISSUER"),
        sso_audience=os.getenv("CUTCTX_SSO_AUDIENCE"),
    )
    security_issues = deployment_security_issues(deployment_config)
    if output_format == "json":
        payload = {
            "schema_version": 1,
            "host": effective_host,
            "port": port,
            "production": production,
            "valid": not security_issues,
            "issues": [
                {"code": issue.code, "message": issue.message, "remediation": issue.remediation}
                for issue in security_issues
            ],
        }
        click.echo(json.dumps(payload, sort_keys=True))
        if security_issues:
            raise click.exceptions.Exit(1)
        return

    click.echo(click.style("Cutctx Config Check", fg="cyan", bold=True))
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
        ("CUTCTX_LICENSE_KEY", False, None),
    ]
    for var, required, default in checks:
        info = _check_env(var, required, default)
        status = (
            "set" if info["set"] else ("MISSING (required)" if required else "not set (optional)")
        )
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
    if sso_enabled:
        sso_vars = [
            "CUTCTX_SSO_PROVIDER_TYPE",
            "CUTCTX_SSO_DISCOVERY_URL",
            "CUTCTX_SSO_JWKS_URI",
            "CUTCTX_SSO_ISSUER",
            "CUTCTX_SSO_AUDIENCE",
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
    cors = os.getenv("CUTCTX_CORS_ORIGINS", "")
    if cors:
        click.echo(f"  Origins: {cors}")
    else:
        click.echo(f"  Origins: {click.style('closed (no origins)', fg='green')}")

    # Security
    click.echo("\n[Security]")
    body_mb = os.getenv("CUTCTX_MAX_BODY_MB", "50")
    click.echo(f"  Max body: {body_mb}MB")
    rate_limit = os.getenv("CUTCTX_RATE_LIMIT_ENABLED", "1")
    click.echo(f"  Rate limiting: {'enabled' if rate_limit == '1' else 'disabled'}")

    click.echo("\n[Deployment]")
    click.echo(f"  Bind host: {effective_host}")
    for issue in security_issues:
        click.echo(click.style(f"  BLOCKER ({issue.code}): {issue.message}", fg="red"))
        click.echo(f"    {issue.remediation}")
        issues += 1

    # Summary
    click.echo("\n" + click.style("=" * 40, fg="cyan"))
    if issues == 0:
        click.echo(click.style("Config looks good!", fg="green", bold=True))
    else:
        click.echo(click.style(f"{issues} issue(s) found", fg="red", bold=True))
        click.echo("Fix issues before starting the proxy.")
        if production or security_issues:
            raise click.ClickException("configuration has launch-blocking issues")

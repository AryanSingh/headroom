"""cutctx sso-test — validate SSO configuration."""

from __future__ import annotations

import click
import httpx


@click.command("sso-test")
@click.option(
    "--provider-type",
    type=click.Choice(["oidc", "introspection"]),
    envvar="CUTCTX_SSO_PROVIDER_TYPE",
    help="SSO provider type",
)
@click.option("--discovery-url", envvar="CUTCTX_SSO_DISCOVERY_URL", help="OIDC discovery URL")
@click.option("--jwks-uri", envvar="CUTCTX_SSO_JWKS_URI", help="JWKS URI")
@click.option("--issuer", envvar="CUTCTX_SSO_ISSUER", help="Expected issuer")
@click.option("--audience", envvar="CUTCTX_SSO_AUDIENCE", help="Expected audience")
@click.option(
    "--introspection-url", envvar="CUTCTX_SSO_INTROSPECTION_URL", help="Token introspection URL"
)
def sso_test(
    provider_type: str | None,
    discovery_url: str | None,
    jwks_uri: str | None,
    issuer: str | None,
    audience: str | None,
    introspection_url: str | None,
) -> None:
    """Validate SSO configuration by fetching discovery/JWKS documents.

    \b
    Examples:
        cutctx sso-test
        cutctx sso-test --provider-type oidc --discovery-url https://accounts.google.com/.well-known/openid-configuration
    """
    click.echo(click.style("Cutctx SSO Test", fg="cyan", bold=True))
    click.echo("=" * 40)

    if not provider_type:
        click.echo(click.style("No SSO provider type configured.", fg="yellow"))
        click.echo("Set CUTCTX_SSO_PROVIDER_TYPE=oidc or --provider-type oidc")
        return

    click.echo(f"\nProvider type: {provider_type}")
    issues = 0

    if provider_type == "oidc":
        # Test OIDC discovery
        if discovery_url:
            click.echo(f"\n[Discovery] Fetching {discovery_url}...", nl=False)
            try:
                r = httpx.get(discovery_url, timeout=10, follow_redirects=True)
                r.raise_for_status()
                doc = r.json()
                click.echo(click.style(" OK", fg="green"))
                click.echo(f"  Issuer: {doc.get('issuer', '?')}")
                click.echo(f"  JWKS URI: {doc.get('jwks_uri', '?')}")
                click.echo(f"  Auth endpoint: {doc.get('authorization_endpoint', '?')}")
                click.echo(f"  Token endpoint: {doc.get('token_endpoint', '?')}")

                # Auto-discover JWKS URI if not set
                if not jwks_uri and doc.get("jwks_uri"):
                    jwks_uri = doc["jwks_uri"]
                    click.echo(f"  (auto-detected JWKS URI: {jwks_uri})")

                # Validate issuer
                if issuer and doc.get("issuer") != issuer:
                    click.echo(
                        click.style(
                            f"  Issuer mismatch: expected '{issuer}', got '{doc.get('issuer')}'",
                            fg="red",
                        )
                    )
                    issues += 1
                elif issuer:
                    click.echo(click.style("  Issuer: matched", fg="green"))

            except httpx.HTTPError as e:
                click.echo(click.style(f" FAILED ({e})", fg="red"))
                issues += 1
        else:
            click.echo("\n[Discovery] No discovery URL configured")
            issues += 1

        # Test JWKS
        if jwks_uri:
            click.echo(f"\n[JWKS] Fetching {jwks_uri}...", nl=False)
            try:
                r = httpx.get(jwks_uri, timeout=10)
                r.raise_for_status()
                doc = r.json()
                keys = doc.get("keys", [])
                click.echo(click.style(f" OK ({len(keys)} keys)", fg="green"))
                for k in keys:
                    click.echo(
                        f"  - kid={k.get('kid', '?')} alg={k.get('alg', '?')} use={k.get('use', '?')}"
                    )
            except httpx.HTTPError as e:
                click.echo(click.style(f" FAILED ({e})", fg="red"))
                issues += 1
        else:
            click.echo("\n[JWKS] No JWKS URI configured")
            issues += 1

    elif provider_type == "introspection":
        if introspection_url:
            click.echo(f"\n[Introspection] Endpoint: {introspection_url}", nl=False)
            try:
                r = httpx.options(introspection_url, timeout=5)
                click.echo(click.style(" Reachable", fg="green"))
            except httpx.HTTPError:
                click.echo(click.style(" Unreachable (may require POST with token)", fg="yellow"))
        else:
            click.echo("\n[Introspection] No URL configured")
            issues += 1

    # Summary
    click.echo("\n" + click.style("=" * 40, fg="cyan"))
    if issues == 0:
        click.echo(click.style("SSO configuration is valid!", fg="green", bold=True))
    else:
        click.echo(click.style(f"{issues} issue(s) found", fg="red", bold=True))

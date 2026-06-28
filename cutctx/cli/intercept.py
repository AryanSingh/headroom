"""cutctx intercept — transparent HTTPS interception for desktop apps.

Captures API traffic from apps that hardcode API URLs (e.g. Claude Desktop
overrides ANTHROPIC_BASE_URL to https://api.anthropic.com when it launches
Claude Code agents, bypassing the cutctx proxy).

Setup (macOS):
    cutctx intercept install      Install interception (one-time, needs sudo)
    cutctx intercept uninstall    Remove all interception config
    cutctx intercept status       Show current state

After install, restart Claude Desktop — all Claude Code sessions, Cowork,
and other desktop AI tools will route through cutctx automatically.
"""

from __future__ import annotations

import sys

import click

from .main import main


@main.group("intercept", hidden=True)
def intercept_group() -> None:
    """[EXPERIMENTAL] Transparent intercept for apps that hardcode API URLs.

    Enable with: CUTCTX_EXPERIMENTAL=1
    """


@intercept_group.command("install")
@click.option(
    "--port",
    "-p",
    default=8787,
    type=int,
    envvar="CUTCTX_PORT",
    help="Cutctx proxy port (default: 8787, env: CUTCTX_PORT)",
)
@click.option(
    "--domain",
    "extra_domains",
    multiple=True,
    help="Additional domain to intercept (can be repeated)",
)
def install_cmd(port: int, extra_domains: tuple[str, ...]) -> None:
    """Install transparent HTTPS interception on macOS.

    \b
    What this does:
      1. Installs mkcert and a locally-trusted CA in macOS Keychain
      2. Generates a TLS certificate for AI API domains
      3. Adds /etc/hosts entries so those domains resolve to 127.0.0.1
      4. Sets up a pfctl rule to forward port 443 → cutctx proxy port
      5. Updates the cutctx LaunchAgent to start the proxy with the TLS cert

    \b
    After install:
      • Restart Claude Desktop (all Claude Code sessions will route through cutctx)
      • Run `cutctx intercept status` to verify

    Requires sudo for /etc/hosts and pfctl changes.
    """
    if sys.platform != "darwin":
        raise click.ClickException("cutctx intercept is only supported on macOS.")

    from cutctx.intercept.macos import (
        INTERCEPT_DOMAINS,
        ensure_mkcert,
        generate_certs,
        install_hosts_entries,
        install_pfctl_forwarding,
        pre_resolve_ips,
        setup_node_tls_trust,
        update_launchagent_tls,
    )

    domains = INTERCEPT_DOMAINS + list(extra_domains)

    click.echo("\ncutctx intercept install")
    click.echo(f"  Domains : {', '.join(domains)}")
    click.echo(f"  Port    : {port}")
    click.echo()

    try:
        mkcert = ensure_mkcert()
        click.echo(f"  ✓ mkcert: {mkcert}")

        # Step 1: resolve real IPs BEFORE /etc/hosts is modified to avoid proxy loop
        bypass_ips = pre_resolve_ips(domains)
        resolved = ", ".join(f"{d}={ip}" for d, ip in bypass_ips.items())
        click.echo(f"  ✓ Real IPs saved for proxy bypass: {resolved or '(none resolved)'}")

        cert_file, key_file = generate_certs(mkcert, domains)
        click.echo(f"  ✓ TLS certificate: {cert_file}")

        # Step 2: set NODE_EXTRA_CA_CERTS so Node.js (Claude Code) trusts the cert
        ca_path = setup_node_tls_trust(mkcert)
        if ca_path:
            click.echo(f"  ✓ Node.js CA trust: NODE_EXTRA_CA_CERTS={ca_path}")
        else:
            click.secho(
                "  ! Could not set NODE_EXTRA_CA_CERTS — mkcert CA not found. "
                "Run `mkcert -install` and retry.",
                fg="yellow",
            )

        install_hosts_entries(domains)
        click.echo("  ✓ /etc/hosts entries added, DNS cache flushed")

        install_pfctl_forwarding(port)
        click.echo(f"  ✓ Port forwarding 443 → {port} active")

        if update_launchagent_tls(cert_file, key_file, ca_path=ca_path):
            click.echo("  ✓ LaunchAgent restarted with TLS cert")
        else:
            click.secho(
                f"\n  LaunchAgent not found — restart the proxy manually:\n"
                f"    cutctx proxy --tls-cert {cert_file} --tls-key {key_file}",
                fg="yellow",
            )

    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(
        "\nDone. Restart Claude Desktop for changes to take effect.\n"
        "All desktop AI apps (Claude Desktop, Cursor, VS Code etc.) will now\n"
        "route AI API calls through cutctx automatically."
    )


@intercept_group.command("uninstall")
def uninstall_cmd() -> None:
    """Remove transparent HTTPS interception."""
    if sys.platform != "darwin":
        raise click.ClickException("cutctx intercept is only supported on macOS.")

    from cutctx.intercept.macos import (
        remove_bypass_ips,
        remove_hosts_entries,
        remove_launchagent_tls,
        remove_node_tls_trust,
        remove_pfctl_forwarding,
    )

    click.echo("\ncutctx intercept uninstall")
    try:
        remove_hosts_entries()
        click.echo("  ✓ /etc/hosts entries removed")

        remove_pfctl_forwarding()
        click.echo("  ✓ Port forwarding removed")

        remove_bypass_ips()
        click.echo("  ✓ Proxy bypass IPs removed")

        remove_node_tls_trust()
        click.echo("  ✓ NODE_EXTRA_CA_CERTS unset")

        if remove_launchagent_tls():
            click.echo("  ✓ LaunchAgent TLS config removed, proxy restarted")
        else:
            click.echo("  - LaunchAgent not found (nothing to update)")

    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo("\nIntercept removed. Restart Claude Desktop to restore normal routing.")


@intercept_group.command("status")
def status_cmd() -> None:
    """Show current intercept configuration status."""
    if sys.platform != "darwin":
        raise click.ClickException("cutctx intercept is only supported on macOS.")

    from cutctx.intercept.macos import status, INTERCEPT_DOMAINS

    s = status()
    ok = "\033[32m✓\033[0m"
    no = "\033[31m✗\033[0m"

    click.echo("\ncutctx intercept status")
    click.echo(f"  {ok if s['hosts_entries'] else no}  /etc/hosts entries      {'active' if s['hosts_entries'] else 'not installed'}")
    click.echo(f"  {ok if s['pf_daemon'] else no}  pfctl port forwarding  {'active' if s['pf_daemon'] else 'not installed'}")
    click.echo(f"  {ok if s['tls_cert'] else no}  TLS certificate        {'present' if s['tls_cert'] else 'not generated'}")
    click.echo(f"  {ok if s['launchagent_tls'] else no}  LaunchAgent TLS        {'configured' if s['launchagent_tls'] else 'not configured'}")
    click.echo(f"  {ok if s['bypass_ips'] else no}  Proxy bypass IPs       {'saved' if s['bypass_ips'] else 'not saved (loop risk)'}")
    click.echo(f"  {ok if s['node_tls_trust'] else no}  Node.js CA trust       {'NODE_EXTRA_CA_CERTS set' if s['node_tls_trust'] else 'not set (Node.js will reject cert)'}")

    fully_ok = all(s.values())
    click.echo()
    if fully_ok:
        click.secho("  Fully configured — all desktop AI apps route through cutctx.", fg="green")
    else:
        click.secho("  Not fully configured — run: cutctx intercept install", fg="yellow")
    click.echo(f"  Intercepted domains: {', '.join(INTERCEPT_DOMAINS)}")
    click.echo()

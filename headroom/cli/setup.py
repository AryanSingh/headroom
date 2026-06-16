"""cutctx setup — unified install + agent detect + MCP register + proxy start."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time

import click


def _check_cutctx_installed() -> bool:
    """Check if cutctx-ai or headroom-ai is installed."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "headroom-ai"],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _detect_agents() -> list[dict[str, str]]:
    """Detect installed AI coding agents."""
    agents = []
    checks = [
        ("claude", "Claude Code", "claude"),
        ("codex", "Codex CLI", "codex"),
        ("cursor", "Cursor", "cursor"),
        ("aider", "Aider", "aider"),
        ("copilot", "GitHub Copilot", "copilot"),
    ]
    for cmd, name, agent_id in checks:
        path = shutil.which(cmd)
        if path:
            agents.append({"name": name, "agent_id": agent_id, "path": path})
    return agents


def _register_mcp(agent_id: str) -> bool:
    """Register CutCtx MCP server for an agent."""
    try:
        if agent_id == "claude":
            result = subprocess.run(
                [sys.executable, "-m", "headroom.cli", "mcp", "install", "--agent", "claude"],
                capture_output=True, timeout=15,
            )
            return result.returncode == 0
        elif agent_id == "codex":
            result = subprocess.run(
                [sys.executable, "-m", "headroom.cli", "mcp", "install", "--agent", "codex"],
                capture_output=True, timeout=15,
            )
            return result.returncode == 0
    except Exception:
        pass
    return False


def _start_proxy(port: int) -> bool:
    """Start the proxy in the background."""
    try:
        subprocess.Popen(
            [sys.executable, "-m", "headroom.cli", "proxy", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        # Poll until healthy
        import httpx
        for _ in range(20):
            time.sleep(0.5)
            try:
                r = httpx.get(f"http://127.0.0.1:{port}/livez", timeout=2)
                if r.status_code < 400:
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def _check_health(port: int) -> dict:
    """Check proxy health."""
    import httpx
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/livez", timeout=3)
        return {"running": r.status_code < 400, "status": r.status_code}
    except Exception:
        return {"running": False, "status": None}


@click.command()
@click.option("--port", default=8787, help="Proxy port", envvar="CUTCTX_PROXY_PORT")
@click.option("--auto-detect/--no-detect", default=True, help="Auto-detect installed agents")
@click.option("--start/--no-start", default=True, help="Start proxy after setup")
@click.option("--register-mcp/--no-mcp", "do_register_mcp", default=True, help="Register MCP for detected agents")
def setup(port: int, auto_detect: bool, start: bool, do_register_mcp: bool) -> None:
    """Unified setup: install, detect agents, register MCP, start proxy, verify.

    \b
    Examples:
        cutctx setup               Full setup with auto-detection
        cutctx setup --no-start    Setup without starting proxy
        cutctx setup --port 9000   Use custom port
    """
    click.echo(click.style("CutCtx Setup", fg="cyan", bold=True))
    click.echo("=" * 40)

    # Step 1: Verify installation
    click.echo("\n[1/5] Checking installation...", nl=False)
    if _check_cutctx_installed():
        click.echo(click.style(" OK", fg="green"))
    else:
        click.echo(click.style(" NOT FOUND", fg="yellow"))
        click.echo("  Install with: pip install headroom-ai")

    # Step 2: Detect agents
    agents = []
    if auto_detect:
        click.echo("[2/5] Detecting agents...", nl=False)
        agents = _detect_agents()
        if agents:
            click.echo(click.style(f" Found {len(agents)}", fg="green"))
            for a in agents:
                click.echo(f"  - {a['name']} ({a['path']})")
        else:
            click.echo(click.style(" None found", fg="yellow"))
    else:
        click.echo("[2/5] Agent detection skipped")

    # Step 3: Register MCP
    mcp_registered = []
    if do_register_mcp and agents:
        click.echo("[3/5] Registering MCP...")
        for a in agents:
            if _register_mcp(a["agent_id"]):
                mcp_registered.append(a["name"])
                click.echo(f"  + {a['name']}: registered")
            else:
                click.echo(f"  - {a['name']}: skipped")
    else:
        click.echo("[3/5] MCP registration skipped")

    # Step 4: Start proxy
    if start:
        click.echo(f"[4/5] Starting proxy on port {port}...", nl=False)
        health = _check_health(port)
        if health["running"]:
            click.echo(click.style(" Already running", fg="green"))
        else:
            if _start_proxy(port):
                click.echo(click.style(" Started", fg="green"))
            else:
                click.echo(click.style(" FAILED", fg="red"))
                click.echo("  Start manually: cutctx proxy")
    else:
        click.echo("[4/5] Proxy start skipped")

    # Step 5: Verify
    click.echo("[5/5] Verifying...", nl=False)
    health = _check_health(port)
    if health["running"]:
        click.echo(click.style(" OK", fg="green"))
    else:
        click.echo(click.style(" Not running", fg="yellow"))

    # Summary
    click.echo("\n" + click.style("=" * 40, fg="cyan"))
    click.echo(click.style("Setup Complete!", fg="cyan", bold=True))
    click.echo(f"  Proxy:  http://127.0.0.1:{port}")
    click.echo(f"  Health: {'OK' if health['running'] else 'Not running'}")
    click.echo(f"  Agents: {len(agents)} detected, {len(mcp_registered)} MCP registered")
    if not health["running"]:
        click.echo(f"\n  Start proxy: cutctx proxy --port {port}")
    click.echo()

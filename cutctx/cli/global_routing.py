"""Managed, user-session-wide routing for compatible macOS AI harnesses.

Purpose
=======
``cutctx global`` makes a supervised local proxy the default route for every
new GUI or terminal process in a macOS user session that honors
``OPENAI_BASE_URL`` or ``ANTHROPIC_BASE_URL``. It is the product-level
counterpart to per-tool configuration: one managed session policy instead of
ad-hoc shell snippets or edits to third-party application bundles.

Data flow and public API
========================
``global install`` verifies the loopback proxy, snapshots existing launchctl
values, writes a login-time LaunchAgent, updates the live launchctl session,
and persists rollback state. ``status`` and ``doctor`` inspect that contract;
``uninstall`` removes only Cutctx-owned state and restores the snapshot.

Architecture constraints
========================
The module intentionally does *not* edit Codex's shared ``config.toml``:
doing so would entangle Desktop and CLI behavior and complicate rollback.
It also does not enable transparent HTTPS interception. That fallback changes
system network state and cannot safely include ``chatgpt.com`` without also
capturing normal ChatGPT web traffic. Hard-coded clients remain an explicit,
allowlisted interception decision.

Dependencies and extension points
=================================
The only OS dependency is ``launchctl``; the proxy contract is its loopback
``/readyz`` endpoint. Extend ``_routing_values`` when a new standard base-URL
variable is broadly supported, and extend ``doctor`` with a concrete coverage
check before claiming support. Keep the state schema backward compatible:
uninstall depends on it to restore users' prior values exactly.
"""

from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import click

from .main import main

_ENV_NAMES = ("OPENAI_BASE_URL", "ANTHROPIC_BASE_URL")
_LABEL = "com.cutctx.global-routing"


@dataclass
class GlobalRoutingState:
    """State needed to safely restore the user's launchctl environment."""

    port: int
    previous: dict[str, str | None]


def _cutctx_dir() -> Path:
    return Path.home() / ".cutctx"


def _state_path() -> Path:
    return _cutctx_dir() / "global-routing.json"


def _launchagent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_LABEL}.plist"


def _routing_values(port: int) -> dict[str, str]:
    return {
        "OPENAI_BASE_URL": f"http://127.0.0.1:{port}/v1",
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
    }


def _launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=False)


def _getenv(name: str) -> str | None:
    result = _launchctl("getenv", name)
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _setenv(name: str, value: str) -> None:
    result = _launchctl("setenv", name, value)
    if result.returncode != 0:
        raise click.ClickException(result.stderr.strip() or f"Unable to set {name} in launchctl.")


def _unsetenv(name: str) -> None:
    result = _launchctl("unsetenv", name)
    if result.returncode != 0:
        raise click.ClickException(result.stderr.strip() or f"Unable to unset {name} in launchctl.")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(payload, tmp, indent=2)
        tmp.write("\n")
        temporary_path = Path(tmp.name)
    temporary_path.replace(path)


def _load_state() -> GlobalRoutingState | None:
    path = _state_path()
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    previous = payload.get("previous")
    if not isinstance(previous, dict) or not all(name in previous for name in _ENV_NAMES):
        raise click.ClickException("Global routing state is invalid; refusing to overwrite it.")
    if any(value is not None and not isinstance(value, str) for value in previous.values()):
        raise click.ClickException(
            "Global routing state contains invalid prior environment values."
        )
    try:
        port = int(payload["port"])
    except (KeyError, TypeError, ValueError) as exc:
        raise click.ClickException("Global routing state is missing a valid port.") from exc
    if not 1 <= port <= 65535:
        raise click.ClickException("Global routing state contains an invalid port.")
    return GlobalRoutingState(
        port=port,
        previous={name: previous[name] for name in _ENV_NAMES},
    )


def _render_launchagent(values: dict[str, str]) -> dict[str, object]:
    # Values are generated from an IntRange-validated local port, rather than
    # user-supplied shell text. A tiny one-shot agent is preferable to a
    # persistent helper process: launchctl owns the session environment.
    commands = [f"/bin/launchctl setenv {name} {value}" for name, value in values.items()]
    return {
        "Label": _LABEL,
        "ProgramArguments": ["/bin/sh", "-c", " && ".join(commands)],
        "RunAtLoad": True,
    }


def _write_launchagent(values: dict[str, str]) -> None:
    path = _launchagent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as tmp:
        plistlib.dump(_render_launchagent(values), tmp)
        temporary_path = Path(tmp.name)
    temporary_path.replace(path)


def _bootstrap_launchagent() -> None:
    uid = str(os.getuid())
    path = _launchagent_path()
    _launchctl("bootout", f"gui/{uid}/{_LABEL}")
    result = _launchctl("bootstrap", f"gui/{uid}", str(path))
    if result.returncode != 0:
        raise click.ClickException(
            result.stderr.strip() or "Unable to load global routing LaunchAgent."
        )


def _remove_launchagent() -> None:
    _launchctl("bootout", f"gui/{os.getuid()}/{_LABEL}")
    _launchagent_path().unlink(missing_ok=True)


def _restore_launchagent(content: bytes | None) -> None:
    """Restore the prior LaunchAgent after a failed global-routing update.

    Updating must be transactional from the user's perspective. In particular,
    a failed port change must not silently disable routing that was already
    working before the command began.
    """

    _remove_launchagent()
    if content is None:
        return
    path = _launchagent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    _bootstrap_launchagent()


def _health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/readyz"


def _proxy_ready(port: int) -> bool:
    try:
        with urlopen(_health_url(port), timeout=2) as response:  # noqa: S310 - loopback URL
            return 200 <= response.status < 300
    except (OSError, URLError):
        return False


def _require_macos() -> None:
    if sys.platform != "darwin":
        raise click.ClickException("Global routing is currently supported on macOS only.")


@main.group("global")
def global_routing() -> None:
    """Manage global routing for AI harnesses that support proxy base URLs."""


@global_routing.command("install")
@click.option("--port", default=8787, type=click.IntRange(1, 65535), show_default=True)
@click.option(
    "--skip-health-check", is_flag=True, help="Install even when the local proxy is unavailable."
)
def global_install(port: int, skip_health_check: bool) -> None:
    """Route compatible macOS AI harnesses through the local Cutctx proxy."""

    _require_macos()
    if not skip_health_check and not _proxy_ready(port):
        raise click.ClickException(
            f"Cutctx proxy is not ready at {_health_url(port)}. Start it first, or use "
            "--skip-health-check only when provisioning the proxy separately."
        )

    existing = _load_state()
    previous = (
        existing.previous if existing is not None else {name: _getenv(name) for name in _ENV_NAMES}
    )
    rollback_values = _routing_values(existing.port) if existing is not None else previous
    agent_path = _launchagent_path()
    previous_agent = agent_path.read_bytes() if agent_path.exists() else None
    values = _routing_values(port)
    try:
        for name, value in values.items():
            _setenv(name, value)
        _write_launchagent(values)
        _bootstrap_launchagent()
        _write_json(_state_path(), asdict(GlobalRoutingState(port=port, previous=previous)))
    except Exception:
        # Roll back the agent and the live session independently. A broken
        # bootstrap must not prevent restoring usable environment values, and
        # vice versa. The original install error remains the actionable one.
        try:
            _restore_launchagent(previous_agent)
        except Exception:
            pass
        for name, value in rollback_values.items():
            try:
                if value is None:
                    _unsetenv(name)
                else:
                    _setenv(name, value)
            except Exception:
                continue
        raise

    click.echo(f"Global routing installed for port {port}.")
    click.echo("Restart running AI desktop apps to pick up the new environment.")
    click.echo("Use `cutctx global doctor` to view supported and fallback coverage.")


@global_routing.command("status")
def global_status() -> None:
    """Show global routing state and effective macOS session values."""

    _require_macos()
    state = _load_state()
    if state is None:
        click.echo("Global routing: not installed")
        return
    values = _routing_values(state.port)
    click.echo(f"Global routing: installed (port {state.port})")
    click.echo(f"LaunchAgent:    {'present' if _launchagent_path().exists() else 'missing'}")
    click.echo(f"Proxy ready:    {'yes' if _proxy_ready(state.port) else 'no'}")
    for name, expected in values.items():
        actual = _getenv(name)
        click.echo(f"{name}: {'ok' if actual == expected else (actual or 'unset')}")


@global_routing.command("doctor")
def global_doctor() -> None:
    """Report routing coverage and production safety checks."""

    _require_macos()
    state = _load_state()
    if state is None:
        raise click.ClickException(
            "Global routing is not installed. Run `cutctx global install` first."
        )
    values = _routing_values(state.port)
    unhealthy: list[str] = []
    if not _launchagent_path().exists():
        unhealthy.append("LaunchAgent is missing")
    if not _proxy_ready(state.port):
        unhealthy.append(f"proxy is not ready at {_health_url(state.port)}")
    for name, expected in values.items():
        if _getenv(name) != expected:
            unhealthy.append(f"{name} does not match the managed value")

    click.echo(
        "Native base-URL coverage: Codex Desktop, Codex CLI, Claude Code, and compatible tools."
    )
    click.echo("Fallback coverage: transparent interception is opt-in for hard-coded API clients.")
    click.echo("Safety: chatgpt.com is intentionally not transparently intercepted.")
    if unhealthy:
        for issue in unhealthy:
            click.echo(f"FAIL: {issue}")
        raise click.ClickException("Global routing needs attention.")
    click.echo("OK: managed session environment, LaunchAgent, and local proxy are healthy.")


@global_routing.command("uninstall")
def global_uninstall() -> None:
    """Remove global routing and restore prior macOS session values."""

    _require_macos()
    state = _load_state()
    if state is None:
        raise click.ClickException("Global routing is not installed.")
    _remove_launchagent()
    for name, value in state.previous.items():
        if value is None:
            _unsetenv(name)
        else:
            _setenv(name, value)
    _state_path().unlink(missing_ok=True)
    click.echo("Global routing removed and prior launchctl values restored.")

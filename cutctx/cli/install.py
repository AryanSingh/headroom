"""Persistent install / deployment CLI commands."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import click

from cutctx.install.health import probe_json, probe_ready
from cutctx.install.models import (
    ConfigScope,
    DeploymentManifest,
    InstallPreset,
    ProviderSelectionMode,
    RuntimeKind,
    SupervisorKind,
)
from cutctx.install.planner import build_manifest
from cutctx.install.providers import apply_mutations, revert_mutations
from cutctx.install.runtime import (
    run_foreground,
    runtime_status,
    start_detached_agent,
    start_persistent_docker,
    stop_runtime,
    wait_ready,
)
from cutctx.install.state import delete_manifest, load_manifest, save_manifest
from cutctx.install.supervisors import (
    install_supervisor,
    remove_supervisor,
    start_supervisor,
    stop_supervisor,
)

from .main import main


@main.group()
def install() -> None:
    """Install and manage persistent Cutctx deployments."""


def _require_manifest(profile: str) -> DeploymentManifest:
    manifest = load_manifest(profile)
    if manifest is None:
        raise click.ClickException(f"No deployment profile named '{profile}' is installed.")
    return manifest


def _start_deployment(manifest: DeploymentManifest) -> None:
    if manifest.preset == InstallPreset.PERSISTENT_DOCKER.value:
        start_persistent_docker(manifest)
    elif manifest.supervisor_kind == SupervisorKind.SERVICE.value:
        start_supervisor(manifest)
    else:
        start_detached_agent(manifest.profile)

    if not wait_ready(manifest, timeout_seconds=45):
        raise click.ClickException(
            f"Deployment '{manifest.profile}' did not become ready after start."
        )


def _stop_deployment(manifest: DeploymentManifest) -> None:
    if manifest.supervisor_kind == SupervisorKind.SERVICE.value:
        stop_supervisor(manifest)
    stop_runtime(manifest)


def _remove_deployment(manifest: DeploymentManifest) -> None:
    try:
        _stop_deployment(manifest)
    except Exception:
        pass
    try:
        remove_supervisor(manifest)
    except Exception:
        pass
    try:
        revert_mutations(manifest)
    except Exception:
        pass
    delete_manifest(manifest.profile)


def _restore_deployment(manifest: DeploymentManifest) -> None:
    restored = deepcopy(manifest)
    restored.mutations = apply_mutations(restored)
    restored.artifacts = install_supervisor(restored)
    save_manifest(restored)
    _start_deployment(restored)


def _reject_task_lifecycle(manifest: DeploymentManifest, action: str) -> None:
    if manifest.supervisor_kind == SupervisorKind.TASK.value:
        raise click.ClickException(
            f"Deployment '{manifest.profile}' uses persistent-task scheduling; "
            f"`cutctx install {action}` is not supported for task deployments."
        )


def _update_plugin_port(port: int) -> None:
    """Update installed plugin.json files to use the resolved proxy port."""
    plugins_dir = Path.home() / ".claude" / "plugins"
    if not plugins_dir.exists():
        return

    port_str = str(port)
    proxy_url = f"http://127.0.0.1:{port_str}"

    for plugin_json in plugins_dir.glob("*/plugin.json"):
        try:
            with open(plugin_json, encoding="utf-8") as f:
                plugin_data = json.load(f)

            # Update settingsUrl and configurationUrl if they reference the old port
            updated = False
            for key in ("settingsUrl", "configurationUrl"):
                if key in plugin_data:
                    plugin_data[key] = f"{proxy_url}/dashboard"
                    updated = True

            # Also check in nested interface object for codex plugins
            if "interface" in plugin_data and isinstance(plugin_data["interface"], dict):
                for key in ("settingsUrl", "configurationUrl"):
                    if key in plugin_data["interface"]:
                        plugin_data["interface"][key] = f"{proxy_url}/dashboard"
                        updated = True

            if updated:
                with open(plugin_json, "w", encoding="utf-8") as f:
                    json.dump(plugin_data, f, indent=2)
                    f.write("\n")
        except Exception:
            # Best-effort: silently ignore errors updating plugin files
            pass


@install.command("apply")
@click.option(
    "--preset",
    type=click.Choice([preset.value for preset in InstallPreset]),
    default=InstallPreset.PERSISTENT_SERVICE.value,
    show_default=True,
    help="Persistent runtime preset to install.",
)
@click.option(
    "--runtime",
    type=click.Choice([runtime.value for runtime in RuntimeKind]),
    default=RuntimeKind.PYTHON.value,
    show_default=True,
    help="Runtime used to execute Cutctx for service/task modes.",
)
@click.option(
    "--scope",
    type=click.Choice([scope.value for scope in ConfigScope]),
    default=ConfigScope.USER.value,
    show_default=True,
    help="Where to apply persistent configuration.",
)
@click.option(
    "--providers",
    "provider_mode",
    type=click.Choice([mode.value for mode in ProviderSelectionMode]),
    default=ProviderSelectionMode.AUTO.value,
    show_default=True,
    help="Target selection mode for direct tool configuration.",
)
@click.option(
    "--target",
    "targets",
    multiple=True,
    type=click.Choice(["claude", "copilot", "codex", "aider", "cursor", "gemini", "openclaw"]),
    help="Tool target to configure when --providers manual is used.",
)
@click.option("--profile", default="default", show_default=True, help="Deployment profile name.")
@click.option(
    "--port", "-p", default=8787, type=int, show_default=True, help="Persistent proxy port."
)
@click.option(
    "--backend",
    default="anthropic",
    show_default=True,
    help="Proxy backend for the persistent runtime.",
)
@click.option(
    "--anyllm-provider",
    default=None,
    help="Provider for any-llm backends when --backend anyllm is used.",
)
@click.option("--region", default=None, help="Cloud region for Bedrock / Vertex style backends.")
@click.option(
    "--mode", "proxy_mode", default="token", show_default=True, help="Proxy optimization mode."
)
@click.option("--memory", is_flag=True, help="Enable persistent memory in the proxy runtime.")
@click.option("--no-telemetry", is_flag=True, help="Disable anonymous telemetry in the runtime.")
@click.option(
    "--image",
    default="ghcr.io/cutctx/cutctx:latest",
    show_default=True,
    help="Docker image to use when runtime=docker or preset=persistent-docker.",
)
def install_apply(
    preset: str,
    runtime: str,
    scope: str,
    provider_mode: str,
    targets: tuple[str, ...],
    profile: str,
    port: int,
    backend: str,
    anyllm_provider: str | None,
    region: str | None,
    proxy_mode: str,
    memory: bool,
    no_telemetry: bool,
    image: str,
) -> None:
    """Install a persistent Cutctx deployment."""

    if preset == InstallPreset.PERSISTENT_DOCKER.value:
        runtime = RuntimeKind.DOCKER.value

    manifest = build_manifest(
        profile=profile,
        preset=preset,
        runtime_kind=runtime,
        scope=scope,
        provider_mode=provider_mode,
        targets=list(targets),
        port=port,
        backend=backend,
        anyllm_provider=anyllm_provider,
        region=region,
        proxy_mode=proxy_mode,
        memory_enabled=memory,
        telemetry_enabled=not no_telemetry,
        image=image,
    )

    existing = load_manifest(profile)
    if existing is not None:
        click.echo(f"Updating existing deployment profile '{profile}'...")
        _remove_deployment(existing)

    try:
        manifest.mutations = apply_mutations(manifest)
        manifest.artifacts = install_supervisor(manifest)
        save_manifest(manifest)
        _start_deployment(manifest)
    except Exception:
        _remove_deployment(manifest)
        if existing is not None:
            click.echo(f"Restoring previous deployment '{profile}'...")
            _restore_deployment(existing)
        raise

    click.echo(
        f"Installed persistent deployment '{profile}' "
        f"({manifest.preset}, runtime={manifest.runtime_kind}, scope={manifest.scope})."
    )
    click.echo(f"Health: {manifest.health_url}")
    if manifest.targets:
        click.echo(f"Targets: {', '.join(manifest.targets)}")

    # Update installed plugin.json files to use the resolved port
    _update_plugin_port(port)


@install.command("status")
@click.option("--profile", default="default", show_default=True, help="Deployment profile name.")
def install_status(profile: str) -> None:
    """Show persistent deployment status."""

    manifest = _require_manifest(profile)
    payload = probe_json(manifest.health_url.replace("/readyz", "/health"))
    click.echo(f"Profile:    {manifest.profile}")
    click.echo(f"Preset:     {manifest.preset}")
    click.echo(f"Runtime:    {manifest.runtime_kind}")
    click.echo(f"Supervisor: {manifest.supervisor_kind}")
    click.echo(f"Scope:      {manifest.scope}")
    click.echo(f"Port:       {manifest.port}")
    click.echo(f"Status:     {runtime_status(manifest)}")
    click.echo(f"Healthy:    {'yes' if probe_ready(manifest.health_url) else 'no'}")
    if payload and isinstance(payload, dict):
        click.echo(f"Health URL: {manifest.health_url.replace('/readyz', '/health')}")
        click.echo(f"Backend:    {payload.get('config', {}).get('backend', manifest.backend)}")


@install.command("start")
@click.option("--profile", default="default", show_default=True, help="Deployment profile name.")
def install_start(profile: str) -> None:
    """Start a persistent deployment."""

    manifest = _require_manifest(profile)
    _reject_task_lifecycle(manifest, "start")
    _start_deployment(manifest)
    click.echo(f"Started deployment '{profile}'.")


@install.command("stop")
@click.option("--profile", default="default", show_default=True, help="Deployment profile name.")
def install_stop(profile: str) -> None:
    """Stop a persistent deployment."""

    manifest = _require_manifest(profile)
    _reject_task_lifecycle(manifest, "stop")
    _stop_deployment(manifest)
    click.echo(f"Stopped deployment '{profile}'.")


@install.command("restart")
@click.option("--profile", default="default", show_default=True, help="Deployment profile name.")
def install_restart(profile: str) -> None:
    """Restart a persistent deployment."""

    manifest = _require_manifest(profile)
    _reject_task_lifecycle(manifest, "restart")
    _stop_deployment(manifest)
    _start_deployment(manifest)
    click.echo(f"Restarted deployment '{profile}'.")


@install.command("remove")
@click.option("--profile", default="default", show_default=True, help="Deployment profile name.")
def install_remove(profile: str) -> None:
    """Remove a persistent deployment and undo managed config."""

    manifest = _require_manifest(profile)
    try:
        if manifest.supervisor_kind == SupervisorKind.SERVICE.value:
            stop_supervisor(manifest)
    except Exception:
        pass
    try:
        stop_runtime(manifest)
    except Exception:
        pass
    try:
        remove_supervisor(manifest)
    except Exception:
        pass
    revert_mutations(manifest)
    delete_manifest(profile)
    click.echo(f"Removed deployment '{profile}'.")


@install.group("agent", hidden=True)
def install_agent() -> None:
    """Hidden runtime helpers used by persistent supervisors."""


@install_agent.command("run")
@click.option("--profile", default="default", show_default=True, help="Deployment profile name.")
def install_agent_run(profile: str) -> None:
    """Run the persistent runtime in the foreground."""

    manifest = _require_manifest(profile)
    raise SystemExit(run_foreground(manifest))


@install_agent.command("ensure")
@click.option("--profile", default="default", show_default=True, help="Deployment profile name.")
def install_agent_ensure(profile: str) -> None:
    """Ensure a persistent deployment is healthy, starting it when needed."""

    manifest = _require_manifest(profile)
    if probe_ready(manifest.health_url):
        click.echo(f"Deployment '{profile}' is already healthy.")
        return
    _start_deployment(manifest)
    click.echo(f"Deployment '{profile}' is healthy.")

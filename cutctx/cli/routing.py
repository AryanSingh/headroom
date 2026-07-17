"""Read-only model-routing status commands."""

from __future__ import annotations

import os

import click
import httpx

from cutctx.cli.main import main


def _safe_savings_experience_enabled() -> bool:
    return os.getenv("CUTCTX_SAFE_SAVINGS_EXPERIENCE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _proxy_url(value: str | None) -> str:
    resolved = value or os.getenv("CUTCTX_PROXY_URL") or "http://127.0.0.1:8787"
    return resolved.rstrip("/")


def _admin_headers(admin_key: str | None) -> dict[str, str]:
    key = admin_key or os.getenv("CUTCTX_ADMIN_API_KEY", "")
    return {"x-cutctx-admin-key": key} if key else {}


@main.group("routing", hidden=not _safe_savings_experience_enabled())
def routing() -> None:
    """Inspect safe model-routing decisions."""


@routing.command("status")
@click.option("--proxy-url", help="Cutctx proxy URL (defaults to CUTCTX_PROXY_URL)")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", help="Admin API key")
def status(proxy_url: str | None, admin_key: str | None) -> None:
    """Show the live, read-only Safe Savings routing status."""
    try:
        response = httpx.get(
            f"{_proxy_url(proxy_url)}/v1/orchestration/safe-savings/status",
            headers=_admin_headers(admin_key),
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise click.ClickException(f"Could not retrieve Safe Savings status: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise click.ClickException(
            "Proxy returned an invalid Safe Savings status response"
        ) from exc

    if not isinstance(payload, dict):
        raise click.ClickException("Proxy returned an invalid Safe Savings status response")

    enabled = bool(payload.get("enabled"))
    click.echo(f"Guided Safe Savings: {'ON' if enabled else 'OFF'}")
    click.echo(f"Mode: {payload.get('mode', 'off')}")
    if payload.get("preset"):
        click.echo(f"Preset: {payload['preset']}")
    click.echo(f"Configured routes: {int(payload.get('route_count') or 0)}")
    if not enabled:
        click.echo("Requests retain the originally requested model.")
        return

    routes = payload.get("routes")
    if isinstance(routes, list) and routes:
        click.echo("Eligible exact routes:")
        for route in routes:
            if not isinstance(route, dict):
                continue
            source = route.get("source_model")
            low_target = route.get("low_target_model")
            if source and low_target:
                low_posture = (
                    "transport-safe" if route.get("low_target_transport_safe") else "restricted"
                )
                click.echo(f"  {source} -> {low_target} (low, {low_posture})")
            medium_target = route.get("medium_target_model")
            if source and medium_target:
                medium_posture = (
                    "transport-safe" if route.get("medium_target_transport_safe") else "restricted"
                )
                click.echo(f"  {source} -> {medium_target} (medium, {medium_posture})")

    decision = payload.get("decision")
    if not isinstance(decision, dict):
        click.echo("Recent decision: none observed")
        return

    disposition = "applied" if decision.get("applied") else "retained"
    requested_model = decision.get("requested_model") or "unknown"
    effective_model = decision.get("effective_model") or requested_model
    click.echo(f"Recent decision: {disposition} {requested_model} -> {effective_model}")
    if decision.get("title"):
        click.echo(f"Reason: {decision['title']}")
    if decision.get("explanation"):
        click.echo(str(decision["explanation"]))
    if decision.get("confidence") is not None:
        click.echo(f"Confidence: {float(decision['confidence']):.2f}")
    signals = decision.get("signals")
    if isinstance(signals, list) and signals:
        click.echo(f"Signals: {', '.join(str(signal) for signal in signals)}")

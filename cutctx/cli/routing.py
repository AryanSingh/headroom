"""Read-only Safe Savings routing status commands."""

from __future__ import annotations

import click
import httpx

from cutctx.cli.main import main
from cutctx.proxy.safe_savings_status import safe_savings_experience_enabled


def _headers(admin_key: str) -> dict[str, str]:
    return {"x-cutctx-admin-key": admin_key} if admin_key else {}


@main.group("routing", hidden=not safe_savings_experience_enabled())
def routing_group() -> None:
    """Inspect conservative model-routing decisions."""


@routing_group.command("status")
@click.option("--proxy-url", envvar="CUTCTX_PROXY_URL", default="http://127.0.0.1:8787")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", default="")
def routing_status(proxy_url: str, admin_key: str) -> None:
    """Show Safe Savings eligibility and the latest routing decision."""
    url = f"{proxy_url.rstrip('/')}/v1/orchestration/safe-savings/status"
    try:
        response = httpx.get(url, headers=_headers(admin_key), timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise click.ClickException(f"Unable to read Safe Savings status: {exc}") from exc
    payload = response.json()
    mode = str(payload.get("mode") or "off")
    click.echo(f"Safe Savings: {mode.title()}")
    if mode == "off":
        click.echo("Requests retain the originally requested model.")
        return
    preset = payload.get("preset") or "custom"
    click.echo(f"Preset: {preset}")
    click.echo("Eligible exact routes:")
    for route in payload.get("routes", []):
        low_safe = "transport-safe" if route.get("low_target_transport_safe") else "restricted"
        click.echo(
            f"  {route['source_model']} -> {route['low_target_model']} "
            f"(low, {low_safe})"
        )
        if route.get("medium_target_model"):
            medium_safe = (
                "transport-safe"
                if route.get("medium_target_transport_safe")
                else "restricted"
            )
            click.echo(
                f"  {route['source_model']} -> {route['medium_target_model']} "
                f"(medium, {medium_safe})"
            )
    decision = payload.get("decision")
    if not isinstance(decision, dict):
        click.echo("Recent decision: none observed")
        return
    state = "applied" if decision.get("applied") else "retained"
    click.echo(
        f"Recent decision: {state} "
        f"{decision.get('requested_model')} -> {decision.get('effective_model')}"
    )
    click.echo(f"Reason: {decision.get('title')}")
    click.echo(str(decision.get("explanation") or ""))
    if decision.get("confidence") is not None:
        click.echo(f"Confidence: {float(decision['confidence']):.2f}")

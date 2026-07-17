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
    return (value or os.getenv("CUTCTX_PROXY_URL", "http://127.0.0.1:8787")).rstrip("/")


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
        raise click.ClickException("Proxy returned an invalid Safe Savings status response") from exc

    if not isinstance(payload, dict):
        raise click.ClickException("Proxy returned an invalid Safe Savings status response")

    enabled = bool(payload.get("enabled"))
    click.echo(f"Guided Safe Savings: {'ON' if enabled else 'OFF'}")
    click.echo(f"Mode: {payload.get('mode', 'off')}")
    if payload.get("preset"):
        click.echo(f"Preset: {payload['preset']}")
    click.echo(f"Configured routes: {int(payload.get('route_count') or 0)}")

    decision = payload.get("decision")
    if isinstance(decision, dict) and decision.get("state"):
        click.echo(f"Current decision: {decision['state']}")
        if decision.get("reason_title"):
            click.echo(f"Reason: {decision['reason_title']}")
        if decision.get("reason_explanation"):
            click.echo(str(decision["reason_explanation"]))

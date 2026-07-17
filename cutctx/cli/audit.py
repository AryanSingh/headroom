"""cutctx audit — query and export audit logs."""

from __future__ import annotations

import json
import os

import click
import httpx


def _api_base() -> str:
    return os.getenv("CUTCTX_PROXY_URL", "http://127.0.0.1:8787")


def _admin_headers(admin_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = admin_key or os.getenv("CUTCTX_ADMIN_API_KEY", "")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


@click.group()
def audit() -> None:
    """Query and export audit logs."""


@audit.command("list")
@click.option("--action", "-a", help="Filter by action type (e.g. org.created)")
@click.option("--actor", help="Filter by actor")
@click.option("--limit", "-n", default=20, help="Max events to show")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", help="Admin API key")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def list_events(
    action: str | None, actor: str | None, limit: int, admin_key: str | None, as_json: bool = False
) -> None:
    """List recent audit events."""
    try:
        params: dict[str, str | int] = {"limit": limit}
        if action:
            params["action"] = action
        if actor:
            params["actor"] = actor
        r = httpx.get(
            f"{_api_base()}/audit/events",
            params=params,
            headers=_admin_headers(admin_key),
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        events = data.get("events", [])
        if as_json:
            click.echo(json.dumps(events, indent=2, default=str))
            return
        if not events:
            click.echo("No audit events found.")
            return
        for e in events:
            ts = e.get("timestamp", "?")[:19]
            action_str = e.get("action", "?")
            actor_str = e.get("actor", "?")
            success = "OK" if e.get("success", True) else "FAIL"
            detail = e.get("detail", "")
            if isinstance(detail, dict):
                detail = json.dumps(detail, ensure_ascii=False)[:80]
            click.echo(f"  [{ts}] {action_str} by {actor_str} — {success}")
            if detail:
                click.echo(f"    {detail}")
    except Exception as e:
        click.echo(f"Error: {e}")


@audit.command("export")
@click.option(
    "--format", "fmt", type=click.Choice(["json", "jsonl"]), default="json", help="Export format"
)
@click.option("--output", "-o", help="Output file (default: stdout)")
@click.option("--action", help="Filter by action type")
@click.option("--limit", "-n", default=500, help="Max events")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", help="Admin API key")
def export_events(
    fmt: str, output: str | None, action: str | None, limit: int, admin_key: str | None
) -> None:
    """Export audit log as JSON or JSONL."""
    try:
        params: dict[str, str | int] = {"format": fmt, "limit": limit}
        if action:
            params["action"] = action
        r = httpx.get(
            f"{_api_base()}/audit/export",
            params=params,
            headers=_admin_headers(admin_key),
            timeout=30,
        )
        r.raise_for_status()
        content = r.text
        if output:
            with open(output, "w") as f:
                f.write(content)
            click.echo(f"Exported to {output}")
        else:
            click.echo(content)
    except Exception as e:
        click.echo(f"Error: {e}")


@audit.command("stats")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", help="Admin API key")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def audit_stats(admin_key: str | None, as_json: bool = False) -> None:
    """Show audit log statistics."""
    try:
        r = httpx.get(
            f"{_api_base()}/audit/events",
            params={"limit": 1000},
            headers=_admin_headers(admin_key),
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        events = data.get("events", [])
        by_action: dict[str, int] = {}
        for e in events:
            a = e.get("action", "unknown")
            by_action[a] = by_action.get(a, 0) + 1
        result = {
            "total": len(events),
            "by_action": dict(sorted(by_action.items(), key=lambda x: -x[1])),
        }
        if as_json:
            click.echo(json.dumps(result, indent=2, default=str))
            return
        click.echo(f"Total events loaded: {len(events)}")
        if by_action:
            click.echo("\nBy action:")
            for a, count in result["by_action"].items():
                click.echo(f"  {a}: {count}")
    except Exception as e:
        click.echo(f"Error: {e}")

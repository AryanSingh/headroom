"""cutctx orgs — manage organizations via the proxy admin API."""

from __future__ import annotations

import os

import click
import httpx

from cutctx.cli.admin_auth import admin_headers, raise_for_cli_status


def _api_base() -> str:
    return os.getenv("CUTCTX_PROXY_URL", "http://127.0.0.1:8787")


def _admin_headers(admin_key: str | None) -> dict[str, str]:
    return admin_headers(admin_key, _api_base())


def _unwrap_list(data: object, *keys: str) -> list:
    """Pull a list out of an API envelope, tolerating either spelling."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _unwrap_obj(data: object, *keys: str) -> dict:
    """Pull an object out of an API envelope, tolerating a bare object.

    H11a: every org endpoint wraps its payload (``{"org": {...}}``), but the
    CLI read the fields off the envelope, so `create` printed ``id=?`` and
    `show` printed ``?/?/?``.
    """
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, dict):
                return value
        return data
    return {}


@click.group()
def orgs() -> None:
    """Manage organizations."""


@orgs.command("list")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", help="Admin API key")
def list_orgs(admin_key: str | None) -> None:
    """List all organizations."""
    try:
        r = httpx.get(f"{_api_base()}/orgs", headers=_admin_headers(admin_key), timeout=10)
        raise_for_cli_status(r)
        data = r.json()
        # H11a: the API returns {"orgs": [...]} but this read "organizations",
        # so the list was always empty and the command reported
        # "No organizations found." while GET /orgs returned real rows.
        orgs_list = _unwrap_list(data, "orgs", "organizations")
        if not orgs_list:
            click.echo("No organizations found.")
            return
        for o in orgs_list:
            click.echo(f"  {o.get('name', '?')} ({o.get('slug', '?')}) — {o.get('id', '?')}")
    except Exception as e:
        raise click.ClickException(str(e)) from e


def _validate_email(ctx: click.Context, param: click.Parameter, value: str) -> str:
    """Basic email validation callback: reject values without '@' and '.'."""
    if value and ("@" not in value or "." not in value):
        raise click.BadParameter(
            f"'{value}' is not a valid email address (must contain @ and .)",
            ctx=ctx,
            param=param,
        )
    return value


@orgs.command("create")
@click.option("--name", "-n", required=True, prompt="Organization Name", help="Organization Name")
@click.option("--email", prompt="Admin email", callback=_validate_email, help="Admin email address")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", help="Admin API key")
def create_org(name: str, email: str, admin_key: str | None) -> None:
    """Create a new organization."""
    try:
        r = httpx.post(
            f"{_api_base()}/orgs",
            headers=_admin_headers(admin_key),
            json={"name": name, "admin_email": email},
            timeout=10,
        )
        raise_for_cli_status(r)
        org = _unwrap_obj(r.json(), "org", "organization")
        click.echo(f"Created: {org.get('name', name)} (id={org.get('id', '?')})")
    except Exception as e:
        raise click.ClickException(str(e)) from e


@orgs.command("delete")
@click.argument("org_id")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", help="Admin API key")
@click.confirmation_option(prompt="Are you sure?")
def delete_org(org_id: str, admin_key: str | None) -> None:
    """Delete an organization and all its workspaces/projects."""
    try:
        r = httpx.delete(
            f"{_api_base()}/orgs/{org_id}", headers=_admin_headers(admin_key), timeout=10
        )
        raise_for_cli_status(r)
        click.echo(f"Deleted org {org_id}")
    except Exception as e:
        raise click.ClickException(str(e)) from e


@orgs.command("show")
@click.argument("org_id")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", help="Admin API key")
def show_org(org_id: str, admin_key: str | None) -> None:
    """Show organization details with hierarchy."""
    try:
        r = httpx.get(f"{_api_base()}/orgs/{org_id}", headers=_admin_headers(admin_key), timeout=10)
        raise_for_cli_status(r)
        data = _unwrap_obj(r.json(), "org", "organization")
        click.echo(f"Organization: {data.get('name', '?')}")
        click.echo(f"  ID: {data.get('id', '?')}")
        click.echo(f"  Slug: {data.get('slug', '?')}")
        workspaces = data.get("workspaces", [])
        for ws in workspaces:
            click.echo(f"  Workspace: {ws.get('name', '?')}")
            for proj in ws.get("projects", []):
                click.echo(f"    Project: {proj.get('name', '?')}")
    except Exception as e:
        raise click.ClickException(str(e)) from e

"""cutctx rbac — manage role-based access control."""

from __future__ import annotations

import os

import click
import httpx

from cutctx.cli.admin_auth import admin_headers, raise_for_cli_status


def _api_base() -> str:
    return os.getenv("CUTCTX_PROXY_URL", "http://127.0.0.1:8787")


def _admin_headers(admin_key: str | None) -> dict[str, str]:
    return admin_headers(admin_key, _api_base())


@click.group()
def rbac() -> None:
    """Manage role-based access control."""


@rbac.command("list")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", help="Admin API key")
def list_roles(admin_key: str | None) -> None:
    """List all role assignments."""
    try:
        r = httpx.get(f"{_api_base()}/rbac/roles", headers=_admin_headers(admin_key), timeout=10)
        raise_for_cli_status(r)
        data = r.json()
        assignments = data.get("assignments", {})
        if not assignments:
            click.echo("No role assignments. Unassigned users default to read-only viewer.")
            return
        click.echo("Role assignments:")
        for user_id, role in assignments.items():
            click.echo(f"  {user_id}: {role}")
    except Exception as e:
        raise click.ClickException(str(e)) from e


@rbac.command("assign")
@click.argument("user_id")
@click.option(
    "--role",
    type=click.Choice(["viewer", "memory_curator", "operator", "admin"]),
    required=True,
    help="Role to assign",
)
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", help="Admin API key")
def assign_role(user_id: str, role: str, admin_key: str | None) -> None:
    """Assign a role to a user."""
    try:
        r = httpx.post(
            f"{_api_base()}/rbac/roles",
            headers=_admin_headers(admin_key),
            json={"user_id": user_id, "role": role},
            timeout=10,
        )
        raise_for_cli_status(r)
        click.echo(f"Assigned role '{role}' to user '{user_id}'")
    except Exception as e:
        raise click.ClickException(str(e)) from e


@rbac.command("revoke")
@click.argument("user_id")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", help="Admin API key")
@click.confirmation_option(prompt="Revoke this user's role?")
def revoke_role(user_id: str, admin_key: str | None) -> None:
    """Revoke a user's role assignment."""
    try:
        r = httpx.delete(
            f"{_api_base()}/rbac/roles/{user_id}",
            headers=_admin_headers(admin_key),
            timeout=10,
        )
        raise_for_cli_status(r)
        click.echo(f"Revoked role for user '{user_id}'")
    except Exception as e:
        raise click.ClickException(str(e)) from e

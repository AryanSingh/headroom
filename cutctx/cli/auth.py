"""Manage least-privilege Cutctx client credentials."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from typing import Any, TypeVar, cast

import click

from cutctx.auth.client_credentials import (
    ClientCredential,
    ClientCredentialError,
    KeyringClientCredentialStore,
    apply_client_auth,
    normalize_proxy_origin,
    resolve_client_credential,
    validate_client_credential,
)

from .main import main

_DEFAULT_PROXY_URL = "http://127.0.0.1:8787"
_CommandFunction = TypeVar("_CommandFunction", bound=Callable[..., Any])


def _store() -> KeyringClientCredentialStore:
    return KeyringClientCredentialStore()


def _origin(proxy_url: str | None) -> str:
    return normalize_proxy_origin(
        proxy_url or os.environ.get("CUTCTX_PROXY_URL") or _DEFAULT_PROXY_URL
    )


def _prompt_key() -> str:
    key = cast(
        str,
        click.prompt(
            "Cutctx client API key",
            hide_input=True,
            confirmation_prompt=False,
            type=str,
        ),
    ).strip()
    if not key:
        raise click.ClickException("Client credential must not be empty.")
    return key


def _validate_for_persistence(origin: str, key: str) -> None:
    status = validate_client_credential(
        origin,
        ClientCredential(origin, key, "keyring"),
    )
    if status.state == "valid":
        return
    if status.state == "expired":
        raise click.ClickException(f"Cutctx client authentication expired for {origin}.")
    if status.state == "unreachable":
        raise click.ClickException(f"Could not reach the Cutctx client-auth endpoint at {origin}.")
    raise click.ClickException(f"Cutctx client authentication is invalid for {origin}.")


def _proxy_url_option(function: _CommandFunction) -> _CommandFunction:
    return cast(
        _CommandFunction,
        click.option(
            "--proxy-url",
            default=None,
            envvar="CUTCTX_PROXY_URL",
            help=f"Cutctx proxy URL (default: {_DEFAULT_PROXY_URL})",
        )(function),
    )


@main.group("auth")
def auth() -> None:
    """Configure reusable least-privilege client authentication."""


@auth.command("login")
@_proxy_url_option
def auth_login(proxy_url: str | None) -> None:
    """Validate and securely store a client credential."""

    origin = _origin(proxy_url)
    key = _prompt_key()
    try:
        _validate_for_persistence(origin, key)
        _store().set(origin, key)
    except ClientCredentialError as exc:
        raise click.ClickException(str(exc)) from None
    click.echo(f"Client authentication configured for {origin}.")


@auth.command("rotate")
@_proxy_url_option
def auth_rotate(proxy_url: str | None) -> None:
    """Validate a replacement before overwriting the current credential."""

    origin = _origin(proxy_url)
    key = _prompt_key()
    try:
        _validate_for_persistence(origin, key)
        _store().set(origin, key)
    except ClientCredentialError as exc:
        raise click.ClickException(str(exc)) from None
    click.echo(f"Client authentication rotated for {origin}.")


@auth.command("status")
@_proxy_url_option
def auth_status(proxy_url: str | None) -> None:
    """Report credential source and validation state without displaying it."""

    origin = _origin(proxy_url)
    try:
        credential = resolve_client_credential(origin, store=_store())
    except ClientCredentialError as exc:
        raise click.ClickException(str(exc)) from None
    if credential is None:
        click.echo(f"Origin: {origin}")
        click.echo("State: not_configured")
        raise click.exceptions.Exit(1)

    status = validate_client_credential(origin, credential)
    click.echo(f"Origin: {origin}")
    click.echo(f"Source: {credential.source}")
    click.echo(f"State: {status.state}")
    if status.expires_at:
        click.echo(f"Expires: {status.expires_at}")
    if status.state != "valid":
        raise click.exceptions.Exit(1)


@auth.command("logout")
@_proxy_url_option
def auth_logout(proxy_url: str | None) -> None:
    """Remove the stored credential for one proxy origin."""

    origin = _origin(proxy_url)
    try:
        removed = _store().delete(origin)
    except ClientCredentialError as exc:
        raise click.ClickException(str(exc)) from None
    if removed:
        click.echo(f"Stored client authentication removed for {origin}.")
    else:
        click.echo(f"No stored client authentication found for {origin}.")


@auth.command(
    "exec",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
)
@_proxy_url_option
@click.argument("command", nargs=-1, required=True, type=click.UNPROCESSED)
def auth_exec(proxy_url: str | None, command: tuple[str, ...]) -> None:
    """Run an arbitrary CLI with CUTCTX_API_KEY in its child environment."""

    origin = _origin(proxy_url)
    child_env = dict(os.environ)
    try:
        apply_client_auth(
            child_env,
            proxy_url=origin,
            required=True,
            store=_store(),
        )
    except ClientCredentialError as exc:
        raise click.ClickException(str(exc)) from None

    try:
        result = subprocess.run(command, env=child_env)
    except OSError as exc:
        raise click.ClickException(
            f"Unable to launch {command[0]!r}: {exc.strerror or 'execution failed'}"
        ) from None
    raise click.exceptions.Exit(result.returncode)

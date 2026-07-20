from __future__ import annotations

import pytest

from cutctx.auth.client_credentials import ClientCredential
from cutctx.cli import proxy as proxy_cli


def test_server_side_environment_key_wins_without_keyring_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        proxy_cli,
        "resolve_client_credential",
        lambda *args, **kwargs: pytest.fail("keyring resolution must not run"),
        raising=False,
    )

    resolved = proxy_cli._resolve_client_api_key_for_bind(
        host="127.0.0.1",
        port=8787,
        tls_enabled=False,
        environ={
            "CUTCTX_CLIENT_API_KEY": "server-secret",
            "CUTCTX_API_KEY": "client-secret",
        },
    )

    assert resolved == "server-secret"


def test_foreground_client_environment_can_supply_same_process_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        proxy_cli,
        "resolve_client_credential",
        lambda *args, **kwargs: pytest.fail("keyring resolution must not run"),
        raising=False,
    )

    resolved = proxy_cli._resolve_client_api_key_for_bind(
        host="127.0.0.1",
        port=8787,
        tls_enabled=False,
        environ={"CUTCTX_API_KEY": "client-secret"},
    )

    assert resolved == "client-secret"


def test_loopback_proxy_resolves_origin_scoped_keyring_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origins: list[str] = []
    monkeypatch.setattr(
        proxy_cli,
        "resolve_client_credential",
        lambda url, **kwargs: origins.append(url)
        or ClientCredential(url, "stored-secret", "keyring"),
        raising=False,
    )

    resolved = proxy_cli._resolve_client_api_key_for_bind(
        host="127.0.0.1",
        port=8787,
        tls_enabled=False,
        environ={},
    )

    assert resolved == "stored-secret"
    assert origins == ["http://127.0.0.1:8787"]


def test_non_loopback_proxy_requires_explicit_public_origin_for_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        proxy_cli,
        "resolve_client_credential",
        lambda *args, **kwargs: pytest.fail("must not guess a public origin"),
        raising=False,
    )

    resolved = proxy_cli._resolve_client_api_key_for_bind(
        host="0.0.0.0",
        port=8787,
        tls_enabled=False,
        environ={},
    )

    assert resolved is None


def test_non_loopback_proxy_uses_explicit_public_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origins: list[str] = []
    monkeypatch.setattr(
        proxy_cli,
        "resolve_client_credential",
        lambda url, **kwargs: origins.append(url)
        or ClientCredential(url, "stored-secret", "keyring"),
        raising=False,
    )

    resolved = proxy_cli._resolve_client_api_key_for_bind(
        host="0.0.0.0",
        port=8787,
        tls_enabled=True,
        environ={"CUTCTX_PUBLIC_URL": "https://proxy.example/base"},
    )

    assert resolved == "stored-secret"
    assert origins == ["https://proxy.example/base"]

from __future__ import annotations

import base64
from dataclasses import dataclass, field

import httpx
import pytest

from cutctx.auth.client_credentials import (
    ClientCredential,
    ClientCredentialConfigError,
    ClientCredentialStatus,
    ClientCredentialStoreError,
    ClientCredentialUnavailableError,
    KeyringClientCredentialStore,
    apply_client_auth,
    ensure_local_client_credential,
    normalize_proxy_origin,
    resolve_client_credential,
    validate_client_credential,
)


@dataclass
class FakeKeyring:
    values: dict[tuple[str, str], str] = field(default_factory=dict)
    saved: tuple[str, str, str] | None = None

    def get_password(self, service: str, account: str) -> str | None:
        return self.values.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        self.saved = (service, account, value)
        self.values[(service, account)] = value

    def delete_password(self, service: str, account: str) -> None:
        self.values.pop((service, account), None)


@dataclass
class MemoryStore:
    values: dict[str, str] = field(default_factory=dict)
    set_calls: list[tuple[str, str]] = field(default_factory=list)

    def get(self, proxy_origin: str) -> str | None:
        return self.values.get(normalize_proxy_origin(proxy_origin))

    def set(self, proxy_origin: str, value: str) -> None:
        origin = normalize_proxy_origin(proxy_origin)
        self.values[origin] = value
        self.set_calls.append((origin, value))

    def delete(self, proxy_origin: str) -> bool:
        return self.values.pop(normalize_proxy_origin(proxy_origin), None) is not None


def test_normalize_proxy_origin_is_stable_and_rejects_secret_bearing_urls() -> None:
    assert normalize_proxy_origin("HTTP://LOCALHOST:80/v1/") == "http://localhost"
    assert (
        normalize_proxy_origin("https://Proxy.Example:443/api")
        == "https://proxy.example"
    )
    assert normalize_proxy_origin("http://[::1]:8787/v1") == "http://[::1]:8787"

    with pytest.raises(ClientCredentialConfigError):
        normalize_proxy_origin("https://user:secret@proxy.example")
    with pytest.raises(ClientCredentialConfigError):
        normalize_proxy_origin("https://proxy.example?key=secret")


def test_keyring_account_uses_non_secret_origin_digest() -> None:
    backend = FakeKeyring()
    store = KeyringClientCredentialStore(keyring_backend=backend)

    store.set("https://proxy.example", "client-secret")

    assert backend.saved is not None
    service, account, value = backend.saved
    assert service == "cutctx"
    assert account.startswith("client-api-key:")
    assert "proxy.example" not in account
    assert value == "client-secret"
    assert store.get("https://proxy.example") == "client-secret"
    assert store.delete("https://proxy.example") is True
    assert store.delete("https://proxy.example") is False


def test_keyring_errors_are_redacted() -> None:
    class FailingKeyring:
        def get_password(self, service: str, account: str) -> str | None:
            raise RuntimeError("backend payload contains client-secret")

    store = KeyringClientCredentialStore(keyring_backend=FailingKeyring())

    with pytest.raises(ClientCredentialStoreError) as exc_info:
        store.get("https://proxy.example")

    assert "client-secret" not in str(exc_info.value)
    assert "backend payload" not in str(exc_info.value)


def test_environment_wins_without_persisting() -> None:
    store = MemoryStore({"http://127.0.0.1:8787": "stored-secret"})

    credential = resolve_client_credential(
        "http://127.0.0.1:8787",
        environ={"CUTCTX_API_KEY": "env-secret"},
        store=store,
    )

    assert credential == ClientCredential(
        proxy_origin="http://127.0.0.1:8787",
        value="env-secret",
        source="environment",
    )
    assert store.set_calls == []


def test_ensure_local_generates_256_bit_secret_once() -> None:
    store = MemoryStore()

    first = ensure_local_client_credential(
        "http://127.0.0.1:8787",
        environ={},
        store=store,
    )
    second = ensure_local_client_credential(
        "http://127.0.0.1:8787",
        environ={},
        store=store,
    )

    padded = first.value + ("=" * (-len(first.value) % 4))
    assert len(base64.urlsafe_b64decode(padded)) >= 32
    assert first.value == second.value
    assert len(store.set_calls) == 1


def test_ensure_local_rejects_remote_origin() -> None:
    with pytest.raises(ClientCredentialConfigError, match="loopback"):
        ensure_local_client_credential(
            "https://proxy.example",
            environ={},
            store=MemoryStore(),
        )


def test_required_auth_fails_closed_when_credential_is_missing() -> None:
    with pytest.raises(ClientCredentialUnavailableError, match="cutctx auth login"):
        apply_client_auth(
            {},
            proxy_url="https://proxy.example",
            required=True,
            store=MemoryStore(),
        )


def test_apply_client_auth_mutates_only_supplied_child_environment() -> None:
    parent = {"UNCHANGED": "1"}
    child = dict(parent)
    store = MemoryStore({"https://proxy.example": "stored-secret"})

    result = apply_client_auth(
        child,
        proxy_url="https://proxy.example/v1",
        required=True,
        store=store,
    )

    assert child["CUTCTX_API_KEY"] == "stored-secret"
    assert "CUTCTX_API_KEY" not in parent
    assert result.configured is True
    assert result.source == "keyring"
    assert "stored-secret" not in repr(result)


@pytest.mark.parametrize(
    ("status_code", "payload", "expected"),
    [
        (
            200,
            {
                "status": "valid",
                "credential_kind": "client",
                "expires_at": None,
            },
            "valid",
        ),
        (
            200,
            {
                "status": "valid",
                "credential_kind": "admin_compat",
                "expires_at": None,
            },
            "invalid",
        ),
        (401, {"error": {"code": "invalid_client_key"}}, "invalid"),
        (401, {"error": {"code": "expired_client_key"}}, "expired"),
        (401, {"error": {"code": "revoked_client_key"}}, "expired"),
    ],
)
def test_validation_preserves_actionable_status(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    payload: dict[str, object],
    expected: str,
) -> None:
    request = httpx.Request("GET", "https://proxy.example/v1/auth/client/status")
    response = httpx.Response(status_code, request=request, json=payload)
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: response)

    status = validate_client_credential(
        "https://proxy.example",
        ClientCredential(
            "https://proxy.example",
            "client-secret",
            "environment",
        ),
    )

    assert status.state == expected
    assert "client-secret" not in repr(status)


def test_validation_reports_unreachable_without_leaking_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> httpx.Response:
        request = httpx.Request(
            "GET",
            "https://proxy.example/v1/auth/client/status",
        )
        raise httpx.ConnectError("client-secret must stay hidden", request=request)

    monkeypatch.setattr(httpx, "get", fail)

    status = validate_client_credential(
        "https://proxy.example",
        ClientCredential(
            "https://proxy.example",
            "client-secret",
            "environment",
        ),
    )

    assert status == ClientCredentialStatus(state="unreachable")
    assert "client-secret" not in repr(status)

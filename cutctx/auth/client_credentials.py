"""Origin-scoped, least-privilege client credentials.

Client processes consume ``CUTCTX_API_KEY``. Proxy processes consume the
same value under ``CUTCTX_CLIENT_API_KEY``. Persistence is delegated to the
operating system credential manager through :mod:`keyring`.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import secrets
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Literal, Protocol
from urllib.parse import urlsplit

import httpx

_SERVICE_NAME = "cutctx"
_CLIENT_ENV = "CUTCTX_API_KEY"
_INSECURE_BACKEND_MARKERS = (
    "keyring.backends.fail",
    "keyring.backends.null",
    "keyrings.alt.file",
    "plaintextkeyring",
)


class ClientCredentialError(RuntimeError):
    """Base error for client credential operations."""


class ClientCredentialConfigError(ClientCredentialError, ValueError):
    """Raised when a proxy origin or credential configuration is invalid."""


class ClientCredentialStoreError(ClientCredentialError):
    """Raised when the protected credential store cannot be used."""


class ClientCredentialUnavailableError(ClientCredentialError):
    """Raised when an operation requires a credential but none is configured."""


@dataclass(frozen=True)
class ClientCredential:
    """A resolved client credential and its non-secret provenance."""

    proxy_origin: str
    value: str = field(repr=False)
    source: Literal["environment", "keyring", "generated"]


@dataclass(frozen=True)
class ClientAuthResult:
    """Redaction-safe result of applying authentication to a child environment."""

    proxy_origin: str
    configured: bool
    source: str | None


@dataclass(frozen=True)
class ClientCredentialStatus:
    """Redaction-safe validation result returned by a proxy."""

    state: Literal["valid", "invalid", "expired", "unreachable", "not_configured"]
    expires_at: str | None = None


class ClientCredentialStore(Protocol):
    """Persistence contract for origin-scoped client credentials."""

    def get(self, proxy_origin: str) -> str | None: ...

    def set(self, proxy_origin: str, value: str) -> None: ...

    def delete(self, proxy_origin: str) -> bool: ...


def normalize_proxy_origin(proxy_url: str) -> str:
    """Return a canonical HTTP(S) origin without retaining URL secrets."""

    try:
        parsed = urlsplit(proxy_url.strip())
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ClientCredentialConfigError(
            "Proxy URL must be a valid absolute HTTP(S) URL."
        ) from exc

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise ClientCredentialConfigError("Proxy URL must be an absolute HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ClientCredentialConfigError(
            "Proxy URL must not contain user info, query credentials, or fragments."
        )

    host = parsed.hostname.lower()
    authority = f"[{host}]" if ":" in host else host
    default_port = 80 if scheme == "http" else 443
    if port is not None and port != default_port:
        authority = f"{authority}:{port}"
    return f"{scheme}://{authority}"


def _account_name(proxy_origin: str) -> str:
    digest = hashlib.sha256(proxy_origin.encode("utf-8")).hexdigest()
    return f"client-api-key:{digest}"


def _default_keyring_backend() -> object:
    try:
        import keyring

        backend = keyring.get_keyring()
        backend_name = (f"{type(backend).__module__}.{type(backend).__qualname__}").lower()
        priority = float(getattr(backend, "priority", 0))
        if priority <= 0 or any(marker in backend_name for marker in _INSECURE_BACKEND_MARKERS):
            raise ClientCredentialStoreError("A secure OS credential store is unavailable.")
        return keyring
    except ClientCredentialStoreError:
        raise
    except Exception:
        raise ClientCredentialStoreError("A secure OS credential store is unavailable.") from None


class KeyringClientCredentialStore:
    """Store credentials in the platform's protected credential manager."""

    def __init__(self, *, keyring_backend: object | None = None) -> None:
        self._backend = keyring_backend or _default_keyring_backend()

    def get(self, proxy_origin: str) -> str | None:
        origin = normalize_proxy_origin(proxy_origin)
        try:
            value = self._backend.get_password(  # type: ignore[attr-defined]
                _SERVICE_NAME,
                _account_name(origin),
            )
        except Exception:
            raise ClientCredentialStoreError(
                "Unable to read the Cutctx client credential from the OS credential store."
            ) from None
        return value if isinstance(value, str) and value.strip() else None

    def set(self, proxy_origin: str, value: str) -> None:
        origin = normalize_proxy_origin(proxy_origin)
        if not value or not value.strip():
            raise ClientCredentialConfigError("Client credential must not be empty.")
        try:
            self._backend.set_password(  # type: ignore[attr-defined]
                _SERVICE_NAME,
                _account_name(origin),
                value,
            )
        except Exception:
            raise ClientCredentialStoreError(
                "Unable to save the Cutctx client credential in the OS credential store."
            ) from None

    def delete(self, proxy_origin: str) -> bool:
        origin = normalize_proxy_origin(proxy_origin)
        account = _account_name(origin)
        try:
            existing = self._backend.get_password(  # type: ignore[attr-defined]
                _SERVICE_NAME,
                account,
            )
            if not existing:
                return False
            self._backend.delete_password(  # type: ignore[attr-defined]
                _SERVICE_NAME,
                account,
            )
        except Exception:
            raise ClientCredentialStoreError(
                "Unable to remove the Cutctx client credential from the OS credential store."
            ) from None
        return True


def _store_or_default(
    store: ClientCredentialStore | None,
) -> ClientCredentialStore:
    return store if store is not None else KeyringClientCredentialStore()


def resolve_client_credential(
    proxy_url: str,
    *,
    environ: Mapping[str, str] | None = None,
    store: ClientCredentialStore | None = None,
) -> ClientCredential | None:
    """Resolve a client credential using environment-before-keyring precedence."""

    origin = normalize_proxy_origin(proxy_url)
    source_env = os.environ if environ is None else environ
    environment_value = source_env.get(_CLIENT_ENV, "")
    if environment_value and environment_value.strip():
        return ClientCredential(origin, environment_value, "environment")

    stored_value = _store_or_default(store).get(origin)
    if stored_value:
        return ClientCredential(origin, stored_value, "keyring")
    return None


def _is_loopback_origin(proxy_origin: str) -> bool:
    host = urlsplit(proxy_origin).hostname
    if host == "localhost":
        return True
    try:
        return bool(host and ipaddress.ip_address(host).is_loopback)
    except ValueError:
        return False


def ensure_local_client_credential(
    proxy_url: str,
    *,
    environ: Mapping[str, str] | None = None,
    store: ClientCredentialStore | None = None,
) -> ClientCredential:
    """Return or generate a 256-bit credential for a loopback proxy."""

    origin = normalize_proxy_origin(proxy_url)
    if not _is_loopback_origin(origin):
        raise ClientCredentialConfigError(
            "Automatic client credential generation is limited to loopback proxies."
        )

    source_env = os.environ if environ is None else environ
    environment_value = source_env.get(_CLIENT_ENV, "")
    if environment_value and environment_value.strip():
        return ClientCredential(origin, environment_value, "environment")

    credential_store = _store_or_default(store)
    stored_value = credential_store.get(origin)
    if stored_value:
        return ClientCredential(origin, stored_value, "keyring")

    generated = secrets.token_urlsafe(32)
    credential_store.set(origin, generated)
    return ClientCredential(origin, generated, "generated")


def apply_client_auth(
    env: MutableMapping[str, str],
    *,
    proxy_url: str,
    required: bool,
    store: ClientCredentialStore | None = None,
) -> ClientAuthResult:
    """Inject client auth into one supplied child environment."""

    origin = normalize_proxy_origin(proxy_url)
    credential = resolve_client_credential(origin, environ=env, store=store)
    if credential is None:
        if required:
            raise ClientCredentialUnavailableError(
                f"Cutctx client authentication is not configured for {origin}. "
                "Run `cutctx auth login`."
            )
        return ClientAuthResult(origin, False, None)

    env[_CLIENT_ENV] = credential.value
    return ClientAuthResult(origin, True, credential.source)


def validate_client_credential(
    proxy_url: str,
    credential: ClientCredential,
    *,
    timeout: float = 5.0,
) -> ClientCredentialStatus:
    """Validate a credential without returning or logging secret material."""

    origin = normalize_proxy_origin(proxy_url)
    try:
        response = httpx.get(
            f"{origin}/v1/auth/client/status",
            headers={"Authorization": f"Bearer {credential.value}"},
            timeout=timeout,
        )
    except httpx.HTTPError:
        return ClientCredentialStatus("unreachable")

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code == 200:
        credential_kind = payload.get("credential_kind") if isinstance(payload, dict) else None
        if credential_kind == "admin_compat":
            return ClientCredentialStatus("invalid")
        expires_at = payload.get("expires_at") if isinstance(payload, dict) else None
        return ClientCredentialStatus(
            "valid",
            expires_at=expires_at if isinstance(expires_at, str) else None,
        )
    if response.status_code in {401, 403}:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        code = error.get("code", "") if isinstance(error, dict) else ""
        if isinstance(code, str) and ("expired" in code.lower() or "revoked" in code.lower()):
            return ClientCredentialStatus("expired")
        return ClientCredentialStatus("invalid")
    return ClientCredentialStatus("unreachable")


__all__ = [
    "ClientAuthResult",
    "ClientCredential",
    "ClientCredentialConfigError",
    "ClientCredentialError",
    "ClientCredentialStatus",
    "ClientCredentialStore",
    "ClientCredentialStoreError",
    "ClientCredentialUnavailableError",
    "KeyringClientCredentialStore",
    "apply_client_auth",
    "ensure_local_client_credential",
    "normalize_proxy_origin",
    "resolve_client_credential",
    "validate_client_credential",
]

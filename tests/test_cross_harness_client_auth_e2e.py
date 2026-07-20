from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from cutctx.auth.client_credentials import (
    KeyringClientCredentialStore,
    apply_client_auth,
)
from cutctx.mcp_registry import build_cutctx_spec
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


@dataclass
class FakeKeyring:
    values: dict[tuple[str, str], str] = field(default_factory=dict)

    def get_password(self, service: str, account: str) -> str | None:
        return self.values.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        self.values[(service, account)] = value

    def delete_password(self, service: str, account: str) -> None:
        self.values.pop((service, account), None)


def test_client_key_round_trip_and_admin_separation() -> None:
    key = "synthetic-client-key-for-e2e"
    origin = "http://127.0.0.1:8787"
    store = KeyringClientCredentialStore(keyring_backend=FakeKeyring())
    store.set(origin, key)

    child_env: dict[str, str] = {}
    auth_result = apply_client_auth(
        child_env,
        proxy_url=origin,
        required=True,
        store=store,
    )

    app = create_app(
        ProxyConfig(
            host="127.0.0.1",
            client_api_key=key,
            admin_api_key="synthetic-admin-key",
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
        )
    )
    headers = {"Authorization": f"Bearer {child_env['CUTCTX_API_KEY']}"}
    with TestClient(app, base_url=origin) as client:
        compress = client.post(
            "/v1/compress",
            headers=headers,
            json={"messages": [], "model": "gpt-4o"},
        )
        retrieve_stats = client.get("/v1/retrieve/stats", headers=headers)
        admin_stats = client.get("/stats", headers=headers)

    assert auth_result.configured is True
    assert auth_result.source == "keyring"
    assert compress.status_code == 200
    assert retrieve_stats.status_code == 200
    assert admin_stats.status_code == 401

    mcp_spec = build_cutctx_spec(origin)
    evidence = f"{auth_result!r}\n{mcp_spec!r}"
    assert key not in evidence
    assert "synthetic-admin-key" not in evidence

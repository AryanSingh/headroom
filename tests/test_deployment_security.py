from __future__ import annotations

import pytest

from cutctx.proxy.deployment_security import (
    DeploymentSecurityError,
    deployment_security_issues,
    is_loopback_host,
    require_secure_deployment,
)
from cutctx.proxy.models import ProxyConfig


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "[::1]", "localhost"])
def test_loopback_hosts_remain_compatible_without_admin_auth(host: str) -> None:
    config = ProxyConfig(host=host)

    assert is_loopback_host(host) is True
    assert deployment_security_issues(config) == []
    require_secure_deployment(config)


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "10.0.0.8", "proxy.internal"])
def test_non_loopback_requires_admin_key_or_complete_sso(host: str, monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    with pytest.raises(DeploymentSecurityError, match="admin authentication"):
        require_secure_deployment(ProxyConfig(host=host))


def test_non_loopback_rejects_admin_key_without_proxy_client_key(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("CUTCTX_PROXY_API_KEY", raising=False)
    with pytest.raises(DeploymentSecurityError, match="proxy client authentication"):
        require_secure_deployment(ProxyConfig(host="0.0.0.0", admin_api_key="test-key"))


def test_non_loopback_accepts_separate_admin_and_proxy_keys(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("CUTCTX_PROXY_API_KEY", raising=False)
    require_secure_deployment(
        ProxyConfig(
            host="0.0.0.0",
            admin_api_key="admin-key",
            proxy_api_key="proxy-key",
        )
    )


def test_non_loopback_accepts_complete_sso(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    require_secure_deployment(
        ProxyConfig(
            host="0.0.0.0",
            sso_enabled=True,
            sso_jwks_uri="https://idp.example.test/jwks",
            sso_issuer="https://idp.example.test/",
            sso_audience="cutctx",
            proxy_api_key="proxy-key",
        )
    )


def test_non_loopback_accepts_complete_sso_without_redundant_enabled_flag(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    require_secure_deployment(
        ProxyConfig(
            host="0.0.0.0",
            sso_jwks_uri="https://idp.example.test/jwks",
            sso_issuer="https://idp.example.test/",
            sso_audience="cutctx",
            proxy_api_key="proxy-key",
        )
    )


def test_non_loopback_rejects_wildcard_cors_even_with_auth(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    with pytest.raises(DeploymentSecurityError, match="Wildcard CORS"):
        require_secure_deployment(
            ProxyConfig(
                host="0.0.0.0",
                admin_api_key="test-key",
                proxy_api_key="proxy-key",
                cors_origins=["*"],
            )
        )


def test_network_deployment_rejects_private_literal_upstream(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_ALLOW_PRIVATE_UPSTREAM", raising=False)
    with pytest.raises(DeploymentSecurityError, match="private or loopback"):
        require_secure_deployment(
            ProxyConfig(
                host="0.0.0.0",
                admin_api_key="test-key",
                proxy_api_key="proxy-key",
                openai_api_url="http://127.0.0.1:9000/v1",
            )
        )


def test_network_deployment_allows_explicit_private_upstream(monkeypatch) -> None:
    monkeypatch.setenv("CUTCTX_ALLOW_PRIVATE_UPSTREAM", "1")
    require_secure_deployment(
        ProxyConfig(
            host="0.0.0.0",
            admin_api_key="test-key",
            proxy_api_key="proxy-key",
            openai_api_url="http://10.0.0.5:9000/v1",
        )
    )

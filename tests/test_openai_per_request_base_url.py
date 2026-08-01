"""Per-request OpenAI upstream override via ``x-cutctx-base-url`` (Phase 1).

Covers acceptance criteria 1-6 of ``.slim/deepwork/opencode-on-8787.md``:

1. Header absent -> process-wide upstream, unchanged.
2. ChatGPT/OAuth auth present -> chatgpt.com wins, override refused + logged.
3. Valid override -> ``https://opencode.ai/zen/go/v1/...`` from both
   ``/zen/go`` and ``/zen/go/v1`` header forms, on chat, responses and models.
4. Bad override -> distinct error + metric, no upstream connect.
5. No class-level mutation; interleaved override/non-override stay distinct.
6. Override active -> requested model preserved (no implicit downgrade).

Plus the post-review must-fixes: the operator's OpenAI credential never reaches
a client-named upstream, ``/health`` advertises the capability only when the
runtime gate could honour it, and the catch-all passthrough vets its own
``x-cutctx-base-url``.
"""

from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from cutctx.proxy import openai_upstream
from cutctx.proxy.openai_upstream import (
    OVERRIDE_HEADER,
    override_metrics_snapshot,
    reset_override_metrics,
    resolve_openai_base_url_override,
)
from cutctx.proxy.server import CutctxProxy, ProxyConfig, create_app

LOOPBACK_BASE_URL = "http://127.0.0.1:8787"
UPSTREAM = "https://opencode.ai/zen/go"
DEEPSEEK_UPSTREAM = "https://api.deepseek.com"
DEEPSEEK_UPSTREAM_V1 = f"{DEEPSEEK_UPSTREAM}/v1"
#: An override names a client-owned upstream, so the client owns the credential.
CLIENT_AUTH = {"authorization": "Bearer client-owned-key"}
#: Distinct from CLIENT_AUTH so a leak of the operator key is unmistakable.
OPERATOR_KEY = "sk-operator-must-not-leak"


@pytest.fixture(autouse=True)
def _clean_override_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(openai_upstream.ALLOWED_HOSTS_ENV, raising=False)
    monkeypatch.delenv(openai_upstream.ALLOWED_PATH_PREFIXES_ENV, raising=False)
    reset_override_metrics()


# ---------------------------------------------------------------------------
# Resolver unit tests
# ---------------------------------------------------------------------------


def _proxy_stub(bind_host: str = "127.0.0.1") -> Any:
    return SimpleNamespace(config=SimpleNamespace(host=bind_host))


def _connection_stub(client_host: str | None = "127.0.0.1") -> Any:
    return SimpleNamespace(client=SimpleNamespace(host=client_host))


def _resolve(
    value: str | None,
    *,
    is_chatgpt_auth: bool = False,
    bind_host: str = "127.0.0.1",
    client_host: str | None = "127.0.0.1",
    host_header: str = "127.0.0.1:8787",
    extra_headers: dict[str, str] | None = None,
    client_authorization: str | None = "Bearer client-owned-key",
) -> Any:
    headers = {"host": host_header}
    if value is not None:
        headers[OVERRIDE_HEADER] = value
    if client_authorization is not None:
        headers["authorization"] = client_authorization
    headers.update(extra_headers or {})
    return resolve_openai_base_url_override(
        _proxy_stub(bind_host),
        _connection_stub(client_host),
        headers,
        is_chatgpt_auth=is_chatgpt_auth,
    )


def test_absent_header_is_inert() -> None:
    decision = _resolve(None)

    assert decision.status == "absent"
    assert decision.active is False
    assert decision.rejected is False
    assert decision.base_url is None
    assert override_metrics_snapshot() == {}


def test_blank_header_is_inert() -> None:
    assert _resolve("   ").status == "absent"


def test_deepseek_root_is_an_allowed_host_specific_default() -> None:
    decision = _resolve(DEEPSEEK_UPSTREAM)

    assert decision.active is True
    assert decision.base_url == DEEPSEEK_UPSTREAM
    assert decision.host == "api.deepseek.com"


def test_deepseek_root_rule_does_not_open_opencode_root() -> None:
    decision = _resolve("https://opencode.ai")

    assert decision.rejected is True
    assert decision.reason == "path_not_allowed"


@pytest.mark.parametrize(
    "value",
    ["https://opencode.ai/zen/go", "https://opencode.ai/zen/go/v1", "https://opencode.ai/zen/go/"],
)
def test_both_url_forms_normalize_to_same_base(value: str) -> None:
    decision = _resolve(value)

    assert decision.active is True
    assert decision.base_url == UPSTREAM
    assert decision.host == "opencode.ai"
    assert override_metrics_snapshot() == {"accepted": 1}


def test_chatgpt_auth_wins_and_refuses_override() -> None:
    decision = _resolve("https://opencode.ai/zen/go", is_chatgpt_auth=True)

    assert decision.status == "ignored"
    assert decision.reason == "chatgpt_subscription_auth"
    assert decision.active is False
    assert decision.rejected is False
    assert override_metrics_snapshot() == {"denied_chatgpt_subscription_auth": 1}


def test_chatgpt_account_header_wins_even_without_flag() -> None:
    decision = _resolve(
        "https://opencode.ai/zen/go",
        is_chatgpt_auth=False,
        extra_headers={"chatgpt-account-id": "acct_123"},
    )

    assert decision.reason == "chatgpt_subscription_auth"
    assert decision.active is False


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("http://opencode.ai/zen/go", "scheme_not_https"),
        ("ftp://opencode.ai/zen/go", "scheme_not_https"),
        ("https://user:pw@opencode.ai/zen/go", "userinfo_not_allowed"),
        ("https://opencode.ai/zen/go?x=1", "query_not_allowed"),
        ("https://opencode.ai/zen/go#frag", "fragment_not_allowed"),
        ("https://evil.example/zen/go", "host_not_allowed"),
        ("https://169.254.169.254/zen/go", "non_global_address"),
        ("https://127.0.0.1/zen/go", "non_global_address"),
        ("https://10.0.0.5/zen/go", "non_global_address"),
        ("https://opencode.ai/other", "path_not_allowed"),
        ("https://opencode.ai/zen/goodies", "path_not_allowed"),
        ("https://opencode.ai/zen/go/../admin", "path_not_allowed"),
        ("https://opencode.ai/zen/go\nx", "malformed_url"),
        ("not-a-url", "scheme_not_https"),
    ],
)
def test_bad_overrides_are_rejected_with_distinct_reasons(value: str, reason: str) -> None:
    decision = _resolve(value)

    assert decision.rejected is True
    assert decision.reason == reason
    assert decision.base_url is None
    assert override_metrics_snapshot() == {f"denied_{reason}": 1}


def test_non_loopback_peer_is_rejected() -> None:
    decision = _resolve("https://opencode.ai/zen/go", client_host="203.0.113.7")

    assert decision.rejected is True
    assert decision.reason == "untrusted_connection"


def test_non_loopback_bind_is_rejected() -> None:
    decision = _resolve("https://opencode.ai/zen/go", bind_host="0.0.0.0")

    assert decision.rejected is True
    assert decision.reason == "untrusted_connection"


def test_non_loopback_host_header_is_rejected() -> None:
    decision = _resolve("https://opencode.ai/zen/go", host_header="attacker.example")

    assert decision.rejected is True
    assert decision.reason == "untrusted_connection"


def test_override_without_client_credential_is_rejected() -> None:
    decision = _resolve(UPSTREAM, client_authorization=None)

    assert decision.rejected is True
    assert decision.reason == "client_credential_required"
    assert decision.base_url is None
    assert override_metrics_snapshot() == {"denied_client_credential_required": 1}


def test_blank_client_credential_is_rejected() -> None:
    assert _resolve(UPSTREAM, client_authorization="   ").reason == "client_credential_required"


def test_missing_credential_refusal_is_a_401() -> None:
    from cutctx.proxy.openai_upstream import (
        override_rejection_payload,
        override_rejection_status_code,
    )

    decision = _resolve(UPSTREAM, client_authorization=None)

    assert override_rejection_status_code(decision) == 401
    assert override_rejection_payload(decision)["error"]["code"] == (
        "base_url_override_requires_credential"
    )
    assert override_rejection_status_code(_resolve("https://evil.example/zen/go")) == 400


def test_host_allowlist_is_env_extensible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(openai_upstream.ALLOWED_HOSTS_ENV, "zen.example.test")
    monkeypatch.setenv(openai_upstream.ALLOWED_PATH_PREFIXES_ENV, "/gw")

    decision = _resolve("https://zen.example.test/gw/v1")

    assert decision.active is True
    assert decision.base_url == "https://zen.example.test/gw"
    # The default entry still applies alongside the operator extension.
    assert _resolve("https://opencode.ai/zen/go").active is True


def test_egress_policy_denial_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    from cutctx.proxy.egress import EgressDecision

    monkeypatch.setattr(
        openai_upstream,
        "get_egress_enforcer",
        lambda: SimpleNamespace(
            check=lambda url: EgressDecision(allowed=False, reason="no_pattern_match")
        ),
    )

    decision = _resolve("https://opencode.ai/zen/go")

    assert decision.rejected is True
    assert decision.reason == "egress_no_pattern_match"


# ---------------------------------------------------------------------------
# Handler integration
# ---------------------------------------------------------------------------


class _CapturingClient:
    """Records outbound URLs without performing network I/O."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.headers: list[dict[str, str]] = []

    def _record(self, method: str, url: str, kwargs: dict[str, Any]) -> httpx.Response:
        self.calls.append((method, url))
        self.headers.append({k.lower(): v for k, v in (kwargs.get("headers") or {}).items()})
        return httpx.Response(200, json={"data": []})

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return self._record(method, url, kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._record("GET", url, kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._record("POST", url, kwargs)

    async def aclose(self) -> None:
        return None


_CHAT_RESPONSE = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 0,
    "model": "gpt-5.4",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "ok"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
}

_RESPONSES_RESPONSE = {
    "id": "resp_1",
    "object": "response",
    "model": "gpt-5.4",
    "status": "completed",
    "output": [
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "ok"}],
        }
    ],
    "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
}


@contextlib.contextmanager
def _proxy_client(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any] | None = None,
    *,
    upstream_headers: list[dict[str, str]] | None = None,
):
    """TestClient bound to a loopback origin with upstream calls captured."""
    urls: list[str] = []

    async def fake_retry_request(self, method, url, headers, body, *args, **kwargs):  # type: ignore[no-untyped-def]
        urls.append(url)
        if upstream_headers is not None:
            upstream_headers.append({k.lower(): v for k, v in (headers or {}).items()})
        return httpx.Response(200, json=payload or _CHAT_RESPONSE)

    monkeypatch.setattr(CutctxProxy, "_retry_request", fake_retry_request)

    app = create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            openai_api_url="https://api.openai.test",
        )
    )
    with TestClient(app, base_url=LOOPBACK_BASE_URL) as client:
        capturing = _CapturingClient()
        client.app.state.proxy.http_client = capturing
        yield client, urls, capturing


def _chat_body() -> dict[str, Any]:
    return {
        "model": "gpt-5.4",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
    }


def _responses_body() -> dict[str, Any]:
    return {"model": "gpt-5.4", "input": "hello", "stream": False}


def test_chat_without_header_uses_process_wide_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    with _proxy_client(monkeypatch) as (client, urls, _):
        response = client.post("/v1/chat/completions", json=_chat_body())

    assert response.status_code == 200
    assert urls == ["https://api.openai.test/v1/chat/completions"]


@pytest.mark.parametrize("header", ["https://opencode.ai/zen/go", "https://opencode.ai/zen/go/v1"])
def test_chat_with_valid_override_routes_to_zen_go(
    monkeypatch: pytest.MonkeyPatch, header: str
) -> None:
    with _proxy_client(monkeypatch) as (client, urls, _):
        response = client.post(
            "/v1/chat/completions",
            json=_chat_body(),
            headers={OVERRIDE_HEADER: header, **CLIENT_AUTH},
        )

    assert response.status_code == 200
    assert urls == ["https://opencode.ai/zen/go/v1/chat/completions"]


@pytest.mark.parametrize("header", [DEEPSEEK_UPSTREAM, DEEPSEEK_UPSTREAM_V1])
def test_chat_routes_deepseek_v4_flash_through_official_upstream(
    monkeypatch: pytest.MonkeyPatch, header: str
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", OPERATOR_KEY)
    calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    async def fake_retry_request(self, method, url, headers, body, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((url, {k.lower(): v for k, v in headers.items()}, body))
        return httpx.Response(200, json=_CHAT_RESPONSE)

    monkeypatch.setattr(CutctxProxy, "_retry_request", fake_retry_request)
    app = create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            openai_api_url="https://api.openai.test",
        )
    )
    body = {**_chat_body(), "model": "deepseek-v4-flash"}

    with TestClient(app, base_url=LOOPBACK_BASE_URL) as client:
        client.app.state.proxy.http_client = _CapturingClient()
        response = client.post(
            "/v1/chat/completions",
            json=body,
            headers={OVERRIDE_HEADER: header, **CLIENT_AUTH},
        )

    assert response.status_code == 200
    assert len(calls) == 1
    upstream_url, upstream_headers, upstream_body = calls[0]
    assert upstream_url == "https://api.deepseek.com/v1/chat/completions"
    assert upstream_body["model"] == "deepseek-v4-flash"
    assert upstream_body["messages"] == body["messages"]
    assert upstream_headers["authorization"] == CLIENT_AUTH["authorization"]
    assert OPERATOR_KEY not in " ".join(upstream_headers.values())


@pytest.mark.parametrize("header", [DEEPSEEK_UPSTREAM, DEEPSEEK_UPSTREAM_V1])
def test_deepseek_override_is_refused_for_chatgpt_authenticated_request(header: str) -> None:
    decision = _resolve(
        header,
        extra_headers={"chatgpt-account-id": "acct_deepseek_characterization"},
    )

    assert decision.status == "ignored"
    assert decision.reason == "chatgpt_subscription_auth"
    assert decision.active is False
    assert decision.base_url is None


def test_chat_with_bad_override_returns_400_and_no_upstream_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _proxy_client(monkeypatch) as (client, urls, _):
        response = client.post(
            "/v1/chat/completions",
            json=_chat_body(),
            headers={OVERRIDE_HEADER: "http://evil.example/zen/go", **CLIENT_AUTH},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "base_url_override_rejected"
    assert urls == []
    assert override_metrics_snapshot().get("denied_scheme_not_https") == 1


def test_chat_override_does_not_mutate_class_attribute(monkeypatch: pytest.MonkeyPatch) -> None:
    original = CutctxProxy.OPENAI_API_URL
    with _proxy_client(monkeypatch) as (client, urls, _):
        proxy = client.app.state.proxy
        client.post(
            "/v1/chat/completions",
            json=_chat_body(),
            headers={OVERRIDE_HEADER: UPSTREAM, **CLIENT_AUTH},
        )
        assert proxy.OPENAI_API_URL == "https://api.openai.test"
        assert "OPENAI_API_URL" not in proxy.__dict__
        client.post("/v1/chat/completions", json=_chat_body())

    assert CutctxProxy.OPENAI_API_URL == original
    assert urls == [
        "https://opencode.ai/zen/go/v1/chat/completions",
        "https://api.openai.test/v1/chat/completions",
    ]


def test_interleaved_concurrent_requests_stay_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    with _proxy_client(monkeypatch) as (client, urls, _):
        proxy = client.app.state.proxy

        async def drive() -> None:
            from starlette.requests import Request

            async def one(with_header: bool) -> None:
                headers = [
                    (b"host", b"127.0.0.1:8787"),
                    (b"content-type", b"application/json"),
                    (b"authorization", CLIENT_AUTH["authorization"].encode()),
                ]
                if with_header:
                    headers.append((OVERRIDE_HEADER.encode(), UPSTREAM.encode()))
                body = __import__("json").dumps(_chat_body()).encode()
                scope = {
                    "type": "http",
                    "method": "POST",
                    "path": "/v1/chat/completions",
                    "raw_path": b"/v1/chat/completions",
                    "query_string": b"",
                    "headers": headers,
                    "client": ("127.0.0.1", 51234),
                    "server": ("127.0.0.1", 8787),
                    "scheme": "http",
                    "http_version": "1.1",
                    "app": client.app,
                    "root_path": "",
                }
                sent = False

                async def receive() -> dict[str, Any]:
                    nonlocal sent
                    if sent:
                        return {"type": "http.disconnect"}
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}

                await proxy.handle_openai_chat(Request(scope, receive))

            await asyncio.gather(*[one(i % 2 == 0) for i in range(8)])

        asyncio.run(drive())

    override_calls = [u for u in urls if u.startswith("https://opencode.ai/")]
    default_calls = [u for u in urls if u.startswith("https://api.openai.test/")]
    assert len(override_calls) == 4
    assert len(default_calls) == 4


def test_responses_http_honors_override(monkeypatch: pytest.MonkeyPatch) -> None:
    with _proxy_client(monkeypatch, payload=_RESPONSES_RESPONSE) as (client, urls, _):
        response = client.post(
            "/v1/responses",
            json=_responses_body(),
            headers={OVERRIDE_HEADER: "https://opencode.ai/zen/go/v1", **CLIENT_AUTH},
        )

    assert response.status_code == 200
    assert urls == ["https://opencode.ai/zen/go/v1/responses"]


def test_responses_http_without_override_uses_process_wide_upstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _proxy_client(monkeypatch, payload=_RESPONSES_RESPONSE) as (client, urls, _):
        response = client.post("/v1/responses", json=_responses_body())

    assert response.status_code == 200
    assert urls == ["https://api.openai.test/v1/responses"]


def test_responses_http_rejects_bad_override(monkeypatch: pytest.MonkeyPatch) -> None:
    with _proxy_client(monkeypatch, payload=_RESPONSES_RESPONSE) as (client, urls, _):
        response = client.post(
            "/v1/responses",
            json=_responses_body(),
            headers={OVERRIDE_HEADER: "https://evil.example/zen/go", **CLIENT_AUTH},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "base_url_override_rejected"
    assert urls == []


def test_models_honors_override(monkeypatch: pytest.MonkeyPatch) -> None:
    with _proxy_client(monkeypatch) as (client, _, capturing):
        response = client.get("/v1/models", headers={OVERRIDE_HEADER: UPSTREAM, **CLIENT_AUTH})

    assert response.status_code == 200
    assert capturing.calls == [("GET", "https://opencode.ai/zen/go/v1/models")]


def test_models_without_override_uses_process_wide_upstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _proxy_client(monkeypatch) as (client, _, capturing):
        response = client.get("/v1/models")

    assert response.status_code == 200
    assert capturing.calls == [("GET", "https://api.openai.test/v1/models")]


def test_models_rejects_bad_override(monkeypatch: pytest.MonkeyPatch) -> None:
    with _proxy_client(monkeypatch) as (client, _, capturing):
        response = client.get(
            "/v1/models",
            headers={OVERRIDE_HEADER: "https://evil.example/zen", **CLIENT_AUTH},
        )

    assert response.status_code == 400
    assert capturing.calls == []


def test_batch_and_embeddings_ignore_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Out of scope for Phase 1: the header must not change these routes."""
    with _proxy_client(monkeypatch) as (client, _, capturing):
        client.post(
            "/v1/embeddings",
            json={"input": "x"},
            headers={OVERRIDE_HEADER: UPSTREAM, **CLIENT_AUTH},
        )

    assert capturing.calls
    assert all("opencode.ai" not in url for _, url in capturing.calls)


def test_override_disables_implicit_model_downgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    from cutctx.proxy import model_router

    real_prepare = model_router.prepare_model_routing

    def spy(proxy, model, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)
        return real_prepare(proxy, model, **kwargs)

    monkeypatch.setattr(model_router, "prepare_model_routing", spy)

    with _proxy_client(monkeypatch) as (client, urls, _):
        client.post(
            "/v1/chat/completions",
            json=_chat_body(),
            headers={OVERRIDE_HEADER: UPSTREAM, **CLIENT_AUTH},
        )

    assert captured
    assert captured[0]["implicit_downgrade_allowed"] is False
    assert captured[0]["allow_transport_safe_targets"] is False
    assert urls == ["https://opencode.ai/zen/go/v1/chat/completions"]


def test_translated_backend_refuses_override(monkeypatch: pytest.MonkeyPatch) -> None:
    with _proxy_client(monkeypatch) as (client, urls, _):
        client.app.state.proxy.anthropic_backend = SimpleNamespace(name="litellm-openai")
        response = client.post(
            "/v1/chat/completions",
            json=_chat_body(),
            headers={OVERRIDE_HEADER: UPSTREAM, **CLIENT_AUTH},
        )

    assert response.status_code == 400
    assert "translated_backend_active" in response.json()["error"]["message"]
    assert override_metrics_snapshot().get("denied_translated_backend_active") == 1
    assert urls == []


# ---------------------------------------------------------------------------
# Must-fix 1: the operator credential never reaches a client-named upstream
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/v1/responses"])
def test_headerless_request_with_override_is_refused_without_operator_key(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", OPERATOR_KEY)
    sent: list[dict[str, str]] = []
    body = _chat_body() if path.endswith("completions") else _responses_body()

    with _proxy_client(monkeypatch, upstream_headers=sent) as (client, urls, _):
        response = client.post(path, json=body, headers={OVERRIDE_HEADER: UPSTREAM})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "base_url_override_requires_credential"
    assert urls == []
    assert sent == []


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/v1/responses"])
def test_override_forwards_client_credential_not_the_operator_key(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", OPERATOR_KEY)
    sent: list[dict[str, str]] = []
    body = _chat_body() if path.endswith("completions") else _responses_body()

    with _proxy_client(monkeypatch, upstream_headers=sent) as (client, urls, _):
        response = client.post(path, json=body, headers={OVERRIDE_HEADER: UPSTREAM, **CLIENT_AUTH})

    assert response.status_code == 200
    assert all(url.startswith("https://opencode.ai/") for url in urls)
    assert sent
    assert sent[0]["authorization"] == CLIENT_AUTH["authorization"]
    assert OPERATOR_KEY not in " ".join(sent[0].values())


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/v1/responses"])
def test_headerless_request_without_override_still_gets_injection(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", OPERATOR_KEY)
    sent: list[dict[str, str]] = []
    body = _chat_body() if path.endswith("completions") else _responses_body()

    with _proxy_client(monkeypatch, upstream_headers=sent) as (client, urls, _):
        response = client.post(path, json=body)

    assert response.status_code == 200
    assert all(url.startswith("https://api.openai.test/") for url in urls)
    assert sent
    assert sent[0]["authorization"] == f"Bearer {OPERATOR_KEY}"


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/v1/responses"])
def test_injection_is_skipped_even_if_the_resolver_accepts_a_headerless_request(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """The handler guard, not just the resolver, keeps the operator key home.

    Forces an accepted decision for a request that carries no Authorization so
    the credential requirement cannot be what makes this pass.
    """
    monkeypatch.setenv("OPENAI_API_KEY", OPERATOR_KEY)
    monkeypatch.setattr(
        openai_upstream,
        "resolve_openai_base_url_override",
        lambda *_args, **_kwargs: openai_upstream.OpenAIBaseUrlDecision(
            status="accepted", reason="accepted", base_url=UPSTREAM, host="opencode.ai"
        ),
    )
    sent: list[dict[str, str]] = []
    body = _chat_body() if path.endswith("completions") else _responses_body()

    with _proxy_client(monkeypatch, upstream_headers=sent) as (client, urls, _):
        response = client.post(path, json=body, headers={OVERRIDE_HEADER: UPSTREAM})

    assert response.status_code == 200
    assert all(url.startswith("https://opencode.ai/") for url in urls)
    assert sent
    assert "authorization" not in sent[0]


def test_injection_cannot_flip_responses_routing_to_chatgpt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-injection ChatGPT detection must not override a raw-header verdict.

    The resolver runs on the raw headers; ``/v1/responses`` re-derives ChatGPT
    routing from the upstream-bound copy, which credential injection can alter.
    The stub makes the second (post-injection) derivation disagree with the
    first: an accepted override must still land on the named upstream.
    """
    from cutctx.proxy.handlers.openai import responses as responses_module

    derivations = {"count": 0}

    def flip_after_the_raw_pass(headers: dict[str, str]) -> tuple[dict[str, str], bool]:
        derivations["count"] += 1
        if derivations["count"] == 1:
            return dict(headers), False
        return {**headers, "ChatGPT-Account-ID": "acct_flip"}, True

    monkeypatch.setattr(responses_module, "_resolve_codex_routing_headers", flip_after_the_raw_pass)

    with _proxy_client(monkeypatch, payload=_RESPONSES_RESPONSE) as (client, urls, _):
        response = client.post(
            "/v1/responses",
            json=_responses_body(),
            headers={OVERRIDE_HEADER: UPSTREAM, **CLIENT_AUTH},
        )

    assert response.status_code == 200
    assert urls == ["https://opencode.ai/zen/go/v1/responses"]
    assert derivations["count"] >= 2


# ---------------------------------------------------------------------------
# Must-fix 2: /health advertises what the runtime can actually honour
# ---------------------------------------------------------------------------


def test_health_advertises_capability_on_loopback_bind() -> None:
    app = create_app(
        ProxyConfig(optimize=False, cache_enabled=False, rate_limit_enabled=False, host="127.0.0.1")
    )
    with TestClient(app, base_url=LOOPBACK_BASE_URL) as client:
        payload = client.get("/health").json()

    assert payload["capabilities"]["per_request_openai_base_url"] is True


def test_health_capability_tracks_the_runtime_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-loopback bind must flip the advertised flag, not just the gate.

    `create_app` refuses an unauthenticated non-loopback bind outright, so the
    flag is exercised by mutating the live proxy's bind host behind `/health`.
    """
    app = create_app(
        ProxyConfig(optimize=False, cache_enabled=False, rate_limit_enabled=False, host="127.0.0.1")
    )
    with TestClient(app, base_url=LOOPBACK_BASE_URL) as client:
        proxy = client.app.state.proxy
        monkeypatch.setattr(proxy.config, "host", "0.0.0.0")
        payload = client.get("/health").json()

    assert payload["capabilities"]["per_request_openai_base_url"] is False


@pytest.mark.parametrize("host", ["0.0.0.0", "203.0.113.7", "", None])
def test_capability_is_false_for_non_loopback_binds(host: str | None) -> None:
    from cutctx.proxy.openai_upstream import override_capability_enabled

    proxy = SimpleNamespace(config=SimpleNamespace(host=host), anthropic_backend=None)

    assert override_capability_enabled(proxy) is False


def test_capability_is_true_for_a_loopback_bind() -> None:
    from cutctx.proxy.openai_upstream import override_capability_enabled

    proxy = SimpleNamespace(config=SimpleNamespace(host="127.0.0.1"), anthropic_backend=None)

    assert override_capability_enabled(proxy) is True


def test_capability_is_false_when_a_translated_backend_is_active() -> None:
    from cutctx.proxy.openai_upstream import override_capability_enabled

    proxy = SimpleNamespace(
        config=SimpleNamespace(host="127.0.0.1"),
        anthropic_backend=SimpleNamespace(name="litellm-openai"),
    )

    assert override_capability_enabled(proxy) is False


# ---------------------------------------------------------------------------
# Must-fix 3: the catch-all passthrough vets its own x-cutctx-base-url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("https://169.254.169.254/latest/meta-data/", "non_global_address"),
        ("http://169.254.169.254/latest/meta-data/", "non_global_address"),
        ("https://[fd00::1]/v1", "non_global_address"),
        ("https://10.0.0.5/v1", "non_global_address"),
        ("file:///etc/passwd", "scheme_not_http"),
        ("gopher://azure.example/v1", "scheme_not_http"),
        ("https://user:pw@azure.example/v1", "userinfo_not_allowed"),
        ("https://azure.example/v1\nx", "malformed_url"),
    ],
)
def test_passthrough_rejects_unsafe_base_urls(value: str, reason: str) -> None:
    from cutctx.proxy.openai_upstream import validate_passthrough_base_url

    base_url, rejection = validate_passthrough_base_url(_connection_stub(), value)

    assert base_url is None
    assert rejection == reason


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://azure.example/openai/", "https://azure.example/openai"),
        ("https://my-tenant.openai.azure.com/", "https://my-tenant.openai.azure.com"),
        ("https://93.184.216.34/v1", "https://93.184.216.34/v1"),
        ("http://custom.example/base", "http://custom.example/base"),
    ],
)
def test_passthrough_accepts_globally_routable_bases(value: str, expected: str) -> None:
    from cutctx.proxy.openai_upstream import validate_passthrough_base_url

    base_url, rejection = validate_passthrough_base_url(_connection_stub(), value)

    assert rejection is None
    assert base_url == expected


def test_passthrough_rejects_non_loopback_peer() -> None:
    from cutctx.proxy.openai_upstream import validate_passthrough_base_url

    base_url, rejection = validate_passthrough_base_url(
        _connection_stub("203.0.113.7"), "https://azure.example/v1"
    )

    assert base_url is None
    assert rejection == "untrusted_connection"


def test_passthrough_route_denies_metadata_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    with _proxy_client(monkeypatch) as (client, _, capturing):
        response = client.get(
            "/latest/meta-data/iam/security-credentials/",
            headers={OVERRIDE_HEADER: "https://169.254.169.254"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "base_url_passthrough_rejected"
    assert capturing.calls == []


def test_passthrough_route_still_accepts_an_azure_shaped_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _proxy_client(monkeypatch) as (client, _, capturing):
        response = client.get(
            "/azure/models",
            headers={
                "api-key": "azure-key",
                OVERRIDE_HEADER: "https://my-tenant.openai.azure.com/openai/",
            },
        )

    assert response.status_code == 200
    assert capturing.calls == [("GET", "https://my-tenant.openai.azure.com/openai/azure/models")]


# ---------------------------------------------------------------------------
# D1 (Phase 4 must-fix): the response cache must key on resolved upstream
# ---------------------------------------------------------------------------


def test_response_cache_does_not_leak_override_upstream_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response fetched via the override upstream must never be served to
    a later identical-body request that did NOT send the override header.

    Regression for D1, found live during the Phase 4 cutover: the semantic
    response cache keyed on ``(messages, model)`` only, so an override
    (zen/go) response could be served byte-identical to a later request with
    the same body that did not send ``x-cutctx-base-url`` and should have
    hit the process-wide OpenAI upstream instead.
    """
    urls: list[str] = []

    async def fake_retry_request(self, method, url, headers, body, *args, **kwargs):  # type: ignore[no-untyped-def]
        urls.append(url)
        if url.startswith("https://opencode.ai/"):
            payload = {**_CHAT_RESPONSE, "id": "chatcmpl-zen-go"}
        else:
            payload = {**_CHAT_RESPONSE, "id": "chatcmpl-openai-direct"}
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(CutctxProxy, "_retry_request", fake_retry_request)

    app = create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=True,
            rate_limit_enabled=False,
            openai_api_url="https://api.openai.test",
        )
    )
    with TestClient(app, base_url=LOOPBACK_BASE_URL) as client:
        client.app.state.proxy.http_client = _CapturingClient()

        # 1. Populate the response cache via the override upstream (zen/go).
        overridden = client.post(
            "/v1/chat/completions",
            json=_chat_body(),
            headers={OVERRIDE_HEADER: UPSTREAM, **CLIENT_AUTH},
        )
        assert overridden.status_code == 200
        assert overridden.json()["id"] == "chatcmpl-zen-go"

        # 2. Same messages + model, no override header: must MISS the
        # override's cache entry and hit the process-wide upstream instead
        # of being served the cached zen/go response.
        plain = client.post("/v1/chat/completions", json=_chat_body())

    assert plain.status_code == 200
    assert plain.json()["id"] == "chatcmpl-openai-direct"
    assert plain.headers.get("x-cutctx-response-cache") != "hit"
    # Both requests must have reached an upstream: the second is a genuine
    # cache miss, not a hit served from the override's cached entry.
    assert urls == [
        "https://opencode.ai/zen/go/v1/chat/completions",
        "https://api.openai.test/v1/chat/completions",
    ]


def test_response_cache_and_credentials_stay_isolated_between_deepseek_and_zen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Identical DeepSeek V4 Flash requests must not cross upstream boundaries."""
    monkeypatch.setenv("OPENAI_API_KEY", OPERATOR_KEY)
    calls: list[tuple[str, dict[str, str]]] = []

    async def fake_retry_request(self, method, url, headers, body, *args, **kwargs):  # type: ignore[no-untyped-def]
        normalized_headers = {key.lower(): value for key, value in headers.items()}
        calls.append((url, normalized_headers))
        response_id = "chatcmpl-deepseek" if "api.deepseek.com" in url else "chatcmpl-zen"
        return httpx.Response(200, json={**_CHAT_RESPONSE, "id": response_id})

    monkeypatch.setattr(CutctxProxy, "_retry_request", fake_retry_request)
    app = create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=True,
            rate_limit_enabled=False,
            openai_api_url="https://api.openai.test",
        )
    )
    body = {**_chat_body(), "model": "deepseek-v4-flash"}
    deepseek_auth = {"authorization": "Bearer deepseek-request-key"}
    zen_auth = {"authorization": "Bearer zen-request-key"}

    with TestClient(app, base_url=LOOPBACK_BASE_URL) as client:
        client.app.state.proxy.http_client = _CapturingClient()
        deepseek_response = client.post(
            "/v1/chat/completions",
            json=body,
            headers={OVERRIDE_HEADER: DEEPSEEK_UPSTREAM, **deepseek_auth},
        )
        zen_response = client.post(
            "/v1/chat/completions",
            json=body,
            headers={OVERRIDE_HEADER: UPSTREAM, **zen_auth},
        )

    assert deepseek_response.status_code == 200
    assert deepseek_response.json()["id"] == "chatcmpl-deepseek"
    assert zen_response.status_code == 200
    assert zen_response.json()["id"] == "chatcmpl-zen"
    assert zen_response.headers.get("x-cutctx-response-cache") != "hit"
    assert [url for url, _ in calls] == [
        "https://api.deepseek.com/v1/chat/completions",
        "https://opencode.ai/zen/go/v1/chat/completions",
    ]
    assert [headers["authorization"] for _, headers in calls] == [
        deepseek_auth["authorization"],
        zen_auth["authorization"],
    ]
    assert all(OPERATOR_KEY not in " ".join(headers.values()) for _, headers in calls)


def test_response_cache_still_hits_for_repeated_override_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity check: the cache still works within the same resolved upstream.

    D1's fix folds the upstream into the cache key; it must not turn the
    cache into a permanent no-op for repeated requests through the same
    override.
    """
    urls: list[str] = []

    async def fake_retry_request(self, method, url, headers, body, *args, **kwargs):  # type: ignore[no-untyped-def]
        urls.append(url)
        return httpx.Response(200, json={**_CHAT_RESPONSE, "id": "chatcmpl-zen-go"})

    monkeypatch.setattr(CutctxProxy, "_retry_request", fake_retry_request)

    app = create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=True,
            rate_limit_enabled=False,
            openai_api_url="https://api.openai.test",
        )
    )
    with TestClient(app, base_url=LOOPBACK_BASE_URL) as client:
        client.app.state.proxy.http_client = _CapturingClient()

        first = client.post(
            "/v1/chat/completions",
            json=_chat_body(),
            headers={OVERRIDE_HEADER: UPSTREAM, **CLIENT_AUTH},
        )
        second = client.post(
            "/v1/chat/completions",
            json=_chat_body(),
            headers={OVERRIDE_HEADER: UPSTREAM, **CLIENT_AUTH},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == "chatcmpl-zen-go"
    assert second.headers.get("x-cutctx-response-cache") == "hit"
    # Only the first request reached the upstream; the second was a cache hit.
    assert urls == ["https://opencode.ai/zen/go/v1/chat/completions"]

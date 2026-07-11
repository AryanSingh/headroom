from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from cutctx.orchestration.config import LayeredConfigStore
from cutctx.orchestration.credentials import EncryptedCredentialStore
from cutctx.orchestration.engine import DeterministicRoutingEngine, RoutingUnavailableError
from cutctx.orchestration.models import (
    Capability,
    ExecutionRecord,
    ModelRecord,
    OrchestrationConfig,
    ProviderAccount,
    Role,
    RouteBinding,
    RoutingMode,
    RoutingRequest,
    RoutingSettings,
)
from cutctx.orchestration.providers import (
    HTTPProviderAdapter,
    LiteLLMProviderAdapter,
    ProviderAdapterRegistry,
    ProviderHealth,
    ProviderSpec,
    builtin_provider_registry,
)
from cutctx.orchestration.registry import DynamicModelRegistry
from cutctx.orchestration.service import OrchestrationService, build_orchestration_service
from cutctx.orchestration.telemetry import ExecutionTelemetryStore
from cutctx.orchestration.workflow import TaskSpec, WorkflowSpec, WorkflowStateStore
from cutctx.proxy.model_router import prepare_model_routing
from cutctx.proxy.routes.orchestration import create_orchestration_router
from cutctx.proxy.savings_metadata import extract_savings_metadata


def _model(
    provider: str,
    model: str,
    *,
    account_id: str | None = None,
    capabilities: set[str] | None = None,
    available: bool = True,
) -> ModelRecord:
    return ModelRecord(
        provider=provider,
        id=model,
        account_id=account_id,
        capabilities=capabilities or {Capability.STREAMING.value, Capability.TOOL_CALLING.value},
        available=available,
    )


def _engine(config: OrchestrationConfig, *models: ModelRecord) -> DeterministicRoutingEngine:
    registry = DynamicModelRegistry()
    for model in models:
        registry.register(model)
    return DeterministicRoutingEngine(config, registry)


def test_given_role_assignment_when_routing_then_assigned_model_is_enforced() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="implementer", name="Implementer")],
        bindings=[
            RouteBinding(
                id="implementer-kimi",
                role="implementer",
                model="kimi:kimi-2.7",
                fallback_chain=["openai:gpt-5.4-mini"],
            )
        ],
        settings=RoutingSettings(mode=RoutingMode.STRICT.value),
    )
    engine = _engine(
        config,
        _model("kimi", "kimi-2.7"),
        _model("openai", "gpt-5.4-mini"),
    )

    decision = engine.route(RoutingRequest(role="Implementer"))

    assert decision.actual_model == "kimi-2.7"
    assert decision.provider == "kimi"
    assert decision.fallback_used is False
    assert decision.binding_id == "implementer-kimi"


def test_strict_mode_refuses_unavailable_assignment_without_using_fallback() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="implementer", name="Implementer")],
        bindings=[
            RouteBinding(
                id="locked",
                role="implementer",
                model="kimi:kimi-2.7",
                fallback_chain=["openai:gpt-5.4-mini"],
            )
        ],
        settings=RoutingSettings(mode="strict"),
    )
    engine = _engine(
        config,
        _model("kimi", "kimi-2.7", available=False),
        _model("openai", "gpt-5.4-mini"),
    )

    with pytest.raises(RoutingUnavailableError) as error:
        engine.route(RoutingRequest(role="implementer"))

    assert error.value.assigned_model == "kimi:kimi-2.7"
    assert error.value.reason == "unavailable"


def test_request_cannot_relax_configured_strict_mode() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="strict-worker",
                role="worker",
                model="openai:model-a",
                fallback_chain=["openai:model-b"],
            )
        ],
        settings=RoutingSettings(mode="strict", policy="role_locked"),
    )
    engine = _engine(
        config,
        _model("openai", "model-a", available=False),
        _model("openai", "model-b"),
    )

    with pytest.raises(RoutingUnavailableError):
        engine.route(RoutingRequest(role="worker", mode="relaxed", policy="balanced"))

    preview = engine.route(
        RoutingRequest(role="worker", mode="relaxed", policy="balanced"),
        allow_overrides=True,
    )
    assert preview.actual_model == "model-b"
    assert preview.mode == "relaxed"


def test_relaxed_mode_uses_explicit_fallback_and_explains_why() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="implementer", name="Implementer")],
        bindings=[
            RouteBinding(
                id="relaxed",
                role="implementer",
                model="kimi:kimi-2.7",
                fallback_chain=["openai:gpt-5.4-mini"],
            )
        ],
        settings=RoutingSettings(mode="relaxed"),
    )
    engine = _engine(
        config,
        _model("kimi", "kimi-2.7", available=False),
        _model("openai", "gpt-5.4-mini"),
    )

    decision = engine.route(RoutingRequest(role="implementer"))

    assert decision.assigned_model == "kimi:kimi-2.7"
    assert decision.actual_model == "gpt-5.4-mini"
    assert decision.fallback_used is True
    assert decision.fallback_trigger == "unavailable"


def test_fallback_chain_never_revisits_a_failed_deployment() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="worker-chain",
                role="worker",
                model="openai:model-a",
                fallback_chain=["openai:model-b", "openai:model-c"],
            )
        ],
        settings=RoutingSettings(mode="relaxed"),
    )
    engine = _engine(
        config,
        _model("openai", "model-a"),
        _model("openai", "model-b"),
        _model("openai", "model-c"),
    )

    first = engine.route(RoutingRequest(role="worker"))
    second = engine.fallback(first, "provider_outage")
    third = engine.fallback(second, "provider_outage")

    assert [
        first.actual_model,
        second.actual_model,
        third.actual_model,
    ] == ["model-a", "model-b", "model-c"]
    with pytest.raises(RoutingUnavailableError):
        engine.fallback(third, "provider_outage")


def test_same_model_on_multiple_accounts_requires_an_exact_deployment() -> None:
    registry = DynamicModelRegistry()
    registry.register(_model("openai", "shared-model"))
    registry.register(_model("openai", "shared-model", account_id="account-a"))
    registry.register(_model("openai", "shared-model", account_id="account-b"))
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="worker-account-a",
                role="worker",
                model="openai:account-a:shared-model",
            )
        ],
    )

    assert registry.get("openai:shared-model") is None
    assert len([model for model in registry.list() if model.id == "shared-model"]) == 2
    decision = DeterministicRoutingEngine(config, registry).route(RoutingRequest(role="worker"))
    assert decision.account_id == "account-a"
    assert decision.actual_model == "shared-model"
    assert decision.fallback_used is False
    assert decision.fallback_trigger is None


def test_agent_binding_deterministically_overrides_role_binding() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(id="role-default", role="worker", model="openai:gpt-5.4-mini"),
            RouteBinding(
                id="frontend-agent",
                role="worker",
                selectors={"agent": "frontend"},
                model="google:gemini-2.5-pro",
            ),
        ],
    )
    engine = _engine(
        config,
        _model("openai", "gpt-5.4-mini"),
        _model("google", "gemini-2.5-pro"),
    )

    decision = engine.route(RoutingRequest(role="worker", selectors={"agent": "frontend"}))

    assert decision.binding_id == "frontend-agent"
    assert decision.provider == "google"


def test_capability_check_never_infers_support_from_model_name() -> None:
    config = OrchestrationConfig(
        roles=[
            Role(
                id="visual",
                name="Visual Auditor",
                required_capabilities={Capability.VISION.value},
            )
        ],
        bindings=[RouteBinding(id="visual-model", role="visual", model="custom:looks-visual")],
    )
    engine = _engine(
        config,
        _model(
            "custom",
            "looks-visual",
            capabilities={Capability.STREAMING.value},
        ),
    )

    with pytest.raises(RoutingUnavailableError) as error:
        engine.route(RoutingRequest(role="visual"))

    assert error.value.reason == "unsupported_capabilities"


def test_layered_config_merges_entities_by_id_and_round_trips(tmp_path: Path) -> None:
    global_path = tmp_path / "global.json"
    project_path = tmp_path / "project.json"
    global_path.write_text(
        '{"version":1,"roles":[{"id":"worker","name":"Worker"}],"settings":{"mode":"strict"}}',
        encoding="utf-8",
    )
    project_path.write_text(
        '{"version":1,"roles":[{"id":"worker","name":"Fast Worker"}],'
        '"settings":{"policy":"cheapest"}}',
        encoding="utf-8",
    )
    store = LayeredConfigStore({"global": global_path, "project": project_path})

    config = store.load()

    assert config.roles[0].name == "Fast Worker"
    assert config.settings.mode == "strict"
    assert config.settings.policy == "cheapest"
    store.save(config)
    assert store.load() == config


def test_layered_config_keeps_same_model_from_multiple_accounts(tmp_path: Path) -> None:
    global_path = tmp_path / "global.json"
    project_path = tmp_path / "project.json"
    global_path.write_text(
        '{"version":1,"models":[{"provider":"openai","account_id":"a","id":"shared"}]}',
        encoding="utf-8",
    )
    project_path.write_text(
        '{"version":1,"models":[{"provider":"openai","account_id":"b","id":"shared"}]}',
        encoding="utf-8",
    )

    config = LayeredConfigStore({"global": global_path, "project": project_path}).load()

    assert {model.deployment_key for model in config.models} == {
        "openai:a:shared",
        "openai:b:shared",
    }


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (RoutingSettings(mode="unsafe"), "Unknown orchestration mode"),
        (RoutingSettings(policy="random"), "Unknown routing policy"),
        (RoutingSettings(retries=11), "retries"),
        (RoutingSettings(timeout_seconds=float("inf")), "timeout_seconds"),
        (RoutingSettings(fallback_triggers={"invented"}), "fallback triggers"),
    ],
)
def test_invalid_routing_settings_are_rejected(
    tmp_path: Path,
    settings: RoutingSettings,
    message: str,
) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    invalid = OrchestrationConfig(
        providers=service.config.providers,
        roles=service.config.roles,
        bindings=service.config.bindings,
        settings=settings,
    )

    with pytest.raises(ValueError, match=message):
        service.replace_config(invalid)


def test_sensitive_custom_headers_must_use_encrypted_credentials(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    service.config.providers[0].custom_headers = {"authorization": "Bearer plaintext"}

    with pytest.raises(ValueError, match="encrypted credential payload"):
        service.replace_config(service.config)


def test_replace_config_validates_effective_layers_before_persisting(tmp_path: Path) -> None:
    global_path = tmp_path / "global.json"
    project_path = tmp_path / "project.json"
    global_path.write_text(
        '{"version":1,"providers":[{"id":"main","provider":"openai"}]}',
        encoding="utf-8",
    )
    service = OrchestrationService(
        config_store=LayeredConfigStore({"global": global_path, "project": project_path}),
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=DynamicModelRegistry(),
        provider_registry=builtin_provider_registry(),
        telemetry=ExecutionTelemetryStore(),
    )
    global_path.write_text(
        '{"version":1,"providers":[{"id":"bad","provider":"unknown"}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown provider"):
        service.replace_config(OrchestrationConfig())
    assert not project_path.exists()


def test_replace_config_prunes_models_removed_from_configuration(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    configured = _model("openai", "temporary", account_id="openai-main")
    first = copy.deepcopy(service.config)
    first.models = [configured]
    service.replace_config(first)
    assert service.model_registry.get(configured.deployment_key) is not None

    second = copy.deepcopy(first)
    second.models = []
    service.replace_config(second)

    assert service.model_registry.get(configured.deployment_key) is None


def test_credentials_are_encrypted_and_support_multiple_accounts(tmp_path: Path) -> None:
    store = EncryptedCredentialStore(tmp_path / "credentials.enc")

    store.put("provider:one", {"api_key": "secret-one"})
    store.put("provider:two", {"api_key": "secret-two", "headers": {"x-org": "acme"}})

    encrypted = (tmp_path / "credentials.enc").read_bytes()
    assert b"secret-one" not in encrypted
    assert b"secret-two" not in encrypted
    assert store.references() == ["provider:one", "provider:two"]
    assert store.get("provider:two") == {
        "api_key": "secret-two",
        "headers": {"x-org": "acme"},
    }
    assert oct((tmp_path / "credentials.key").stat().st_mode & 0o777) == "0o600"


def test_credential_write_preserves_layered_config_boundaries(tmp_path: Path) -> None:
    global_path = tmp_path / "global.json"
    project_path = tmp_path / "project.json"
    global_path.write_text(
        json.dumps(
            {
                "version": 1,
                "providers": [
                    {"id": "shared-openai", "provider": "openai", "display_name": "Shared"}
                ],
                "settings": {"mode": "strict"},
            }
        ),
        encoding="utf-8",
    )
    service = OrchestrationService(
        config_store=LayeredConfigStore({"global": global_path, "project": project_path}),
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=DynamicModelRegistry(),
        provider_registry=builtin_provider_registry(),
        telemetry=ExecutionTelemetryStore(),
    )

    assert service.put_credential(
        "shared-openai", {"api_key": "test-secret"}, layer="project"
    ) == (
        "provider:shared-openai"
    )

    assert json.loads(project_path.read_text(encoding="utf-8")) == {
        "version": 1,
        "providers": [{"id": "shared-openai", "credential_ref": "provider:shared-openai"}],
    }
    assert service.config.providers[0].provider == "openai"
    assert service.config.providers[0].credential_ref == "provider:shared-openai"
    assert service.config.settings.mode == "strict"


def test_provider_accounts_and_credentials_persist_across_restarts(tmp_path: Path, monkeypatch) -> None:
    state_dir = tmp_path / "state"
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    workspace_a.mkdir()
    workspace_b.mkdir()

    monkeypatch.chdir(workspace_a)
    service = build_orchestration_service(data_dir=state_dir)
    account_id = "openai-main"

    stored_account = service.put_account(
        account_id,
        {
            "provider": "openai",
            "display_name": "Primary OpenAI",
            "base_url": "https://api.openai.com/v1",
        },
    )
    reference = service.put_credential(account_id, {"api_key": "persist-me"})

    assert stored_account["id"] == account_id
    assert reference == "provider:openai-main"
    assert json.loads((state_dir / "user.json").read_text(encoding="utf-8"))["providers"][0][
        "credential_ref"
    ] == reference
    assert not (workspace_a / ".cutctx" / "orchestration.json").exists()

    monkeypatch.chdir(workspace_b)
    restarted = build_orchestration_service(data_dir=state_dir)

    assert restarted.accounts() == [
        {
            "id": account_id,
            "provider": "openai",
            "display_name": "Primary OpenAI",
            "auth_method": "api_key",
            "credential_ref": reference,
            "base_url": "https://api.openai.com/v1",
            "organization_id": None,
            "workspace_id": None,
            "custom_headers": {},
            "enabled": True,
            "metadata": {},
            "credential_configured": True,
        }
    ]


@pytest.mark.asyncio
async def test_provider_adapter_validates_credentials_discovers_models_and_invokes() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "dynamic-model",
                            "capabilities": ["vision", "tool_calling", "streaming"],
                            "context_length": 200000,
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    transport = httpx.MockTransport(respond)
    adapter = HTTPProviderAdapter(
        ProviderSpec(
            "custom-provider",
            "Custom Provider",
            default_base_url="https://provider.test",
        ),
        ProviderAccount(id="custom-main", provider="custom-provider"),
        {"api_key": "valid-key"},
        client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
    )

    health = await adapter.authenticate()
    models = await adapter.refresh_models()
    response = await adapter.invoke(
        {"model": "dynamic-model", "messages": [{"role": "user", "content": "hi"}]}
    )

    assert health.ok is True
    assert models[0].key == "custom-provider:dynamic-model"
    assert models[0].supports({"vision", "tool_calling"})
    assert response["choices"][0]["message"]["content"] == "ok"
    assert all(request.headers["authorization"] == "Bearer valid-key" for request in requests)


@pytest.mark.asyncio
async def test_provider_adapter_reports_invalid_credentials_without_leaking_key() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(401, text="invalid credential"))
    adapter = HTTPProviderAdapter(
        ProviderSpec("custom-provider", "Custom", default_base_url="https://provider.test"),
        ProviderAccount(id="custom-main", provider="custom-provider"),
        {"api_key": "do-not-leak"},
        client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
    )

    health = await adapter.authenticate()

    assert health.ok is False
    assert health.status == "authentication_failed"
    assert "do-not-leak" not in (health.detail or "")


@pytest.mark.asyncio
async def test_openai_compatible_api_base_does_not_duplicate_version_prefix() -> None:
    seen_urls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json={"data": []})

    adapter = HTTPProviderAdapter(
        ProviderSpec("external-gateway", "External Gateway"),
        ProviderAccount(
            id="gateway-main",
            provider="external-gateway",
            base_url="http://gateway.internal:8080/v1",
        ),
        None,
        client_factory=lambda **kwargs: httpx.AsyncClient(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    )

    await adapter.refresh_models()

    assert seen_urls == ["http://gateway.internal:8080/v1/models"]


class _DumpableResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return self.payload


@pytest.mark.asyncio
async def test_litellm_adapter_normalizes_provider_and_protects_account_auth() -> None:
    calls: list[dict[str, Any]] = []

    async def completion(**kwargs: Any) -> _DumpableResponse:
        calls.append(kwargs)
        return _DumpableResponse(
            {
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            }
        )

    adapter = LiteLLMProviderAdapter(
        ProviderSpec(
            "openrouter",
            "OpenRouter",
            default_base_url="https://openrouter.ai/api",
            litellm_provider="openrouter",
        ),
        ProviderAccount(
            id="openrouter-main",
            provider="openrouter",
            base_url="https://gateway.example/v1",
            organization_id="org-1",
            custom_headers={"x-workspace": "acme"},
        ),
        {"api_key": "stored-key", "headers": {"x-account": "primary"}},
        completion_fn=completion,
    )

    response = await adapter.invoke(
        {
            "model": "anthropic/claude-sonnet-4",
            "messages": [{"role": "user", "content": "hello"}],
            "api_key": "request-must-not-override-storage",
            "base_url": "https://attacker.invalid",
        }
    )

    assert response["choices"][0]["message"]["content"] == "ok"
    assert calls == [
        {
            "messages": [{"role": "user", "content": "hello"}],
            "model": "openrouter/anthropic/claude-sonnet-4",
            "stream": False,
            "num_retries": 0,
            "fallbacks": [],
            "api_key": "stored-key",
            "base_url": "https://gateway.example/v1",
            "organization": "org-1",
            "extra_headers": {"x-workspace": "acme", "x-account": "primary"},
        }
    ]


@pytest.mark.asyncio
async def test_litellm_adapter_rejects_hidden_runtime_controls() -> None:
    async def completion(**kwargs: Any) -> _DumpableResponse:
        raise AssertionError("Completion must not be called for invalid parameters")

    adapter = LiteLLMProviderAdapter(
        ProviderSpec("custom", "Custom", litellm_provider="openai"),
        ProviderAccount(id="custom-main", provider="custom"),
        {"api_key": "stored-key"},
        completion_fn=completion,
    )

    with pytest.raises(ValueError, match="mock_response"):
        await adapter.invoke(
            {
                "model": "model-a",
                "messages": [{"role": "user", "content": "hello"}],
                "mock_response": "spoofed",
            }
        )


@pytest.mark.asyncio
async def test_litellm_adapter_uses_only_stored_cloud_runtime_fields() -> None:
    calls: list[dict[str, Any]] = []

    async def completion(**kwargs: Any) -> _DumpableResponse:
        calls.append(kwargs)
        return _DumpableResponse({"choices": []})

    adapter = LiteLLMProviderAdapter(
        ProviderSpec("bedrock", "Bedrock", litellm_provider="bedrock"),
        ProviderAccount(
            id="bedrock-main",
            provider="bedrock",
            metadata={"litellm": {"aws_region_name": "us-east-1"}},
        ),
        {},
        completion_fn=completion,
    )

    await adapter.invoke(
        {
            "model": "anthropic.claude-model",
            "messages": [{"role": "user", "content": "hello"}],
            "aws_region_name": "attacker-region-1",
        }
    )

    assert calls[0]["aws_region_name"] == "us-east-1"
    assert "attacker-region-1" not in str(calls[0])


@pytest.mark.asyncio
async def test_litellm_adapter_requires_explicit_environment_credential_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "process-global-key")
    adapter = LiteLLMProviderAdapter(
        ProviderSpec(
            "openai",
            "OpenAI",
            api_key_env="OPENAI_API_KEY",
            litellm_provider="openai",
        ),
        ProviderAccount(id="openai-main", provider="openai"),
        None,
        completion_fn=lambda **kwargs: None,
    )

    with pytest.raises(ValueError, match="no explicit credential"):
        await adapter.invoke(
            {
                "model": "gpt-model",
                "messages": [{"role": "user", "content": "hello"}],
            }
        )


@pytest.mark.asyncio
async def test_google_discovery_normalizes_models_prefix() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"models": [{"name": "models/gemini-2.5-pro"}]},
        )
    )
    adapter = LiteLLMProviderAdapter(
        ProviderSpec(
            "google",
            "Google",
            api_style="google",
            default_base_url="https://provider.test",
            models_path="/v1beta/models",
            litellm_provider="gemini",
        ),
        ProviderAccount(id="google-main", provider="google"),
        None,
        client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
        model_info_fn=lambda *args, **kwargs: {},
        supported_params_fn=lambda *args, **kwargs: [],
    )

    models = await adapter.refresh_models()

    assert models[0].id == "gemini-2.5-pro"
    assert models[0].metadata["runtime_model"] == "gemini/gemini-2.5-pro"


@pytest.mark.asyncio
async def test_litellm_adapter_streams_openai_sse() -> None:
    async def completion(**kwargs: Any) -> AsyncIterator[_DumpableResponse]:
        assert kwargs["model"] == "openai/gpt-5.4-mini"
        assert kwargs["stream"] is True

        async def chunks() -> AsyncIterator[_DumpableResponse]:
            yield _DumpableResponse({"choices": [{"delta": {"content": "hello"}, "index": 0}]})

        return chunks()

    adapter = LiteLLMProviderAdapter(
        ProviderSpec("openai", "OpenAI", litellm_provider="openai"),
        ProviderAccount(id="openai-main", provider="openai"),
        {"api_key": "key"},
        completion_fn=completion,
    )

    chunks = [
        chunk
        async for chunk in adapter.stream(
            {
                "model": "gpt-5.4-mini",
                "messages": [{"role": "user", "content": "hello"}],
            }
        )
    ]

    assert chunks[-1] == b"data: [DONE]\n\n"
    assert b'"content": "hello"' in chunks[0]


@pytest.mark.asyncio
async def test_litellm_metadata_enriches_discovered_models_by_capability() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "model-a"}]})
    )
    adapter = LiteLLMProviderAdapter(
        ProviderSpec(
            "openrouter",
            "OpenRouter",
            default_base_url="https://provider.test",
            litellm_provider="openrouter",
        ),
        ProviderAccount(id="openrouter-main", provider="openrouter"),
        {"api_key": "key"},
        client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
        model_info_fn=lambda *args, **kwargs: {
            "max_input_tokens": 200_000,
            "max_output_tokens": 8_192,
            "input_cost_per_token": 0.000001,
            "output_cost_per_token": 0.000003,
            "supports_reasoning": True,
            "supports_vision": True,
        },
        supported_params_fn=lambda *args, **kwargs: [
            "tools",
            "response_format",
            "stream",
        ],
    )

    models = await adapter.refresh_models()

    assert models[0].capabilities >= {
        "reasoning",
        "vision",
        "tool_calling",
        "json_mode",
        "structured_outputs",
        "streaming",
        "long_context",
    }
    assert models[0].input_cost_per_million == 1.0
    assert models[0].output_cost_per_million == 3.0
    assert models[0].metadata["runtime_model"] == "openrouter/model-a"


def test_builtin_provider_registry_uses_litellm_runtime() -> None:
    registry = builtin_provider_registry()

    adapter = registry.create(
        ProviderAccount(id="google-main", provider="google"),
        {"api_key": "key"},
    )

    assert isinstance(adapter, LiteLLMProviderAdapter)
    assert adapter._runtime_model("gemini-2.5-pro") == "gemini/gemini-2.5-pro"


def test_builtin_provider_registry_exposes_opencode_go_gateway() -> None:
    registry = builtin_provider_registry()
    spec = next(item for item in registry.specs() if item.id == "opencode-go")
    adapter = registry.create(
        ProviderAccount(id="opencode-go-main", provider="opencode-go"),
        {"api_key": "key"},
    )

    assert spec.display_name == "OpenCode Go"
    assert spec.default_base_url == "https://opencode.ai/zen/go/v1"
    assert isinstance(adapter, LiteLLMProviderAdapter)
    assert adapter._runtime_model("deepseek-v4-flash") == "openai/deepseek-v4-flash"


def test_litellm_status_codes_map_to_configured_fallback_triggers() -> None:
    class LiteLLMRateLimitError(Exception):
        status_code = 429

    assert OrchestrationService._classify_failure(LiteLLMRateLimitError()) == "rate_limit"


def test_direct_execution_route_is_explicitly_opt_in(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})

    default_paths = {route.path for route in create_orchestration_router(service).routes}
    enabled_paths = {
        route.path
        for route in create_orchestration_router(
            service,
            enable_direct_execution=True,
        ).routes
    }

    assert "/v1/orchestration/execute" not in default_paths
    assert "/v1/orchestration/execute" in enabled_paths
    assert "/v1/orchestration/workflows/{workflow_id}/run" not in default_paths
    assert "/v1/orchestration/workflows/{workflow_id}/run" in enabled_paths


@pytest.mark.asyncio
async def test_workflow_execution_uses_role_bound_service_and_persists_output(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {"answer": "implemented"}, "anthropic": {}})
    store = WorkflowStateStore(tmp_path / "workflows.json")
    spec = WorkflowSpec(
        id="implementation",
        tasks=[
            TaskSpec(
                id="implement",
                role="worker",
                payload={"messages": [{"role": "user", "content": "implement it"}]},
            )
        ],
    )
    workflow = store.submit(spec)

    state = await service.run_workflow(store, workflow.id, spec)

    assert state.status == "completed"
    assert state.tasks["implement"].result["routing"]["actual_model"] == "gpt-5.4-mini"
    assert state.tasks["implement"].result["response"] == {"answer": "implemented"}


class _FakeAdapter:
    def __init__(
        self,
        spec: ProviderSpec,
        account: ProviderAccount,
        credential: dict[str, Any] | None,
        behavior: dict[str, Any],
    ) -> None:
        self.spec = spec
        self.account = account
        self.credential = credential
        self.behavior = behavior

    async def authenticate(self) -> ProviderHealth:
        return ProviderHealth(True, "healthy", 1.0)

    async def health(self) -> ProviderHealth:
        return await self.authenticate()

    async def list_models(self) -> list[ModelRecord]:
        return await self.refresh_models()

    async def refresh_models(self) -> list[ModelRecord]:
        return [
            _model(
                self.account.provider, f"{self.account.provider}-model", account_id=self.account.id
            )
        ]

    async def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        outcome = self.behavior[self.account.provider]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def stream(self, request: dict[str, Any]) -> AsyncIterator[bytes]:
        outcome = self.behavior[self.account.provider]
        if isinstance(outcome, Exception):
            raise outcome
        yield f"{self.account.provider}:one".encode()
        yield b":two"

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> None:
        return None

    def estimate_latency(self, model: str) -> None:
        return None

    def capabilities(self, model: str) -> set[str]:
        return {Capability.STREAMING.value}


def _service(tmp_path: Path, behavior: dict[str, Any]) -> OrchestrationService:
    providers = ProviderAdapterRegistry()
    for provider in behavior:
        spec = ProviderSpec(provider, provider.title())
        providers.register(
            spec,
            lambda spec, account, credential, behavior=behavior: _FakeAdapter(
                spec, account, credential, behavior
            ),
        )
    service = OrchestrationService(
        config_store=LayeredConfigStore({"project": tmp_path / "config.json"}),
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=DynamicModelRegistry(),
        provider_registry=providers,
        telemetry=ExecutionTelemetryStore(),
    )
    config = OrchestrationConfig(
        providers=[
            ProviderAccount(id="openai-main", provider="openai"),
            ProviderAccount(id="anthropic-main", provider="anthropic"),
        ],
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="worker-route",
                role="worker",
                model="openai:gpt-5.4-mini",
                fallback_chain=["anthropic:claude-worker"],
            )
        ],
        settings=RoutingSettings(mode="relaxed", retries=0),
    )
    service.model_registry.register(_model("openai", "gpt-5.4-mini", account_id="openai-main"))
    service.model_registry.register(
        _model("anthropic", "claude-worker", account_id="anthropic-main")
    )
    service.replace_config(config)
    return service


@pytest.mark.asyncio
async def test_execution_retries_provider_failure_through_configured_fallback(
    tmp_path: Path,
) -> None:
    service = _service(
        tmp_path,
        {
            "openai": httpx.ReadTimeout("timeout"),
            "anthropic": {"content": [{"text": "ok"}], "usage": {"input_tokens": 4}},
        },
    )

    decision, response = await service.execute(
        RoutingRequest(role="worker"), messages=[{"role": "user", "content": "hello"}]
    )

    assert decision.provider == "anthropic"
    assert decision.fallback_used is True
    assert decision.fallback_trigger == "provider_outage"
    assert response["content"][0]["text"] == "ok"
    assert service.telemetry.list()[0]["actual_model"] == "claude-worker"


@pytest.mark.asyncio
async def test_execution_parameters_cannot_override_the_enforced_route(
    tmp_path: Path,
) -> None:
    service = _service(
        tmp_path,
        {"openai": {"choices": [{"message": {"content": "ok"}}]}, "anthropic": {}},
    )

    with pytest.raises(ValueError, match="model, provider"):
        await service.execute(
            RoutingRequest(role="worker"),
            messages=[{"role": "user", "content": "hello"}],
            parameters={"model": "attacker-model", "provider": "attacker"},
        )


def test_management_views_redact_custom_header_values(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    service.config.providers[0].custom_headers = {
        "authorization": "Bearer secret",
        "x-tenant": "private-tenant",
    }

    account = service.accounts()[0]
    public_config = service.public_config()

    assert account["custom_headers"] == {
        "authorization": "********",
        "x-tenant": "********",
    }
    assert "Bearer secret" not in str(public_config)


def test_provider_health_only_changes_the_matching_account_models() -> None:
    registry = DynamicModelRegistry()
    registry.register(_model("openai", "model-a", account_id="account-a"))
    registry.register(_model("openai", "model-a", account_id="account-b"))

    registry.mark_provider_available("openai", False, account_id="account-a")

    account_a = registry.get("openai:account-a:model-a")
    account_b = registry.get("openai:account-b:model-a")
    assert account_a is not None and account_a.available is False
    assert account_b is not None and account_b.available is True


def test_disabled_explicit_provider_account_cannot_execute(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    decision = service.route(RoutingRequest(role="worker"))
    service.config.providers[0].enabled = False

    with pytest.raises(RoutingUnavailableError) as error:
        service._execution_account(decision)

    assert error.value.reason == "unavailable"


def test_execution_telemetry_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "executions.jsonl"
    store = ExecutionTelemetryStore(path)
    store.record(
        ExecutionRecord(
            request_id="request-1",
            requested_role="worker",
            assigned_model="openai:model-a",
            actual_model="model-a",
            provider="openai",
            account_id="openai-main",
            binding_id="worker-route",
            routing_reason="deterministic_assignment",
            mode="strict",
            policy="role_locked",
            started_at="2026-07-10T00:00:00+00:00",
        )
    )

    reloaded = ExecutionTelemetryStore(path)

    assert reloaded.list()[0]["request_id"] == "request-1"


def test_execution_telemetry_redacts_upstream_credentials(tmp_path: Path) -> None:
    store = ExecutionTelemetryStore(tmp_path / "executions.jsonl")
    secret = "sk-live-never-persist"
    store.record(
        ExecutionRecord(
            request_id="request-secret",
            requested_role="worker",
            assigned_model=None,
            actual_model="model-a",
            provider="openai",
            account_id="openai-main",
            binding_id=None,
            routing_reason="provider_error",
            mode="strict",
            policy="role_locked",
            started_at="2026-07-10T00:00:00+00:00",
            error=f"Authorization: Bearer {secret}; api_key={secret}",
        )
    )

    serialized = (tmp_path / "executions.jsonl").read_text(encoding="utf-8")
    assert secret not in serialized
    assert "[REDACTED]" in serialized


@pytest.mark.asyncio
async def test_streaming_uses_the_assigned_provider(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    chunks = []

    async for decision, chunk in service.stream(
        RoutingRequest(role="worker"), messages=[{"role": "user", "content": "hello"}]
    ):
        chunks.append(chunk)

    assert decision.provider == "openai"
    assert b"".join(chunks) == b"openai:one:two"
    assert service.telemetry.list()[0]["provider"] == "openai"


@pytest.mark.asyncio
async def test_streaming_falls_back_only_before_the_first_byte(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        {"openai": httpx.ReadTimeout("timeout"), "anthropic": {}},
    )
    decisions: list[str] = []
    chunks: list[bytes] = []

    async for decision, chunk in service.stream(
        RoutingRequest(role="worker"),
        messages=[{"role": "user", "content": "hello"}],
    ):
        decisions.append(decision.provider)
        chunks.append(chunk)

    assert decisions == ["anthropic", "anthropic"]
    assert b"".join(chunks) == b"anthropic:one:two"
    execution = service.telemetry.list()[0]
    assert execution["fallback_used"] is True
    assert execution["fallback_trigger"] == "provider_outage"


@pytest.mark.asyncio
async def test_streaming_falls_back_when_account_setup_fails_before_first_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    resolve_account = service._execution_account

    def fail_openai_setup(decision):
        if decision.provider == "openai":
            raise httpx.ReadTimeout("setup timeout")
        return resolve_account(decision)

    monkeypatch.setattr(service, "_execution_account", fail_openai_setup)
    chunks = [
        chunk
        async for _, chunk in service.stream(
            RoutingRequest(role="worker"), messages=[{"role": "user", "content": "hello"}]
        )
    ]

    assert b"".join(chunks) == b"anthropic:one:two"
    execution = service.telemetry.list()[0]
    assert execution["provider"] == "anthropic"
    assert execution["fallback_trigger"] == "provider_outage"


@pytest.mark.asyncio
async def test_streaming_uses_a_total_attempt_deadline_not_per_chunk_timeout(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    service.config.settings.timeout_seconds = 0.025

    class SlowAdapter:
        async def stream(self, _request):
            while True:
                await asyncio.sleep(0.01)
                yield b"chunk"

    service.adapter = lambda _account_id: SlowAdapter()  # type: ignore[method-assign]
    received = []
    with pytest.raises(RuntimeError, match="deadline exceeded"):
        async for _, chunk in service.stream(
            RoutingRequest(role="worker"), messages=[{"role": "user", "content": "hello"}]
        ):
            received.append(chunk)

    assert received
    assert "deadline exceeded" in service.telemetry.list()[0]["error"]


@pytest.mark.asyncio
async def test_streaming_cancellation_closes_iterator_and_records_execution(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    started = asyncio.Event()
    closed = asyncio.Event()

    class BlockingAdapter:
        async def stream(self, _request):
            started.set()
            try:
                await asyncio.Event().wait()
                yield b"unreachable"
            finally:
                closed.set()

    service.adapter = lambda _account_id: BlockingAdapter()  # type: ignore[method-assign]
    iterator = service.stream(
        RoutingRequest(role="worker"), messages=[{"role": "user", "content": "hello"}]
    )
    task = asyncio.create_task(anext(iterator))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert closed.is_set()
    execution = service.telemetry.list()[0]
    assert execution["error"] == "Streaming execution was cancelled"


def test_legacy_proxy_role_header_uses_orchestration_assignment(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    handler = type(
        "Handler",
        (),
        {
            "_orchestration_service": service,
            "_orchestration_account_id": "openai-main",
            "_model_router": None,
        },
    )()
    metadata = extract_savings_metadata(request_headers={"x-cutctx-role": "worker"})

    model, routed = prepare_model_routing(
        handler,
        "gpt-5.5",
        request_savings_metadata=metadata,
        transport_provider="openai",
    )

    assert model == "gpt-5.4-mini"
    assert routed["model_routing"]["role"] == "worker"
    assert routed["model_routing"]["request_overrides"] == {"reasoning": {"effort": "high"}}


def test_legacy_proxy_role_binding_does_not_downgrade_on_unproven_transport(
    tmp_path: Path,
) -> None:
    """A role binding must not swap in a model the wire mode can't prove supports.

    Codex Responses Lite / ChatGPT subscription transports set
    ``implicit_downgrade_allowed=False`` precisely because they can't prove an
    arbitrary target model is valid in that mode. Role bindings verify
    provider/account transport but say nothing about wire-mode compatibility,
    so they must respect the same guard instead of bypassing it.
    """
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    handler = type(
        "Handler",
        (),
        {
            "_orchestration_service": service,
            "_orchestration_account_id": "openai-main",
            "_model_router": None,
        },
    )()
    metadata = extract_savings_metadata(request_headers={"x-cutctx-role": "worker"})

    model, routed = prepare_model_routing(
        handler,
        "gpt-5.5",
        request_savings_metadata=metadata,
        transport_provider="openai",
        implicit_downgrade_allowed=False,
    )

    assert model == "gpt-5.5"
    assert routed["model_routing"]["target_model"] == "gpt-5.5"
    assert routed["model_routing"]["reason"] == "downgrade_blocked_unproven_transport"


def test_legacy_proxy_refuses_unproven_provider_account(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    handler = type(
        "Handler",
        (),
        {"_orchestration_service": service, "_model_router": None},
    )()

    with pytest.raises(RoutingUnavailableError) as error:
        prepare_model_routing(
            handler,
            "role:worker",
            transport_provider="openai",
        )

    assert error.value.reason == "account_transport_mismatch"


def test_legacy_proxy_refuses_cross_provider_assignment(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    service.config.bindings[0].model = "anthropic:claude-worker"
    service.engine = DeterministicRoutingEngine(service.config, service.model_registry)
    handler = type("Handler", (), {"_orchestration_service": service, "_model_router": None})()

    with pytest.raises(RoutingUnavailableError) as error:
        prepare_model_routing(
            handler,
            "role:worker",
            transport_provider="openai",
        )

    assert error.value.reason == "transport_mismatch"

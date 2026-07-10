"""Provider adapter protocol and declarative built-in provider catalog."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast, runtime_checkable

import httpx

from .models import Capability, ModelRecord, ProviderAccount


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    display_name: str
    api_style: str = "openai"
    default_base_url: str = ""
    models_path: str = "/v1/models"
    invoke_path: str = "/v1/chat/completions"
    api_key_header: str = "authorization"
    api_key_prefix: str = "Bearer "
    api_key_env: str = ""
    local: bool = False
    auth_methods: tuple[str, ...] = ("api_key",)
    litellm_provider: str | None = None


@dataclass
class ProviderHealth:
    ok: bool
    status: str
    latency_ms: float | None = None
    detail: str | None = None


@runtime_checkable
class ProviderAdapter(Protocol):
    account: ProviderAccount

    async def authenticate(self) -> ProviderHealth: ...
    async def list_models(self) -> list[ModelRecord]: ...
    async def refresh_models(self) -> list[ModelRecord]: ...
    async def invoke(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def stream(self, request: dict[str, Any]) -> AsyncIterator[bytes]: ...
    async def health(self) -> ProviderHealth: ...
    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float | None: ...
    def estimate_latency(self, model: str) -> float | None: ...
    def capabilities(self, model: str) -> set[str]: ...


def _default_capabilities(model: dict[str, Any]) -> set[str]:
    advertised = model.get("capabilities")
    if isinstance(advertised, list):
        return {str(item) for item in advertised}
    capabilities: set[str] = set()
    if bool(model.get("streaming")):
        capabilities.add(Capability.STREAMING.value)
    if bool(model.get("tool_calling") or model.get("function_calling")):
        capabilities.add(Capability.TOOL_CALLING.value)
    if bool(model.get("json_mode")):
        capabilities.add(Capability.JSON_MODE.value)
    if bool(model.get("structured_outputs")):
        capabilities.add(Capability.STRUCTURED_OUTPUTS.value)
    if bool(model.get("vision")):
        capabilities.add(Capability.VISION.value)
    if bool(model.get("reasoning")):
        capabilities.add(Capability.REASONING.value)
    return capabilities


class HTTPProviderAdapter:
    """Data-driven adapter for OpenAI, Anthropic, Google, and compatible APIs."""

    def __init__(
        self,
        spec: ProviderSpec,
        account: ProviderAccount,
        credential: dict[str, Any] | None,
        *,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        self.spec = spec
        self.account = account
        self.credential = credential or {}
        self.client_factory = client_factory
        self._models: dict[str, ModelRecord] = {}

    @property
    def base_url(self) -> str:
        return (self.account.base_url or self.spec.default_base_url).rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {str(key): str(value) for key, value in self.account.custom_headers.items()}
        headers.update(
            {str(key): str(value) for key, value in self.credential.get("headers", {}).items()}
        )
        api_key = str(self.credential.get("api_key", "")).strip()
        if (
            not api_key
            and self.spec.api_key_env
            and bool(self.account.metadata.get("allow_environment_credentials", False))
        ):
            api_key = os.environ.get(self.spec.api_key_env, "").strip()
        if api_key:
            headers[self.spec.api_key_header] = f"{self.spec.api_key_prefix}{api_key}"
        if self.account.organization_id:
            headers.setdefault("openai-organization", self.account.organization_id)
        if self.spec.api_style == "anthropic":
            headers.setdefault("anthropic-version", "2023-06-01")
        return headers

    def _url(self, path: str) -> str:
        if not self.base_url:
            raise ValueError(f"Provider {self.spec.id} has no base URL")
        normalized_path = path if path.startswith("/") else f"/{path}"
        for api_prefix in ("/v1", "/v1beta"):
            if self.base_url.endswith(api_prefix) and (
                normalized_path == api_prefix or normalized_path.startswith(f"{api_prefix}/")
            ):
                normalized_path = normalized_path[len(api_prefix) :] or "/"
                break
        return f"{self.base_url}{normalized_path}"

    async def authenticate(self) -> ProviderHealth:
        return await self.health()

    async def health(self) -> ProviderHealth:
        import time

        started = time.perf_counter()
        try:
            async with self.client_factory(timeout=10.0) as client:
                response = await client.get(
                    self._url(str(self.account.metadata.get("models_path", self.spec.models_path))),
                    headers=self._headers(),
                )
            latency = (time.perf_counter() - started) * 1000
            if response.status_code in {401, 403}:
                return ProviderHealth(
                    False,
                    "authentication_failed",
                    latency,
                    f"Provider rejected credentials (HTTP {response.status_code})",
                )
            return ProviderHealth(
                response.is_success,
                "healthy" if response.is_success else "unhealthy",
                latency,
                None
                if response.is_success
                else f"Provider health check failed (HTTP {response.status_code})",
            )
        except Exception as exc:  # noqa: BLE001 - health must be observable, never fatal
            return ProviderHealth(
                False,
                "unreachable",
                (time.perf_counter() - started) * 1000,
                f"Provider is unreachable ({type(exc).__name__})",
            )

    async def list_models(self) -> list[ModelRecord]:
        if self._models:
            return list(self._models.values())
        return await self.refresh_models()

    async def refresh_models(self) -> list[ModelRecord]:
        async with self.client_factory(timeout=30.0) as client:
            response = await client.get(
                self._url(str(self.account.metadata.get("models_path", self.spec.models_path))),
                headers=self._headers(),
            )
            response.raise_for_status()
        payload = response.json()
        raw_models = (
            payload.get("data", payload.get("models", [])) if isinstance(payload, dict) else []
        )
        if not isinstance(raw_models, list):
            raw_models = []
        records: list[ModelRecord] = []
        for item in raw_models:
            if isinstance(item, str):
                item = {"id": item}
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or item.get("name") or "").strip()
            if self.spec.api_style == "google" and model_id.startswith("models/"):
                model_id = model_id.removeprefix("models/")
            if not model_id:
                continue
            record = ModelRecord(
                provider=self.spec.id,
                account_id=self.account.id,
                id=model_id,
                display_name=str(item.get("display_name") or item.get("displayName") or model_id),
                capabilities=_default_capabilities(item),
                context_length=int(item.get("context_length") or item.get("inputTokenLimit") or 0),
                max_output_tokens=int(
                    item.get("max_output_tokens") or item.get("outputTokenLimit") or 0
                )
                or None,
                deprecated=bool(item.get("deprecated", False)),
                available=True,
                metadata={key: value for key, value in item.items() if key not in {"id", "name"}},
            )
            records.append(record)
        self._models = {record.key: record for record in records}
        return records

    def _translate_request(self, request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        payload = dict(request)
        if self.spec.api_style == "anthropic":
            payload.setdefault("max_tokens", 4096)
            return "/v1/messages", payload
        if self.spec.api_style == "google":
            model = str(payload.pop("model"))
            messages = payload.pop("messages", [])
            contents = [
                {
                    "role": "model" if message.get("role") == "assistant" else "user",
                    "parts": [{"text": str(message.get("content", ""))}],
                }
                for message in messages
                if message.get("role") != "system"
            ]
            return f"/v1beta/models/{model}:generateContent", {"contents": contents, **payload}
        return str(self.account.metadata.get("invoke_path", self.spec.invoke_path)), payload

    async def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        path, payload = self._translate_request(request)
        async with self.client_factory(timeout=float(request.get("timeout", 120.0))) as client:
            response = await client.post(self._url(path), headers=self._headers(), json=payload)
            response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    async def stream(self, request: dict[str, Any]) -> AsyncIterator[bytes]:
        path, payload = self._translate_request({**request, "stream": True})
        async with self.client_factory(timeout=float(request.get("timeout", 120.0))) as client:
            async with client.stream(
                "POST", self._url(path), headers=self._headers(), json=payload
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float | None:
        record = self._models.get(f"{self.spec.id}:{model}")
        if (
            record is None
            or record.input_cost_per_million is None
            or record.output_cost_per_million is None
        ):
            return None
        return (
            input_tokens * record.input_cost_per_million
            + output_tokens * record.output_cost_per_million
        ) / 1_000_000

    def estimate_latency(self, model: str) -> float | None:
        record = self._models.get(f"{self.spec.id}:{model}")
        return record.latency_ms if record else None

    def capabilities(self, model: str) -> set[str]:
        record = self._models.get(f"{self.spec.id}:{model}")
        return set(record.capabilities) if record else set()


class LiteLLMProviderAdapter(HTTPProviderAdapter):
    """Use LiteLLM's OSS SDK for provider execution and model metadata.

    HTTP discovery and health checks remain data-driven so local and custom
    providers can expose their live model inventory. LiteLLM handles the hard
    part: provider-specific request/response translation, tools, reasoning,
    streaming, authentication dialects, and pricing for 100+ providers.

    Runtime imports are lazy to keep the orchestration domain importable in
    lightweight environments and to preserve CutCtx's no-``.env``-leak rule.
    """

    _REQUEST_AUTH_FIELDS = {
        "api_base",
        "api_key",
        "base_url",
        "custom_llm_provider",
        "extra_headers",
        "organization",
    }
    _ACCOUNT_RUNTIME_FIELDS = {
        "api_version",
        "aws_region_name",
        "deployment_id",
        "region_name",
        "vertex_location",
        "vertex_project",
    }
    _INFERENCE_FIELDS = {
        "audio",
        "frequency_penalty",
        "logit_bias",
        "logprobs",
        "max_completion_tokens",
        "max_tokens",
        "modalities",
        "n",
        "parallel_tool_calls",
        "prediction",
        "presence_penalty",
        "reasoning_effort",
        "response_format",
        "safety_identifier",
        "seed",
        "service_tier",
        "stop",
        "stream_options",
        "temperature",
        "thinking",
        "tool_choice",
        "tools",
        "top_logprobs",
        "top_p",
        "user",
        "verbosity",
        "web_search_options",
    }

    def __init__(
        self,
        spec: ProviderSpec,
        account: ProviderAccount,
        credential: dict[str, Any] | None,
        *,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
        completion_fn: Callable[..., Any] | None = None,
        model_info_fn: Callable[..., Any] | None = None,
        supported_params_fn: Callable[..., Any] | None = None,
        completion_cost_fn: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(
            spec,
            account,
            credential,
            client_factory=client_factory,
        )
        self._completion_fn = completion_fn
        self._model_info_fn = model_info_fn
        self._supported_params_fn = supported_params_fn
        self._completion_cost_fn = completion_cost_fn

    @staticmethod
    def _runtime() -> Any:
        from cutctx.backends import litellm as runtime

        if not runtime.LITELLM_AVAILABLE:
            raise RuntimeError("LiteLLM is required for orchestration execution; install cutctx-ai")
        return runtime

    def _provider_name(self) -> str:
        configured = str(self.account.metadata.get("litellm_provider", "")).strip()
        return configured or self.spec.litellm_provider or self.spec.id

    def _runtime_model(self, model: str) -> str:
        provider = self._provider_name().strip("/")
        if provider == "gemini" and model.startswith("models/"):
            model = model.removeprefix("models/")
        if model.startswith(f"{provider}/"):
            return model
        return f"{provider}/{model}"

    def _runtime_kwargs(self, request: dict[str, Any], *, stream: bool) -> dict[str, Any]:
        unknown = sorted(
            set(request)
            - self._INFERENCE_FIELDS
            - self._REQUEST_AUTH_FIELDS
            - self._ACCOUNT_RUNTIME_FIELDS
            - {"messages", "model", "stream"}
        )
        if unknown:
            raise ValueError(
                "Unsupported orchestration inference parameters: " + ", ".join(unknown)
            )
        payload = {key: value for key, value in request.items() if key in self._INFERENCE_FIELDS}
        payload["messages"] = request.get("messages", [])
        payload["model"] = self._runtime_model(str(request["model"]))
        payload["stream"] = stream
        payload["num_retries"] = 0
        payload["fallbacks"] = []

        api_key = str(self.credential.get("api_key", "")).strip()
        allow_environment = bool(self.account.metadata.get("allow_environment_credentials", False))
        if not api_key and self.spec.api_key_env and allow_environment:
            api_key = os.environ.get(self.spec.api_key_env, "").strip()
        if api_key:
            payload["api_key"] = api_key
        elif self.spec.api_key_env and not self.spec.local:
            raise ValueError(
                f"Provider account {self.account.id!r} has no explicit credential; "
                "set allow_environment_credentials=true to opt into process credentials"
            )

        if self.account.base_url or self.spec.local:
            payload["base_url"] = self.base_url
        if self.account.organization_id:
            payload["organization"] = self.account.organization_id

        headers = {str(key): str(value) for key, value in self.account.custom_headers.items()}
        headers.update(
            {str(key): str(value) for key, value in self.credential.get("headers", {}).items()}
        )
        if headers:
            payload["extra_headers"] = headers

        runtime_options = self.account.metadata.get("litellm", {})
        if isinstance(runtime_options, dict):
            payload.update(
                {
                    key: value
                    for key, value in runtime_options.items()
                    if key in self._ACCOUNT_RUNTIME_FIELDS
                }
            )
        return payload

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return cast("dict[str, Any]", value)
        if hasattr(value, "model_dump"):
            return cast(
                "dict[str, Any]",
                value.model_dump(exclude_none=True, exclude_unset=True),
            )
        if hasattr(value, "json"):
            parsed = json.loads(value.json())
            if isinstance(parsed, dict):
                return cast("dict[str, Any]", parsed)
        raise TypeError(f"Unsupported LiteLLM response type: {type(value).__name__}")

    def _completion(self) -> Callable[..., Any]:
        return self._completion_fn or self._runtime().acompletion

    def _model_info(self) -> Callable[..., Any]:
        return self._model_info_fn or self._runtime().litellm.get_model_info

    def _supported_params(self) -> Callable[..., Any]:
        return self._supported_params_fn or self._runtime().litellm.get_supported_openai_params

    def _completion_cost(self) -> Callable[..., Any]:
        return self._completion_cost_fn or self._runtime().litellm.completion_cost

    async def refresh_models(self) -> list[ModelRecord]:
        records = await super().refresh_models()
        for record in records:
            self._enrich_model(record)
        return records

    def _enrich_model(self, record: ModelRecord) -> None:
        model_info = self._model_info()
        supported_params = self._supported_params()
        runtime_model = self._runtime_model(record.id)
        provider = self._provider_name()
        try:
            raw_info = model_info(runtime_model, custom_llm_provider=provider)
            info = self._as_dict(raw_info) if not isinstance(raw_info, dict) else raw_info
        except Exception:  # noqa: BLE001 - unknown models remain discoverable
            info = {}
        try:
            params = set(supported_params(runtime_model, custom_llm_provider=provider) or [])
        except Exception:  # noqa: BLE001 - provider metadata is best effort
            params = set()

        flag_capabilities = {
            "supports_function_calling": Capability.TOOL_CALLING.value,
            "supports_reasoning": Capability.REASONING.value,
            "supports_response_schema": Capability.STRUCTURED_OUTPUTS.value,
            "supports_vision": Capability.VISION.value,
            "supports_audio_input": Capability.AUDIO.value,
            "supports_audio_output": Capability.AUDIO.value,
            "supports_native_streaming": Capability.STREAMING.value,
        }
        for flag, capability in flag_capabilities.items():
            if info.get(flag):
                record.capabilities.add(capability)
        if "tools" in params:
            record.capabilities.add(Capability.TOOL_CALLING.value)
        if "response_format" in params:
            record.capabilities.update(
                {
                    Capability.JSON_MODE.value,
                    Capability.STRUCTURED_OUTPUTS.value,
                }
            )
        if "reasoning_effort" in params:
            record.capabilities.add(Capability.REASONING.value)
        if "thinking" in params:
            record.capabilities.add(Capability.THINKING.value)
        if "stream" in params:
            record.capabilities.add(Capability.STREAMING.value)

        record.context_length = int(
            info.get("max_input_tokens") or info.get("max_tokens") or record.context_length
        )
        record.max_output_tokens = (
            int(info["max_output_tokens"])
            if info.get("max_output_tokens") is not None
            else record.max_output_tokens
        )
        if record.context_length >= 128_000:
            record.capabilities.add(Capability.LONG_CONTEXT.value)
        if info.get("input_cost_per_token") is not None:
            record.input_cost_per_million = float(info["input_cost_per_token"]) * 1_000_000
        if info.get("output_cost_per_token") is not None:
            record.output_cost_per_million = float(info["output_cost_per_token"]) * 1_000_000
        record.metadata["runtime"] = "litellm"
        record.metadata["runtime_model"] = runtime_model

    async def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        response = await self._completion()(**self._runtime_kwargs(request, stream=False))
        return self._as_dict(response)

    async def stream(self, request: dict[str, Any]) -> AsyncIterator[bytes]:
        response = await self._completion()(**self._runtime_kwargs(request, stream=True))
        try:
            async for chunk in response:
                yield f"data: {json.dumps(self._as_dict(chunk))}\n\n".encode()
            yield b"data: [DONE]\n\n"
        finally:
            if hasattr(response, "aclose"):
                await response.aclose()

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float | None:
        try:
            return float(
                self._completion_cost()(
                    model=self._runtime_model(model),
                    prompt="",
                    completion="",
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens,
                )
            )
        except Exception:  # noqa: BLE001 - unknown pricing is valid
            return super().estimate_cost(model, input_tokens, output_tokens)


class ProviderAdapterRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ProviderSpec] = {}
        self._factories: dict[
            str, Callable[[ProviderSpec, ProviderAccount, dict[str, Any] | None], ProviderAdapter]
        ] = {}

    def register(
        self,
        spec: ProviderSpec,
        factory: Callable[[ProviderSpec, ProviderAccount, dict[str, Any] | None], ProviderAdapter]
        | None = None,
    ) -> None:
        self._specs[spec.id] = spec
        self._factories[spec.id] = factory or HTTPProviderAdapter

    def create(
        self, account: ProviderAccount, credential: dict[str, Any] | None = None
    ) -> ProviderAdapter:
        try:
            return self._factories[account.provider](
                self._specs[account.provider], account, credential
            )
        except KeyError as exc:
            raise ValueError(f"Unknown provider: {account.provider}") from exc

    def specs(self) -> list[ProviderSpec]:
        return sorted(self._specs.values(), key=lambda item: item.display_name.lower())


def builtin_provider_registry() -> ProviderAdapterRegistry:
    registry = ProviderAdapterRegistry()
    specs = [
        ProviderSpec(
            "openai",
            "OpenAI",
            default_base_url="https://api.openai.com",
            api_key_env="OPENAI_API_KEY",
            litellm_provider="openai",
        ),
        ProviderSpec(
            "anthropic",
            "Anthropic",
            api_style="anthropic",
            default_base_url="https://api.anthropic.com",
            api_key_header="x-api-key",
            api_key_prefix="",
            api_key_env="ANTHROPIC_API_KEY",
            litellm_provider="anthropic",
        ),
        ProviderSpec(
            "google",
            "Google Gemini",
            api_style="google",
            default_base_url="https://generativelanguage.googleapis.com",
            models_path="/v1beta/models",
            api_key_header="x-goog-api-key",
            api_key_prefix="",
            api_key_env="GEMINI_API_KEY",
            litellm_provider="gemini",
        ),
        ProviderSpec(
            "openrouter",
            "OpenRouter",
            default_base_url="https://openrouter.ai/api",
            api_key_env="OPENROUTER_API_KEY",
            litellm_provider="openrouter",
        ),
        ProviderSpec(
            "deepseek",
            "DeepSeek",
            default_base_url="https://api.deepseek.com",
            api_key_env="DEEPSEEK_API_KEY",
            litellm_provider="deepseek",
        ),
        ProviderSpec(
            "kimi",
            "Kimi / Moonshot",
            default_base_url="https://api.moonshot.ai",
            api_key_env="MOONSHOT_API_KEY",
            litellm_provider="moonshot",
        ),
        ProviderSpec(
            "minimax",
            "MiniMax",
            default_base_url="https://api.minimax.chat",
            api_key_env="MINIMAX_API_KEY",
            litellm_provider="minimax",
        ),
        ProviderSpec(
            "qwen",
            "Qwen / DashScope",
            default_base_url="https://dashscope-intl.aliyuncs.com/compatible-mode",
            api_key_env="DASHSCOPE_API_KEY",
            litellm_provider="dashscope",
        ),
        ProviderSpec(
            "glm",
            "GLM / Zhipu",
            default_base_url="https://open.bigmodel.cn/api/paas",
            api_key_env="ZHIPUAI_API_KEY",
            litellm_provider="zai",
        ),
        ProviderSpec(
            "groq",
            "Groq",
            default_base_url="https://api.groq.com/openai",
            api_key_env="GROQ_API_KEY",
            litellm_provider="groq",
        ),
        ProviderSpec(
            "ollama",
            "Ollama",
            default_base_url="http://127.0.0.1:11434",
            local=True,
            auth_methods=("none",),
            litellm_provider="ollama",
        ),
        ProviderSpec(
            "lmstudio",
            "LM Studio",
            default_base_url="http://127.0.0.1:1234",
            local=True,
            auth_methods=("none",),
            litellm_provider="lm_studio",
        ),
        ProviderSpec(
            "azure-openai",
            "Azure OpenAI",
            api_key_header="api-key",
            api_key_prefix="",
            api_key_env="AZURE_API_KEY",
            auth_methods=("api_key",),
            litellm_provider="azure",
        ),
        ProviderSpec("openai-compatible", "OpenAI-compatible API", litellm_provider="openai"),
        ProviderSpec("custom", "Custom endpoint", litellm_provider="openai"),
    ]
    for spec in specs:
        registry.register(spec, LiteLLMProviderAdapter)
    return registry

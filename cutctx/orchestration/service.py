"""Composition root for configuration, routing, providers, execution, and telemetry."""

from __future__ import annotations

import asyncio
import copy
import math
import os
import threading
import time
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .audit import ReceiptAuditStore
from .config import LayeredConfigStore, default_config_paths
from .credentials import CredentialStore, EncryptedCredentialStore
from .engine import DeterministicRoutingEngine, RoutingUnavailableError
from .models import (
    ExecutionRecord,
    FallbackTrigger,
    OrchestrationConfig,
    OutcomeRecord,
    ProviderAccount,
    RoutingDecision,
    RoutingMode,
    RoutingPolicy,
    RoutingRequest,
    TaskType,
    config_from_dict,
    to_dict,
)
from .policy_bundle import compile_policy_bundle
from .providers import ProviderAdapter, ProviderAdapterRegistry, builtin_provider_registry
from .registry import DynamicModelRegistry
from .telemetry import ExecutionTelemetryStore, OutcomeTelemetryStore
from .workflow import TaskSpec, WorkflowRunner, WorkflowSpec, WorkflowState, WorkflowStateStore


class OrchestrationService:
    _RESERVED_EXECUTION_PARAMETERS = {
        "account_id",
        "messages",
        "model",
        "provider",
        "request_id",
        "role",
        "routing",
        "selectors",
        "stream",
    }
    _COOLDOWN_TRIGGERS = {
        FallbackTrigger.TIMEOUT.value,
        FallbackTrigger.RATE_LIMIT.value,
        FallbackTrigger.PROVIDER_OUTAGE.value,
        FallbackTrigger.AUTH_FAILURE.value,
        FallbackTrigger.QUOTA_EXHAUSTED.value,
    }

    def __init__(
        self,
        *,
        config_store: LayeredConfigStore,
        credential_store: CredentialStore,
        model_registry: DynamicModelRegistry,
        provider_registry: ProviderAdapterRegistry | None = None,
        telemetry: ExecutionTelemetryStore | None = None,
        outcome_telemetry: OutcomeTelemetryStore | None = None,
        receipt_audit: ReceiptAuditStore | None = None,
        workflow_store: WorkflowStateStore | None = None,
    ) -> None:
        self.config_store = config_store
        self.credential_store = credential_store
        self.model_registry = model_registry
        self.provider_registry = provider_registry or builtin_provider_registry()
        self.telemetry = telemetry or ExecutionTelemetryStore()
        self.outcome_telemetry = outcome_telemetry or OutcomeTelemetryStore()
        self.receipt_audit = receipt_audit
        self.workflow_store = workflow_store or WorkflowStateStore(
            Path.home() / ".cutctx" / "orchestration" / "workflows.json"
        )
        self._state_lock = threading.RLock()
        self.config = self.config_store.load()
        if self.config.models:
            self.model_registry.sync_configured(self.config.models)
        self._validate_config(self.config)
        self.engine = DeterministicRoutingEngine(
            self.config,
            self.model_registry,
            require_configured_accounts=True,
        )

    def replace_config(
        self, config: OrchestrationConfig | dict[str, Any], *, layer: str = "project"
    ) -> OrchestrationConfig:
        if isinstance(config, dict):
            restored = self._restore_redacted_provider_fields(config)
            parsed = config_from_dict(restored)
        else:
            parsed = config
        with self._state_lock:
            effective = self.config_store.preview(parsed, layer=layer)
            self._validate_config(effective)
            self.config_store.save(parsed, layer=layer)
            self._activate_config(effective)
            return self.config

    def _restore_redacted_provider_fields(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Preserve secrets represented by management-API mask sentinels."""
        restored = copy.deepcopy(payload)
        existing = {account.id: account for account in self.config.providers}
        providers = restored.get("providers", [])
        if not isinstance(providers, list):
            return restored
        for item in providers:
            if not isinstance(item, dict):
                continue
            account = existing.get(str(item.get("id", "")))
            headers = item.get("custom_headers")
            if account is None or not isinstance(headers, dict):
                continue
            item["custom_headers"] = {
                str(key): (
                    account.custom_headers.get(str(key), str(value))
                    if value == "********"
                    else str(value)
                )
                for key, value in headers.items()
            }
        return restored

    def route(
        self,
        request: RoutingRequest,
        *,
        allow_overrides: bool = False,
    ) -> RoutingDecision:
        with self._state_lock:
            return self.engine.route(
                self._apply_policy_defaults(request), allow_overrides=allow_overrides
            )

    def _apply_policy_defaults(self, request: RoutingRequest) -> RoutingRequest:
        """Intersect caller constraints with effective layered policy limits.

        The service owns this merge so every entry point—preview, direct
        execution, proxy routing, and workflow execution—uses identical,
        non-bypassable organization/project limits.
        """
        if request.task_type is not None and request.task_type not in {
            value.value for value in TaskType
        }:
            raise ValueError(f"Unknown task type: {request.task_type!r}")
        settings = self.config.settings
        profile = self._profile(request.profile)

        def narrow(caller: set[str], policy: set[str]) -> set[str]:
            normalized_policy = {value.casefold() for value in policy}
            if not normalized_policy:
                return set(caller)
            if not caller:
                return set(policy)
            narrowed = {value for value in caller if value.casefold() in normalized_policy}
            if not narrowed:
                raise ValueError("Request constraints do not satisfy organization/project policy")
            return narrowed

        if profile is not None:
            request = replace(
                request,
                role=request.role or profile.role,
                required_capabilities={
                    *request.required_capabilities,
                    *profile.required_capabilities,
                },
                allowed_providers=narrow(request.allowed_providers, profile.allowed_providers),
                max_cost_usd=(
                    min(request.max_cost_usd, profile.max_cost_usd)
                    if request.max_cost_usd is not None and profile.max_cost_usd is not None
                    else request.max_cost_usd
                    if profile.max_cost_usd is None
                    else profile.max_cost_usd
                ),
            )
        return replace(
            request,
            allowed_providers=narrow(request.allowed_providers, settings.allowed_providers),
            allowed_regions=narrow(request.allowed_regions, settings.allowed_regions),
            allowed_data_classifications=narrow(
                request.allowed_data_classifications, settings.allowed_data_classifications
            ),
            policy_version=settings.policy_version,
        )

    def _profile(self, profile_id: str | None) -> Any | None:
        if profile_id is None:
            return None
        for profile in self.config.profiles:
            if profile.id.casefold() == profile_id.casefold():
                return profile
        raise ValueError(f"Unknown routing profile: {profile_id!r}")

    def routing_profiles(self) -> list[dict[str, Any]]:
        return [to_dict(profile) for profile in self.config.profiles]

    def record_outcome(self, outcome: OutcomeRecord | dict[str, Any]) -> dict[str, Any]:
        """Persist bounded evaluation signals after validating their contract."""
        parsed = OutcomeRecord(**outcome) if isinstance(outcome, dict) else outcome
        if not parsed.request_id.strip():
            raise ValueError("Outcome request_id must not be empty")
        if parsed.task_type not in {value.value for value in TaskType}:
            raise ValueError(f"Unknown task type: {parsed.task_type!r}")
        if parsed.developer_rating is not None and not 1 <= parsed.developer_rating <= 5:
            raise ValueError("developer_rating must be between 1 and 5")
        if not parsed.recorded_at:
            parsed = replace(parsed, recorded_at=datetime.now(timezone.utc).isoformat())
        self.outcome_telemetry.record(parsed)
        return to_dict(parsed)

    def shadow_route(
        self,
        request: RoutingRequest,
        *,
        candidate_profile: str | None = None,
        candidate_policy: str | None = None,
        candidate_model: str | None = None,
    ) -> dict[str, Any]:
        """Compare a candidate route without invoking a provider.

        Shadow mode is intentionally a pure decision comparison: unlike a
        provider replay it creates no cost, no side effects, and no new model
        output. That makes it safe to expose before a scheduler is trusted to
        alter live execution.
        """
        baseline = self.route(request, allow_overrides=True)
        candidate_request = replace(
            request,
            profile=None if candidate_model else candidate_profile or request.profile,
            policy=candidate_policy or request.policy,
            requested_model=candidate_model or request.requested_model,
            # A model candidate is a deliberate manual comparison, not a
            # hidden override of an existing role binding.
            role=None if candidate_model else request.role,
        )
        candidate = self.route(candidate_request, allow_overrides=True)
        changed = (
            baseline.provider != candidate.provider
            or baseline.account_id != candidate.account_id
            or baseline.actual_model != candidate.actual_model
        )
        return {
            "shadow_version": 1,
            "executed": False,
            "changed": changed,
            "baseline": to_dict(baseline),
            "candidate": to_dict(candidate),
        }

    def provider_specs(self) -> list[dict[str, Any]]:
        configured = {account.provider for account in self.config.providers}
        return [
            {
                "id": spec.id,
                "display_name": spec.display_name,
                "api_style": spec.api_style,
                "default_base_url": spec.default_base_url,
                "runtime": "litellm" if spec.litellm_provider else "http",
                "runtime_provider": spec.litellm_provider,
                "auth_methods": list(spec.auth_methods),
                "local": spec.local,
                "configured": spec.id in configured,
            }
            for spec in self.provider_registry.specs()
        ]

    def capability_manifest(self) -> dict[str, Any]:
        """Return the deployment-scoped capability contract used for routing.

        Discovery is useful but never treated as verification. Operators mark a
        deployment verified only after exercising the capability against the
        target account/region. This makes the public matrix honest about the
        difference between advertised and supported behavior.
        """
        deployments: list[dict[str, Any]] = []
        for model in self.model_registry.list():
            metadata = model.metadata if isinstance(model.metadata, dict) else {}
            verified = metadata.get("capability_verified") is True
            deployments.append(
                {
                    "deployment_key": model.deployment_key,
                    "provider": model.provider,
                    "account_id": model.account_id,
                    "model": model.id,
                    "capabilities": sorted(model.capabilities),
                    "verification": {
                        "status": "verified" if verified else "advertised",
                        "verified_at": metadata.get("capability_verified_at"),
                        "source": metadata.get("capability_source", "registry"),
                    },
                }
            )
        return {"manifest_version": 1, "deployments": deployments}

    def policy_bundle(self) -> dict[str, Any]:
        """Return the effective bundle; signing occurs in the customer key boundary."""
        with self._state_lock:
            return compile_policy_bundle(self.config)

    def accounts(self) -> list[dict[str, Any]]:
        credential_refs = set(self.credential_store.references())
        return [
            {
                **self._public_account(account),
                "credential_configured": bool(
                    account.credential_ref and account.credential_ref in credential_refs
                ),
            }
            for account in self.config.providers
        ]

    def public_config(self) -> dict[str, Any]:
        payload = to_dict(self.config)
        payload["providers"] = [self._public_account(account) for account in self.config.providers]
        return payload

    @staticmethod
    def _public_account(account: ProviderAccount) -> dict[str, Any]:
        payload = to_dict(account)
        payload["custom_headers"] = {str(key): "********" for key in account.custom_headers}
        return payload

    def put_account(
        self,
        account_id: str,
        account: ProviderAccount | dict[str, Any],
        *,
        layer: str = "user",
    ) -> dict[str, Any]:
        if isinstance(account, dict):
            payload = dict(account)
            payload["id"] = account_id
            restored = self._restore_redacted_provider_fields({"providers": [payload]})
            providers = config_from_dict(restored).providers
            if not providers:
                raise ValueError(f"Provider account {account_id} is invalid")
            parsed = providers[0]
        else:
            if account.id != account_id:
                raise ValueError(
                    f"Provider account id mismatch: expected {account_id}, got {account.id}"
                )
            parsed = account
        with self._state_lock:
            payload, effective = self.config_store.prepare_provider_patch(
                account_id,
                to_dict(parsed),
                layer=layer,
            )
            self._validate_config(effective)
            self.config_store.save_payload(payload, layer=layer)
            self._activate_config(effective)
            return self._public_account(self._account(account_id))

    def put_credential(
        self, account_id: str, secret: dict[str, Any], *, layer: str = "user"
    ) -> str:
        account = self._account(account_id)
        reference = account.credential_ref or f"provider:{account.id}"
        self.credential_store.put(reference, secret)
        if account.credential_ref != reference:
            with self._state_lock:
                payload, effective = self.config_store.prepare_provider_patch(
                    account.id,
                    {"credential_ref": reference},
                    layer=layer,
                )
                self._validate_config(effective)
                self.config_store.save_payload(payload, layer=layer)
                self._activate_config(effective)
        return reference

    def delete_credential(self, account_id: str) -> bool:
        account = self._account(account_id)
        return bool(account.credential_ref and self.credential_store.delete(account.credential_ref))

    def adapter(self, account_id: str) -> ProviderAdapter:
        account = self._account(account_id)
        credential = (
            self.credential_store.get(account.credential_ref) if account.credential_ref else None
        )
        return self.provider_registry.create(account, credential)

    def _activate_config(self, effective: OrchestrationConfig) -> None:
        self._validate_config(effective)
        candidate_engine = DeterministicRoutingEngine(
            effective,
            self.model_registry,
            require_configured_accounts=True,
        )
        self.model_registry.sync_configured(effective.models)
        self.config = effective
        self.engine = candidate_engine

    async def test_account(self, account_id: str) -> dict[str, Any]:
        health = await self.adapter(account_id).authenticate()
        account = self._account(account_id)
        self.model_registry.update_provider_runtime_signals(
            account.provider,
            account_id=account.id,
            health_score=1.0 if health.ok else 0.0,
            latency_ms=health.latency_ms,
        )
        if health.ok:
            self.model_registry.clear_provider_cooldowns(account.provider, account_id=account.id)
        return {
            "ok": health.ok,
            "status": health.status,
            "latency_ms": health.latency_ms,
            "detail": health.detail,
        }

    async def refresh_models(self, account_id: str) -> list[dict[str, Any]]:
        models = await self.model_registry.refresh(self.adapter(account_id))
        return [
            to_dict(model) | {"key": model.key, "deployment_key": model.deployment_key}
            for model in models
        ]

    async def execute(
        self,
        request: RoutingRequest,
        *,
        messages: list[dict[str, Any]],
        parameters: dict[str, Any] | None = None,
    ) -> tuple[RoutingDecision, dict[str, Any]]:
        execution_parameters = self._execution_parameters(parameters)
        decision = self.route(request)
        attempts = 0
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        error: Exception | None = None
        response: dict[str, Any] | None = None
        execution_adapter: ProviderAdapter | None = None
        max_attempts = max(1, self.config.settings.retries + 1)

        while attempts < max_attempts:
            attempts += 1
            try:
                account = self._execution_account(decision)
                adapter = self.adapter(account.id)
                execution_adapter = adapter
                response = await asyncio.wait_for(
                    adapter.invoke(
                        {
                            "model": decision.actual_model,
                            "messages": messages,
                            **execution_parameters,
                        }
                    ),
                    timeout=self.config.settings.timeout_seconds,
                )
                error = None
                break
            except Exception as exc:  # noqa: BLE001 - translated to deterministic fallback trigger
                error = exc
                trigger = self._classify_failure(exc)
                if attempts < max_attempts:
                    continue
                self._cool_down_after_failure(decision, trigger)
                try:
                    decision = self.engine.fallback(decision, trigger)
                except RoutingUnavailableError:
                    break
                max_attempts += max(1, self.config.settings.retries + 1)

        latency_ms = (time.perf_counter() - started) * 1000
        usage = response.get("usage", {}) if isinstance(response, dict) else {}
        input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
        output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
        cost_usd = None
        if (
            execution_adapter is not None
            and isinstance(input_tokens, int)
            and isinstance(output_tokens, int)
        ):
            cost_usd = execution_adapter.estimate_cost(
                decision.actual_model,
                input_tokens,
                output_tokens,
            )
        record = ExecutionRecord(
            request_id=decision.request_id,
            requested_role=decision.role,
            assigned_model=decision.assigned_model,
            actual_model=decision.actual_model,
            provider=decision.provider,
            account_id=decision.account_id,
            binding_id=decision.binding_id,
            routing_reason=decision.reason,
            mode=decision.mode,
            policy=decision.policy,
            started_at=started_at,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            retries=max(0, attempts - 1),
            fallback_used=decision.fallback_used,
            fallback_trigger=decision.fallback_trigger,
            fallback_from=decision.fallback_from,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_hit=usage.get("cache_hit"),
            error=str(error) if error else None,
            policy_version=str(decision.policy_constraints.get("policy_version", "1")),
            policy_constraints=dict(decision.policy_constraints),
            task_type=request.task_type,
        )
        self.telemetry.record(record)
        if self.receipt_audit is not None:
            self.receipt_audit.append(decision, execution_id=f"{decision.request_id}:{started_at}")
        if error is not None or response is None:
            raise RuntimeError(
                f"Assigned model {decision.actual_model} failed after {attempts} attempt(s): {error}"
            ) from error
        return decision, response

    async def run_workflow(
        self,
        store: WorkflowStateStore,
        workflow_id: str,
        spec: WorkflowSpec | None = None,
        *,
        max_concurrency: int = 4,
    ) -> WorkflowState:
        """Run durable role-bound tasks through the canonical executor."""

        async def execute_task(_task_id: str, task: TaskSpec) -> dict[str, Any]:
            messages = task.payload.get("messages", [])
            parameters = task.payload.get("parameters", {})
            if not isinstance(messages, list) or not isinstance(parameters, dict):
                raise ValueError("workflow task payload requires messages and parameters")
            decision, response = await self.execute(
                RoutingRequest(role=task.role), messages=messages, parameters=parameters
            )
            return {"routing": to_dict(decision), "response": response}

        return await WorkflowRunner(store, execute_task, max_concurrency=max_concurrency).run(
            workflow_id, spec
        )

    async def stream(
        self,
        request: RoutingRequest,
        *,
        messages: list[dict[str, Any]],
        parameters: dict[str, Any] | None = None,
    ) -> AsyncIterator[tuple[RoutingDecision, bytes]]:
        execution_parameters = self._execution_parameters(parameters)
        decision = self.route(request)
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        attempts = 0
        max_attempts = max(1, self.config.settings.retries + 1)
        error: Exception | None = None
        iterator: AsyncIterator[bytes] | None = None

        try:
            while attempts < max_attempts:
                attempts += 1
                emitted = False
                try:
                    # Provider/account setup is part of a streaming attempt.
                    # It must receive the same pre-first-byte retry/fallback
                    # policy as an error raised by the iterator itself.
                    account = self._execution_account(decision)
                    adapter = self.adapter(account.id)
                    iterator = adapter.stream(
                        {
                            "model": decision.actual_model,
                            "messages": messages,
                            "timeout": self.config.settings.timeout_seconds,
                            **execution_parameters,
                        }
                    )
                    deadline = time.perf_counter() + self.config.settings.timeout_seconds
                    while True:
                        remaining = deadline - time.perf_counter()
                        if remaining <= 0:
                            raise TimeoutError("streaming execution deadline exceeded")
                        try:
                            chunk = await asyncio.wait_for(anext(iterator), timeout=remaining)
                        except TimeoutError as exc:
                            raise TimeoutError("streaming execution deadline exceeded") from exc
                        emitted = True
                        yield decision, chunk
                except StopAsyncIteration:
                    error = None
                    break
                except asyncio.CancelledError:
                    error = RuntimeError("Streaming execution was cancelled")
                    raise
                except Exception as exc:  # noqa: BLE001 - normalized into fallback policy
                    error = exc
                    trigger = self._classify_failure(exc)
                    if emitted:
                        # Switching providers after bytes are visible would
                        # corrupt the stream. Report the terminal error instead.
                        self._cool_down_after_failure(decision, trigger)
                        break
                    if attempts < max_attempts:
                        continue
                    self._cool_down_after_failure(decision, trigger)
                    try:
                        decision = self.engine.fallback(decision, trigger)
                    except RoutingUnavailableError:
                        break
                    max_attempts += max(1, self.config.settings.retries + 1)
                finally:
                    if iterator is not None and hasattr(iterator, "aclose"):
                        await iterator.aclose()
                    iterator = None
        finally:
            self.telemetry.record(
                ExecutionRecord(
                    request_id=decision.request_id,
                    requested_role=decision.role,
                    assigned_model=decision.assigned_model,
                    actual_model=decision.actual_model,
                    provider=decision.provider,
                    account_id=decision.account_id,
                    binding_id=decision.binding_id,
                    routing_reason=decision.reason,
                    mode=decision.mode,
                    policy=decision.policy,
                    started_at=started_at,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    retries=max(0, attempts - 1),
                    fallback_used=decision.fallback_used,
                    fallback_trigger=decision.fallback_trigger,
                    fallback_from=decision.fallback_from,
                    error=str(error) if error else None,
                    policy_version=str(decision.policy_constraints.get("policy_version", "1")),
                    policy_constraints=dict(decision.policy_constraints),
                    task_type=request.task_type,
                )
            )
            if self.receipt_audit is not None:
                self.receipt_audit.append(
                    decision, execution_id=f"{decision.request_id}:{started_at}"
                )
        if error is not None:
            raise RuntimeError(
                f"Assigned model {decision.actual_model} failed during streaming: {error}"
            ) from error

    @classmethod
    def _execution_parameters(
        cls,
        parameters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        values = dict(parameters or {})
        reserved = sorted(cls._RESERVED_EXECUTION_PARAMETERS.intersection(values))
        if reserved:
            raise ValueError(
                "Execution parameters cannot override routing fields: " + ", ".join(reserved)
            )
        return values

    def _execution_account(self, decision: RoutingDecision) -> ProviderAccount:
        if decision.account_id:
            account = self._account(decision.account_id)
            if not account.enabled:
                raise RoutingUnavailableError(
                    f"Assigned provider account {account.id!r} is disabled",
                    assigned_model=decision.assigned_model,
                    reason=FallbackTrigger.UNAVAILABLE.value,
                )
            if account.provider != decision.provider:
                raise RoutingUnavailableError(
                    f"Assigned account {account.id!r} belongs to {account.provider}, "
                    f"not {decision.provider}",
                    assigned_model=decision.assigned_model,
                    reason=FallbackTrigger.AUTH_FAILURE.value,
                )
            return account
        accounts = [
            account
            for account in self.config.providers
            if account.provider == decision.provider and account.enabled
        ]
        if not accounts:
            raise RoutingUnavailableError(
                f"No enabled account is configured for provider {decision.provider}",
                assigned_model=decision.assigned_model,
                reason=FallbackTrigger.AUTH_FAILURE.value,
            )
        return sorted(accounts, key=lambda item: item.id)[0]

    def _cool_down_after_failure(self, decision: RoutingDecision, trigger: str) -> None:
        if trigger not in self._COOLDOWN_TRIGGERS:
            return
        try:
            self.model_registry.cool_down(
                self.engine._decision_deployment_key(decision),
                self.config.settings.deployment_cooldown_seconds,
            )
        except KeyError:
            # The execution path can surface a stale registry entry; fallback
            # remains responsible for its normal unavailable handling.
            return

    def _account(self, account_id: str) -> ProviderAccount:
        for account in self.config.providers:
            if account.id == account_id:
                return account
        raise KeyError(f"Unknown provider account: {account_id}")

    @staticmethod
    def _classify_failure(exc: Exception) -> str:
        if isinstance(exc, asyncio.TimeoutError | TimeoutError):
            return FallbackTrigger.TIMEOUT.value
        status_code = getattr(exc, "status_code", None)
        if status_code is None:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            if status_code in {401, 403}:
                return FallbackTrigger.AUTH_FAILURE.value
            if status_code == 429:
                return FallbackTrigger.RATE_LIMIT.value
            if status_code in {402, 409}:
                return FallbackTrigger.QUOTA_EXHAUSTED.value
            if status_code >= 500:
                return FallbackTrigger.PROVIDER_OUTAGE.value
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status in {401, 403}:
                return FallbackTrigger.AUTH_FAILURE.value
            if status == 429:
                return FallbackTrigger.RATE_LIMIT.value
            if status in {402, 409}:
                return FallbackTrigger.QUOTA_EXHAUSTED.value
            if status >= 500:
                return FallbackTrigger.PROVIDER_OUTAGE.value
        if isinstance(exc, httpx.TransportError):
            return FallbackTrigger.PROVIDER_OUTAGE.value
        return FallbackTrigger.UNKNOWN.value

    def _validate_config(self, config: OrchestrationConfig) -> None:
        def unique(items: list[Any], label: str, *, casefold: bool = False) -> None:
            identifiers = [str(item.id) for item in items]
            if casefold:
                identifiers = [identifier.casefold() for identifier in identifiers]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"Duplicate {label} ids are not allowed")

        unique(config.providers, "provider account")
        unique(config.roles, "role", casefold=True)
        unique(config.profiles, "profile", casefold=True)
        unique(config.bindings, "binding")
        deployment_keys = [model.deployment_key for model in config.models]
        if len(deployment_keys) != len(set(deployment_keys)):
            raise ValueError("Duplicate model deployment keys are not allowed")

        valid_modes = {mode.value for mode in RoutingMode}
        valid_policies = {policy.value for policy in RoutingPolicy}
        valid_triggers = {trigger.value for trigger in FallbackTrigger}
        if config.settings.mode not in valid_modes:
            raise ValueError(f"Unknown orchestration mode: {config.settings.mode!r}")
        if config.settings.policy not in valid_policies:
            raise ValueError(f"Unknown routing policy: {config.settings.policy!r}")
        unknown_triggers = set(config.settings.fallback_triggers) - valid_triggers
        if unknown_triggers:
            raise ValueError("Unknown fallback triggers: " + ", ".join(sorted(unknown_triggers)))
        if not isinstance(config.settings.retries, int) or not 0 <= config.settings.retries <= 10:
            raise ValueError("Orchestration retries must be an integer between 0 and 10")
        if (
            not isinstance(config.settings.timeout_seconds, int | float)
            or not math.isfinite(float(config.settings.timeout_seconds))
            or not 0 < float(config.settings.timeout_seconds) <= 3600
        ):
            raise ValueError("Orchestration timeout_seconds must be between 0 and 3600")
        if (
            not isinstance(config.settings.deployment_cooldown_seconds, int | float)
            or not math.isfinite(float(config.settings.deployment_cooldown_seconds))
            or not 1 <= float(config.settings.deployment_cooldown_seconds) <= 3600
        ):
            raise ValueError("Orchestration deployment_cooldown_seconds must be between 1 and 3600")
        provider_specs = {spec.id for spec in self.provider_registry.specs()}
        provider_accounts = {account.id: account for account in config.providers}
        for account in config.providers:
            if account.provider not in provider_specs:
                raise ValueError(
                    f"Provider account {account.id!r} references unknown provider "
                    f"{account.provider!r}"
                )
            if not isinstance(account.enabled, bool):
                raise ValueError(f"Provider account {account.id!r} has an invalid enabled flag")
            sensitive_headers = {
                name
                for name in account.custom_headers
                if name.casefold()
                in {
                    "authorization",
                    "proxy-authorization",
                    "x-api-key",
                    "api-key",
                    "x-auth-token",
                }
            }
            if sensitive_headers:
                raise ValueError(
                    f"Provider account {account.id!r} stores sensitive custom headers; "
                    "put them in the encrypted credential payload under 'headers': "
                    + ", ".join(sorted(sensitive_headers))
                )
        for model in config.models:
            if model.account_id:
                model_account = provider_accounts.get(model.account_id)
                if model_account is None:
                    raise ValueError(
                        f"Model {model.deployment_key!r} references unknown account "
                        f"{model.account_id!r}"
                    )
                if model_account.provider != model.provider:
                    raise ValueError(
                        f"Model {model.deployment_key!r} does not match account provider "
                        f"{model_account.provider!r}"
                    )

        role_ids = {role.id.casefold() for role in config.roles}
        for profile in config.profiles:
            if profile.role.casefold() not in role_ids:
                raise ValueError(f"Profile {profile.id!r} references unknown role {profile.role!r}")
            if profile.max_cost_usd is not None and profile.max_cost_usd < 0:
                raise ValueError(f"Profile {profile.id!r} has an invalid max_cost_usd")
        configured_models = {model.deployment_key: model for model in config.models}
        configured_models.update(
            {
                model.key: model
                for model in config.models
                if sum(candidate.key == model.key for candidate in config.models) == 1
            }
        )
        for binding in config.bindings:
            if binding.role and binding.role.casefold() not in role_ids:
                raise ValueError(f"Binding {binding.id!r} references unknown role {binding.role!r}")
            if not isinstance(binding.selectors, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in binding.selectors.items()
            ):
                raise ValueError(f"Binding {binding.id!r} has invalid selectors")
            if not isinstance(binding.model, str) or not binding.model.strip():
                raise ValueError(f"Binding {binding.id!r} has no model assignment")
            if not isinstance(binding.fallback_chain, list) or any(
                not isinstance(model, str) or not model.strip() for model in binding.fallback_chain
            ):
                raise ValueError(f"Binding {binding.id!r} has an invalid fallback chain")
            if not isinstance(binding.equivalent_deployments, list) or any(
                not isinstance(model, str) or not model.strip()
                for model in binding.equivalent_deployments
            ):
                raise ValueError(f"Binding {binding.id!r} has invalid equivalent deployments")
            if not isinstance(binding.equivalent_deployment_weights, dict) or any(
                not isinstance(key, str)
                or not key.strip()
                or not isinstance(value, int | float)
                or isinstance(value, bool)
                or not math.isfinite(float(value))
                or float(value) < 0
                for key, value in binding.equivalent_deployment_weights.items()
            ):
                raise ValueError(
                    f"Binding {binding.id!r} has invalid equivalent deployment weights"
                )
            allowed_weighted_deployments = {binding.model, *binding.equivalent_deployments}
            if not set(binding.equivalent_deployment_weights).issubset(
                allowed_weighted_deployments
            ):
                raise ValueError(
                    f"Binding {binding.id!r} equivalent deployment weights must target the primary "
                    "or an explicit equivalent deployment"
                )
            primary_model = configured_models.get(binding.model)
            if primary_model is not None:
                for equivalent_key in binding.equivalent_deployments:
                    equivalent_model = configured_models.get(equivalent_key)
                    if equivalent_model is not None and equivalent_model.key != primary_model.key:
                        raise ValueError(
                            f"Binding {binding.id!r} equivalent deployment "
                            f"{equivalent_key!r} changes model identity"
                        )


def build_orchestration_service(
    *, data_dir: Path | str | None = None, config_paths: dict[str, Path | str] | None = None
) -> OrchestrationService:
    root = Path(
        data_dir or os.environ.get("CUTCTX_ORCHESTRATION_DIR", "~/.cutctx/orchestration")
    ).expanduser()
    resolved_paths: dict[str, Path | str]
    if config_paths is None:
        resolved_paths = dict(default_config_paths(root))
    else:
        resolved_paths = config_paths
    audit_key = os.environ.get("CUTCTX_ORCHESTRATION_AUDIT_KEY", "").strip()
    return OrchestrationService(
        config_store=LayeredConfigStore(resolved_paths),
        credential_store=EncryptedCredentialStore(root / "credentials.enc"),
        model_registry=DynamicModelRegistry(root / "models.json"),
        telemetry=ExecutionTelemetryStore(root / "executions.jsonl"),
        outcome_telemetry=OutcomeTelemetryStore(root / "outcomes.jsonl"),
        receipt_audit=(
            ReceiptAuditStore(root / "receipt-audit.jsonl", key=audit_key) if audit_key else None
        ),
        workflow_store=WorkflowStateStore(root / "workflows.json"),
    )

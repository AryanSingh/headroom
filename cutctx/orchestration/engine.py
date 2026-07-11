"""Deterministic capability-based role and selector routing."""

from __future__ import annotations

import uuid
from dataclasses import replace

from .models import (
    FallbackTrigger,
    ModelRecord,
    OrchestrationConfig,
    Role,
    RouteBinding,
    RoutingDecision,
    RoutingMode,
    RoutingPolicy,
    RoutingRequest,
)
from .registry import DynamicModelRegistry

SELECTOR_PRECEDENCE = {
    "agent": 800,
    "workflow": 700,
    "command": 600,
    "skill": 500,
    "task_type": 400,
    "repository": 300,
    "workspace": 200,
    "organization": 100,
}


class RoutingUnavailableError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        assigned_model: str | None = None,
        reason: str = "unavailable",
    ) -> None:
        super().__init__(message)
        self.assigned_model = assigned_model
        self.reason = reason


class DeterministicRoutingEngine:
    def __init__(
        self,
        config: OrchestrationConfig,
        registry: DynamicModelRegistry,
        *,
        require_configured_accounts: bool = False,
    ) -> None:
        self.config = config
        self.registry = registry
        self.require_configured_accounts = require_configured_accounts

    def route(
        self,
        request: RoutingRequest,
        *,
        allow_overrides: bool = False,
    ) -> RoutingDecision:
        configured_mode = self.config.settings.mode
        if allow_overrides:
            mode = request.mode or configured_mode
            policy = request.policy or self.config.settings.policy
        else:
            mode = (
                RoutingMode.STRICT.value
                if configured_mode == RoutingMode.STRICT.value
                or request.mode == RoutingMode.STRICT.value
                else configured_mode
            )
            policy = self.config.settings.policy
        request_id = request.request_id or uuid.uuid4().hex
        role = self._find_role(request.role)
        required = set(request.required_capabilities)
        if role is not None:
            required.update(role.required_capabilities)

        binding = self._select_binding(request)
        if binding is not None:
            required.update(binding.required_capabilities)
            primary = binding.model
            fallbacks = [*binding.fallback_chain, *self.config.settings.global_fallback_chain]
            reason = "deterministic_assignment"
        elif request.role:
            raise RoutingUnavailableError(
                f"Role {request.role!r} has no model assignment",
                reason="unassigned_role",
            )
        elif request.requested_model:
            primary = self._normalize_requested_model(
                request.requested_model, request.requested_provider
            )
            fallbacks = list(self.config.settings.global_fallback_chain)
            reason = "manual_model"
        else:
            raise RoutingUnavailableError("No role or model was requested", reason="missing_route")

        candidates = self._deduplicate(
            [primary] if mode == RoutingMode.STRICT.value else [primary, *fallbacks]
        )
        selected, rejected_reason = self._first_eligible(candidates, required)
        if selected is None:
            if mode == RoutingMode.STRICT.value:
                raise RoutingUnavailableError(
                    f"Assigned model {primary!r} cannot execute: {rejected_reason}",
                    assigned_model=primary,
                    reason=rejected_reason or "unavailable",
                )
            selected = self._policy_candidate(policy, required, excluded=set(candidates))
            if selected is None:
                raise RoutingUnavailableError(
                    "No configured model satisfies the request capabilities",
                    assigned_model=primary,
                    reason=rejected_reason or "unavailable",
                )
            candidates.append(selected.key)

        # ``primary`` may be an account-scoped deployment key
        # (``provider:account:model``), while ``ModelRecord.key`` intentionally
        # omits the account.  Compare deployment identities so a successful
        # exact-account assignment is not incorrectly reported as a fallback.
        fallback_used = selected.deployment_key != primary
        return RoutingDecision(
            request_id=request_id,
            role=role.id if role else request.role,
            assigned_model=primary,
            actual_model=selected.id,
            provider=selected.provider,
            account_id=selected.account_id,
            binding_id=binding.id if binding else None,
            mode=mode,
            policy=policy,
            reason=reason if not fallback_used else f"fallback:{rejected_reason or 'unavailable'}",
            fallback_used=fallback_used,
            fallback_trigger=(rejected_reason or FallbackTrigger.UNAVAILABLE.value)
            if fallback_used
            else None,
            fallback_from=primary if fallback_used else None,
            candidates=candidates,
            attempted_deployments=[selected.deployment_key],
            required_capabilities=required,
        )

    def fallback(self, decision: RoutingDecision, trigger: str) -> RoutingDecision:
        if decision.mode == RoutingMode.STRICT.value:
            raise RoutingUnavailableError(
                f"Strict mode refused fallback after {trigger}",
                assigned_model=decision.assigned_model,
                reason=trigger,
            )
        if trigger not in self.config.settings.fallback_triggers:
            raise RoutingUnavailableError(
                f"Fallback trigger {trigger!r} is disabled",
                assigned_model=decision.assigned_model,
                reason=trigger,
            )
        current_key = self._decision_deployment_key(decision)
        already_failed = {*decision.attempted_deployments, current_key}
        selected, reason = self._first_eligible(
            decision.candidates,
            decision.required_capabilities,
            excluded=already_failed,
        )
        if selected is None:
            configured_deployments = {
                model.deployment_key
                for key in decision.candidates
                if (model := self.registry.get(key)) is not None
            }
            selected = self._policy_candidate(
                decision.policy,
                decision.required_capabilities,
                excluded={*already_failed, *configured_deployments},
            )
        if selected is None:
            raise RoutingUnavailableError(
                f"No fallback is available after {trigger}",
                assigned_model=decision.assigned_model,
                reason=reason or trigger,
            )
        return replace(
            decision,
            actual_model=selected.id,
            provider=selected.provider,
            account_id=selected.account_id,
            reason=f"fallback:{trigger}",
            fallback_used=True,
            fallback_trigger=trigger,
            fallback_from=current_key,
            attempted_deployments=self._deduplicate(
                [*decision.attempted_deployments, current_key, selected.deployment_key]
            ),
        )

    @staticmethod
    def _decision_deployment_key(decision: RoutingDecision) -> str:
        if decision.account_id:
            return f"{decision.provider}:{decision.account_id}:{decision.actual_model}"
        return f"{decision.provider}:{decision.actual_model}"

    def _find_role(self, role: str | None) -> Role | None:
        if not role:
            return None
        normalized = role.casefold()
        for item in self.config.roles:
            if item.id.casefold() == normalized or item.name.casefold() == normalized:
                return item
        return None

    def _select_binding(self, request: RoutingRequest) -> RouteBinding | None:
        role = self._find_role(request.role)
        role_ids = {
            value.casefold() for value in (request.role, role.id if role else None) if value
        }
        candidates: list[tuple[int, int, str, RouteBinding]] = []
        for binding in self.config.bindings:
            if not binding.enabled:
                continue
            if binding.role and binding.role.casefold() not in role_ids:
                continue
            if any(request.selectors.get(key) != value for key, value in binding.selectors.items()):
                continue
            selector_score = sum(SELECTOR_PRECEDENCE.get(key, 1) for key in binding.selectors)
            candidates.append((len(binding.selectors), selector_score, binding.id, binding))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return candidates[0][3]

    def _normalize_requested_model(self, model: str, provider: str | None) -> str:
        if ":" in model:
            return model
        if provider:
            return f"{provider}:{model}"
        record = self.registry.get(model)
        if record is None:
            return model
        return record.key

    def _first_eligible(
        self,
        candidates: list[str],
        required: set[str],
        *,
        excluded: set[str] | None = None,
    ) -> tuple[ModelRecord | None, str | None]:
        last_reason: str | None = None
        excluded_deployments = excluded or set()
        for key in candidates:
            model = self.registry.get(key)
            if model is None:
                last_reason = "model_not_registered"
                continue
            if model.deployment_key in excluded_deployments:
                continue
            if model.deprecated:
                last_reason = FallbackTrigger.MODEL_DEPRECATED.value
                continue
            if not model.available:
                last_reason = FallbackTrigger.UNAVAILABLE.value
                continue
            if self.require_configured_accounts and not self._has_enabled_account(model):
                last_reason = FallbackTrigger.AUTH_FAILURE.value
                continue
            if not model.supports(required):
                last_reason = FallbackTrigger.UNSUPPORTED_CAPABILITIES.value
                continue
            return model, None
        return None, last_reason

    def _has_enabled_account(self, model: ModelRecord) -> bool:
        return any(
            account.enabled
            and account.provider == model.provider
            and (model.account_id is None or account.id == model.account_id)
            for account in self.config.providers
        )

    def _policy_candidate(
        self, policy: str, required: set[str], *, excluded: set[str]
    ) -> ModelRecord | None:
        if policy in {RoutingPolicy.ROLE_LOCKED.value, RoutingPolicy.MANUAL.value}:
            return None
        models = [
            model
            for model in self.registry.list(required_capabilities=required, available_only=True)
            if model.deployment_key not in excluded
            and not model.deprecated
            and (not self.require_configured_accounts or self._has_enabled_account(model))
        ]
        if not models:
            return None
        if policy == RoutingPolicy.FASTEST.value:
            return min(
                models,
                key=lambda model: (model.latency_ms is None, model.latency_ms or 0, model.key),
            )
        if policy == RoutingPolicy.CHEAPEST.value:
            return min(
                models,
                key=lambda model: (
                    model.input_cost_per_million is None,
                    model.input_cost_per_million or 0,
                    model.key,
                ),
            )
        if policy == RoutingPolicy.HIGHEST_QUALITY.value:
            return max(models, key=lambda model: (model.reliability or 0, model.key))
        return min(
            models,
            key=lambda model: (
                -float(model.reliability or 0),
                float(model.latency_ms or 1_000_000),
                float(model.input_cost_per_million or 1_000_000),
                model.key,
            ),
        )

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if value and value not in result:
                result.append(value)
        return result

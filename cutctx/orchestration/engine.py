"""Deterministic capability-based role and selector routing."""

from __future__ import annotations

import hashlib
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
        decision_trace: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.assigned_model = assigned_model
        self.reason = reason
        self.decision_trace = decision_trace


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
        self._validate_request_constraints(request)
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
            equivalents = list(binding.equivalent_deployments)
            equivalent_weights = dict(binding.equivalent_deployment_weights)
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
            equivalents = []
            equivalent_weights = {}
            reason = "manual_model"
        else:
            raise RoutingUnavailableError("No role or model was requested", reason="missing_route")

        equivalent_candidates = self._validated_equivalents(primary, equivalents)
        candidates = self._deduplicate(
            [primary, *equivalent_candidates]
            if mode == RoutingMode.STRICT.value
            else [primary, *equivalent_candidates, *fallbacks]
        )
        selected, rejected_reason, selection_evidence = self._select_primary_or_equivalent(
            primary,
            equivalent_candidates,
            required,
            request,
            equivalent_weights=equivalent_weights,
        )
        if selected is None and mode != RoutingMode.STRICT.value:
            selected, rejected_reason = self._first_eligible(fallbacks, required, request=request)
        if selected is None:
            if mode == RoutingMode.STRICT.value:
                raise RoutingUnavailableError(
                    f"Assigned model {primary!r} cannot execute: {rejected_reason}",
                    assigned_model=primary,
                    reason=rejected_reason or "unavailable",
                )
            selected = self._policy_candidate(
                policy, required, excluded=set(candidates), request=request
            )
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
        equivalent_deployment_keys = {
            model.deployment_key
            for key in equivalent_candidates
            if (model := self.registry.get(key)) is not None
        }
        fallback_used = (
            selected.deployment_key != primary
            and selected.deployment_key not in equivalent_deployment_keys
        )
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
            reason=(
                "equivalent_deployment_selected"
                if selected.deployment_key != primary and not fallback_used
                else reason
                if not fallback_used
                else f"fallback:{rejected_reason or 'unavailable'}"
            ),
            fallback_used=fallback_used,
            fallback_trigger=(rejected_reason or FallbackTrigger.UNAVAILABLE.value)
            if fallback_used
            else None,
            fallback_from=primary if fallback_used else None,
            candidates=candidates,
            attempted_deployments=[selected.deployment_key],
            required_capabilities=required,
            policy_constraints=self._policy_constraints(request),
            selection_evidence=selection_evidence,
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
        request = self._request_from_policy_constraints(decision.policy_constraints)
        selected, reason = self._first_eligible(
            decision.candidates,
            decision.required_capabilities,
            excluded=already_failed,
            request=request,
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
                request=request,
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
        request: RoutingRequest | None = None,
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
            if self.registry.cooldown_remaining_seconds(model.deployment_key) is not None:
                last_reason = "cooling_down"
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
            constraint_reason = self._constraint_rejection_reason(model, request)
            if constraint_reason is not None:
                last_reason = constraint_reason
                continue
            return model, None
        return None, last_reason

    @staticmethod
    def _validate_request_constraints(request: RoutingRequest) -> None:
        if request.max_cost_usd is not None:
            if request.max_cost_usd < 0:
                raise ValueError("max_cost_usd must be non-negative")
            if request.estimated_input_tokens is None or request.estimated_output_tokens is None:
                raise ValueError(
                    "max_cost_usd requires estimated_input_tokens and estimated_output_tokens"
                )
        for value, name in (
            (request.estimated_input_tokens, "estimated_input_tokens"),
            (request.estimated_output_tokens, "estimated_output_tokens"),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")

    @staticmethod
    def _policy_constraints(request: RoutingRequest) -> dict[str, object]:
        """Return the stable, serializable policy portion of a decision receipt."""
        return {
            "allowed_providers": sorted(value.lower() for value in request.allowed_providers),
            "allowed_regions": sorted(value.lower() for value in request.allowed_regions),
            "allowed_data_classifications": sorted(
                value.lower() for value in request.allowed_data_classifications
            ),
            "data_classification": request.data_classification,
            "estimated_input_tokens": request.estimated_input_tokens,
            "estimated_output_tokens": request.estimated_output_tokens,
            "max_cost_usd": request.max_cost_usd,
            "policy_version": request.policy_version,
        }

    @staticmethod
    def _request_from_policy_constraints(values: dict[str, object]) -> RoutingRequest:
        """Recreate constraints for retry/fallback without trusting mutable caller state."""
        return RoutingRequest(
            allowed_providers={str(value) for value in values.get("allowed_providers", [])},
            allowed_regions={str(value) for value in values.get("allowed_regions", [])},
            allowed_data_classifications={
                str(value) for value in values.get("allowed_data_classifications", [])
            },
            data_classification=(
                str(values["data_classification"])
                if values.get("data_classification") is not None
                else None
            ),
            estimated_input_tokens=(
                int(values["estimated_input_tokens"])
                if values.get("estimated_input_tokens") is not None
                else None
            ),
            estimated_output_tokens=(
                int(values["estimated_output_tokens"])
                if values.get("estimated_output_tokens") is not None
                else None
            ),
            max_cost_usd=(
                float(values["max_cost_usd"]) if values.get("max_cost_usd") is not None else None
            ),
            policy_version=str(values.get("policy_version", "1")),
        )

    @staticmethod
    def _constraint_rejection_reason(
        model: ModelRecord, request: RoutingRequest | None
    ) -> str | None:
        if request is None:
            return None
        if request.allowed_providers and model.provider.lower() not in {
            value.lower() for value in request.allowed_providers
        }:
            return "provider_not_allowed"
        metadata = model.metadata if isinstance(model.metadata, dict) else {}
        if request.allowed_regions:
            region = str(metadata.get("region", "")).lower()
            if region not in {value.lower() for value in request.allowed_regions}:
                return "residency_mismatch"
        if request.data_classification:
            if request.allowed_data_classifications and request.data_classification.lower() not in {
                value.lower() for value in request.allowed_data_classifications
            }:
                return "data_classification_not_allowed"
            supported = metadata.get("data_classifications", [])
            supported_values = (
                {str(value).lower() for value in supported}
                if isinstance(supported, list)
                else set()
            )
            if request.data_classification.lower() not in supported_values:
                return "data_classification_not_allowed"
        if request.max_cost_usd is not None:
            if model.input_cost_per_million is None or model.output_cost_per_million is None:
                return "cost_unknown"
            estimated_cost = (
                (request.estimated_input_tokens or 0) * model.input_cost_per_million
                + (request.estimated_output_tokens or 0) * model.output_cost_per_million
            ) / 1_000_000
            if estimated_cost > request.max_cost_usd:
                return "budget_exceeded"
        return None

    def _validated_equivalents(self, primary: str, equivalents: list[str]) -> list[str]:
        primary_model = self.registry.get(primary)
        if primary_model is None:
            return []
        return [
            key
            for key in equivalents
            if (candidate := self.registry.get(key)) is not None
            and candidate.key == primary_model.key
            and candidate.deployment_key != primary_model.deployment_key
        ]

    def _select_primary_or_equivalent(
        self,
        primary: str,
        equivalents: list[str],
        required: set[str],
        request: RoutingRequest,
        *,
        equivalent_weights: dict[str, float],
    ) -> tuple[ModelRecord | None, str | None, dict[str, object]]:
        keys = self._deduplicate([primary, *equivalents])
        eligible: list[ModelRecord] = []
        rejected: list[dict[str, str]] = []
        last_reason: str | None = None
        for key in keys:
            model, reason = self._first_eligible([key], required, request=request)
            if model is None:
                last_reason = reason
                rejected.append({"model": key, "reason": reason or "unavailable"})
            else:
                eligible.append(model)
        if not eligible:
            return None, last_reason, {"strategy": "equivalent_reliability", "rejected": rejected}
        weighted = [
            (model, float(equivalent_weights.get(model.deployment_key, 0)))
            for model in eligible
            if float(equivalent_weights.get(model.deployment_key, 0)) > 0
        ]
        if weighted:
            total_weight = sum(weight for _, weight in weighted)
            cohort_fraction = self._cohort_fraction(request.request_id)
            threshold = cohort_fraction * total_weight
            cumulative = 0.0
            selected = weighted[-1][0]
            for model, weight in weighted:
                cumulative += weight
                if threshold < cumulative:
                    selected = model
                    break
            return (
                selected,
                None,
                {
                    "strategy": "equivalent_weighted",
                    "selected": selected.deployment_key,
                    "cohort_fraction": cohort_fraction,
                    "eligible_weights": [
                        {"deployment": model.deployment_key, "weight": weight}
                        for model, weight in weighted
                    ],
                    "rejected": rejected,
                },
            )
        primary_model = self.registry.get(primary)
        scored = [
            (self._reliability_score(model, is_primary=model is primary_model), model)
            for model in eligible
        ]
        scored.sort(key=lambda item: (float(item[0]["score"]), item[1].deployment_key))
        _score, selected = scored[-1]
        return (
            selected,
            None,
            {
                "strategy": "equivalent_reliability",
                "selected": selected.deployment_key,
                "scores": [
                    {"deployment": model.deployment_key, **components}
                    for components, model in reversed(scored)
                ],
                "rejected": rejected,
            },
        )

    @staticmethod
    def _cohort_fraction(request_id: str) -> float:
        digest = hashlib.sha256(request_id.encode("utf-8")).digest()
        return int.from_bytes(digest, "big") / (1 << (8 * len(digest)))

    @staticmethod
    def _reliability_score(
        model: ModelRecord,
        *,
        is_primary: bool,
    ) -> dict[str, float]:
        metadata = model.metadata if isinstance(model.metadata, dict) else {}
        reliability_default = model.reliability if model.reliability is not None else 1.0
        health = DeterministicRoutingEngine._bounded_runtime_signal(
            metadata.get("health_score", reliability_default), 1.0
        )
        rate_headroom = DeterministicRoutingEngine._bounded_runtime_signal(
            metadata.get("rate_limit_headroom", 1.0), 1.0
        )
        budget_headroom = DeterministicRoutingEngine._bounded_runtime_signal(
            metadata.get("budget_headroom", 1.0), 1.0
        )
        latency_value = (
            model.latency_ms if model.latency_ms is not None else metadata.get("latency_ms", 1000.0)
        )
        latency = max(
            DeterministicRoutingEngine._finite_runtime_signal(latency_value, 1000.0),
            0.0,
        )
        latency_score = 1.0 / (1.0 + latency / 1000.0)
        total = (
            health * 0.4
            + rate_headroom * 0.25
            + budget_headroom * 0.2
            + latency_score * 0.15
            + (1e-9 if is_primary else 0.0)
        )
        return {
            "score": total,
            "health": health,
            "rate_limit_headroom": rate_headroom,
            "budget_headroom": budget_headroom,
            "latency_score": latency_score,
        }

    @staticmethod
    def _finite_runtime_signal(value: object, default: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        if parsed != parsed or parsed in {float("inf"), float("-inf")}:
            return default
        return parsed

    @staticmethod
    def _bounded_runtime_signal(value: object, default: float) -> float:
        return min(
            max(DeterministicRoutingEngine._finite_runtime_signal(value, default), 0.0),
            1.0,
        )

    def _has_enabled_account(self, model: ModelRecord) -> bool:
        return any(
            account.enabled
            and account.provider == model.provider
            and (model.account_id is None or account.id == model.account_id)
            for account in self.config.providers
        )

    def _policy_candidate(
        self,
        policy: str,
        required: set[str],
        *,
        excluded: set[str],
        request: RoutingRequest | None = None,
    ) -> ModelRecord | None:
        if policy in {RoutingPolicy.ROLE_LOCKED.value, RoutingPolicy.MANUAL.value}:
            return None
        models = [
            model
            for model in self.registry.list(required_capabilities=required, available_only=True)
            if model.deployment_key not in excluded
            and not model.deprecated
            and (not self.require_configured_accounts or self._has_enabled_account(model))
            and self._constraint_rejection_reason(model, request) is None
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

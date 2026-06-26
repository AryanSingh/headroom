# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Config-driven cost-based model router.

Blocker-5 part 2 (production-audit-progress-2026-06-20.md):
the audit found that the 5-source savings model was wired
at the data layer but not at the request path. The
``model_routing`` source was structurally zero because
no code actually routed a request to a cheaper model.

This module adds a minimum viable router that:
  1. Reads a config map from cutctx.toml (or env var)
     declaring source-model -> target-model downgrades,
     e.g. opus-4 -> sonnet-4, gpt-4o -> gpt-4o-mini.
  2. At request time, asks the policy: "is this request
     downgradeable?" via a workload classifier (simple
     heuristics — tool complexity, cache-read share, etc.).
  3. If yes, returns the target model name. The handler
     that calls this method then overrides the upstream
     call's `model` field with the target.
  4. The savings (tokens + USD) are computed by comparing
     the requested-model cost to the actual-model cost at
     LiteLLM's published rates.
  5. The savings flow into RequestOutcome.model_routing_*
     fields so the existing funnel attributes them
     correctly.

The router is OFF by default (an empty config map
means no routing happens). Operators opt in by adding
a ``[model_routing]`` block to cutctx.toml:

  [model_routing]
  enabled = true
  downgrade_when = "low_cache_read"  # or "always"
  routes = [
    {source = "claude-opus-4-5", target = "claude-sonnet-4-5"},
    {source = "gpt-4o", target = "gpt-4o-mini"},
  ]
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("cutctx.proxy.model_router")


@dataclass
class ModelRoute:
    """A single source -> target downgrade mapping."""

    source: str
    target: str
    # Optional per-route cost-delta override (USD per million
    # tokens). If unset, the router looks up the LiteLLM cost
    # for source and target. If both lookups fail, the route
    # is treated as zero-savings and skipped.
    source_cost_per_mtok: float | None = None
    target_cost_per_mtok: float | None = None


@dataclass
class ModelRouterConfig:
    """Operator config for the model router.

    The default config is empty (no routing). Operators
    populate ``routes`` to opt in.
    """

    enabled: bool = False
    downgrade_when: str = "low_cache_read"
    routes: list[ModelRoute] = field(default_factory=list)
    # Workload-classifier thresholds. A request is
    # "downgradeable" when (cache_read_tokens /
    # attempted_input_tokens) < cache_read_threshold
    # AND (tool_calls / num_messages) < tool_complexity_threshold.
    cache_read_threshold: float = 0.5
    tool_complexity_threshold: float = 2.0

    @classmethod
    def from_env(cls) -> ModelRouterConfig:
        """Build a config from the CUTCTX_MODEL_ROUTING env
        var. The env var is a JSON string. Empty / unset =>
        empty config.
        """
        raw = os.environ.get("CUTCTX_MODEL_ROUTING", "").strip()
        if not raw:
            return cls()
        import json as _json

        try:
            payload = _json.loads(raw)
        except _json.JSONDecodeError as exc:
            logger.warning("CUTCTX_MODEL_ROUTING is not valid JSON: %s", exc)
            return cls()
        routes = [
            ModelRoute(
                source=r["source"],
                target=r["target"],
                source_cost_per_mtok=r.get("source_cost_per_mtok"),
                target_cost_per_mtok=r.get("target_cost_per_mtok"),
            )
            for r in payload.get("routes", [])
            if "source" in r and "target" in r
        ]
        return cls(
            enabled=bool(payload.get("enabled", False)),
            downgrade_when=str(payload.get("downgrade_when", "low_cache_read")),
            routes=routes,
            cache_read_threshold=float(
                payload.get("cache_read_threshold", 0.5)
            ),
            tool_complexity_threshold=float(
                payload.get("tool_complexity_threshold", 2.0)
            ),
        )


@dataclass
class RoutingDecision:
    """The output of ``ModelRouter.maybe_route``.

    ``target_model`` is None when no downgrade is applied
    (the request is routed as-is). When set, the caller
    should override the upstream call's ``model`` field
    with the target.
    """

    target_model: str | None = None
    source_model: str = ""
    routing_applied: bool = False
    tokens_saved: int = 0
    usd_saved: float = 0.0
    reason: str = "no_route"


class ModelRouter:
    """Cost-based model router.

    Constructed with a config; ``maybe_route`` is the
    request-time entry point.
    """

    def __init__(self, config: ModelRouterConfig | None = None) -> None:
        self.config = config or ModelRouterConfig.from_env()

    def maybe_route(
        self,
        requested_model: str,
        *,
        cache_read_tokens: int = 0,
        attempted_input_tokens: int = 0,
        tool_calls: int = 0,
        num_messages: int = 0,
    ) -> RoutingDecision:
        """Decide whether to downgrade this request to a cheaper
        model.

        Returns a ``RoutingDecision`` whose ``target_model`` is
        either None (no downgrade) or a string (the target
        model name). The caller is responsible for actually
        overriding the upstream call.
        """
        if not self.config.enabled:
            return RoutingDecision(
                source_model=requested_model,
                reason="router_disabled",
            )
        # Find a route for the requested model.
        route = self._find_route(requested_model)
        if route is None:
            return RoutingDecision(
                source_model=requested_model,
                reason="no_route_for_model",
            )
        # Workload classifier.
        if not self._is_downgradeable(
            cache_read_tokens=cache_read_tokens,
            attempted_input_tokens=attempted_input_tokens,
            tool_calls=tool_calls,
            num_messages=num_messages,
        ):
            return RoutingDecision(
                source_model=requested_model,
                reason="workload_not_downgradeable",
            )
        # Compute the savings. Both costs are USD per million
        # input tokens (LiteLLM convention).
        src_cost = route.source_cost_per_mtok
        tgt_cost = route.target_cost_per_mtok
        if src_cost is None or tgt_cost is None:
            src_cost, tgt_cost = self._lookup_costs(
                route.source, route.target
            )
        if src_cost is None or tgt_cost is None or src_cost <= tgt_cost:
            # Could not compute a positive savings. Skip.
            return RoutingDecision(
                source_model=requested_model,
                reason="cost_lookup_failed",
            )
        # The caller computes the actual token savings in a follow-up
        # step once the request has completed.
        return RoutingDecision(
            target_model=route.target,
            source_model=route.source,
            routing_applied=True,
            tokens_saved=0,  # filled by caller after the request
            usd_saved=0.0,  # filled by caller after the request
            reason="downgrade_applied",
        )

    def finalize_savings(
        self,
        decision: RoutingDecision,
        *,
        input_tokens: int,
    ) -> RoutingDecision:
        """After the request completes, compute the actual
        token + USD savings from the decision's per-mtok delta.
        The caller updates the decision with the real values.
        """
        if not decision.routing_applied or decision.target_model is None:
            return decision
        # Find the route again to get the per-mtok delta.
        route = self._find_route(decision.source_model)
        if route is None:
            return decision
        src_cost = route.source_cost_per_mtok
        tgt_cost = route.target_cost_per_mtok
        if src_cost is None or tgt_cost is None:
            src_cost, tgt_cost = self._lookup_costs(
                route.source, route.target
            )
        if src_cost is None or tgt_cost is None:
            return decision
        per_mtok_delta = src_cost - tgt_cost
        usd_saved = input_tokens * per_mtok_delta / 1_000_000.0
        return RoutingDecision(
            target_model=decision.target_model,
            source_model=decision.source_model,
            routing_applied=decision.routing_applied,
            tokens_saved=input_tokens,
            usd_saved=usd_saved,
            reason=decision.reason,
        )

    def _find_route(self, model: str) -> ModelRoute | None:
        for r in self.config.routes:
            if r.source == model:
                return r
        return None

    def _is_downgradeable(
        self,
        *,
        cache_read_tokens: int,
        attempted_input_tokens: int,
        tool_calls: int,
        num_messages: int,
    ) -> bool:
        if self.config.downgrade_when == "always":
            return True
        if self.config.downgrade_when == "low_cache_read":
            if attempted_input_tokens <= 0:
                return True  # no data; default to downgradeable
            cache_share = cache_read_tokens / max(attempted_input_tokens, 1)
            if cache_share > self.config.cache_read_threshold:
                return False
        if self.config.downgrade_when == "low_complexity":
            if num_messages <= 0:
                return True
            tool_ratio = tool_calls / max(num_messages, 1)
            if tool_ratio > self.config.tool_complexity_threshold:
                return False
        return True

    def _lookup_costs(
        self, source: str, target: str
    ) -> tuple[float | None, float | None]:
        """Look up LiteLLM-published input costs (USD per
        million tokens). Returns (None, None) if either
        model is unknown to LiteLLM.
        """
        try:
            import litellm as _litellm

            src_info = _litellm.model_cost.get(source, {})
            tgt_info = _litellm.model_cost.get(target, {})
            src_cost = src_info.get("input_cost_per_token")
            tgt_cost = tgt_info.get("input_cost_per_token")
            # LiteLLM stores cost per token, we store per
            # million tokens.
            return (
                float(src_cost) * 1_000_000.0 if src_cost else None,
                float(tgt_cost) * 1_000_000.0 if tgt_cost else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("LiteLLM cost lookup failed: %s", exc)
            return (None, None)


def prepare_model_routing(
    handler: Any,
    requested_model: str,
    *,
    request_savings_metadata: dict[str, dict[str, Any]] | None = None,
    cache_read_tokens: int = 0,
    attempted_input_tokens: int = 0,
    tool_calls: int = 0,
    num_messages: int = 0,
) -> tuple[str, dict[str, dict[str, Any]] | None]:
    """Apply an enabled router and attach placeholder routing metadata."""

    router = getattr(handler, "_model_router", None)
    if router is None:
        return requested_model, request_savings_metadata

    try:
        decision = router.maybe_route(
            requested_model,
            cache_read_tokens=cache_read_tokens,
            attempted_input_tokens=attempted_input_tokens,
            tool_calls=tool_calls,
            num_messages=num_messages,
        )
    except Exception:  # noqa: BLE001
        return requested_model, request_savings_metadata

    if not decision.routing_applied or not decision.target_model:
        return requested_model, request_savings_metadata

    updated_metadata = dict(request_savings_metadata or {})
    updated_metadata["model_routing"] = {
        "source_model": decision.source_model or requested_model,
        "target_model": decision.target_model,
        "reason": decision.reason,
        "tokens_saved": 0,
        "usd_saved": 0.0,
    }
    return decision.target_model, updated_metadata


__all__ = [
    "ModelRouter",
    "ModelRouterConfig",
    "ModelRoute",
    "RoutingDecision",
    "prepare_model_routing",
]

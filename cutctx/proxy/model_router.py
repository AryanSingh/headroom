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
import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

logger = logging.getLogger("cutctx.proxy.model_router")


class TaskComplexity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


def classify_task_complexity(messages: list[dict[str, Any]]) -> TaskComplexity:
    """Classify a turn conservatively before selecting a cheaper model.

    This is an eligibility gate, not an intent model: uncertainty must retain
    the requested model.  In particular, code, tool context, reference-
    dependent requests, and genuinely complex follow-ups stay on the stronger
    model. A short, plainly easy follow-up is still allowed to downgrade even
    when the thread already has prior turns.
    """
    if not messages:
        return TaskComplexity.HIGH

    last_user_message = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if not last_user_message:
        return TaskComplexity.HIGH

    raw_content = last_user_message.get("content", "")
    if not isinstance(raw_content, str):
        # Multimodal content and structured content need the requested model's
        # capability contract; do not turn their representation into a string.
        return TaskComplexity.HIGH
    content = raw_content
    normalized_content = content.strip().lower()

    if not normalized_content:
        return TaskComplexity.HIGH

    if any(
        marker in normalized_content
        for marker in (
            "```",
            "<tool",
            "function ",
            "traceback",
            "stack trace",
            "diff --git",
            "begin patch",
        )
    ):
        return TaskComplexity.HIGH

    if normalized_content in {
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "ok",
        "okay",
    }:
        return TaskComplexity.LOW

    # Regex heuristic for low complexity
    low_complexity_patterns = [
        r"fix\s*(?:the)?\s*typo",
        r"add\s*(?:a)?\s*docstring",
        r"add\s*(?:type)?\s*hints?",
        r"fix\s*lint(?:ing)?",
        r"rename\s*(?:the)?\s*variable",
        r"format\s*(?:the)?\s*code",
        r"\bsummar(?:y|ize|ise)\b",
        r"\bexplain\b",
        r"\bwhat\s+is\b",
        r"\bhow\s+do\s+i\b",
        r"\bwhere\s+is\b",
        r"\blist\b",
        r"\bshow\b",
        r"\bgive\s+me\b",
    ]

    high_complexity_patterns = [
        r"\bbuild\b",
        r"\bimplement\b",
        r"\bdebug\b",
        r"\brefactor\b",
        r"\barchitecture\b",
        r"\bmigration\b",
        r"\bwire\b",
        r"\bfix\s+(?:bug|issue|failure|error|crash|broken|routing)\b",
        r"\bcomplete\s+work\b",
        r"\btest\s+.*\bend\s*to\s*end\b",
        r"\b(?:review|audit|investigate|analy[sz]e|design|plan|compare|optimi[sz]e|security)\b",
        r"\b(?:continue|complete|finish)\b",
        r"\bfix\s+(?:this|that|it)\b",
        r"\bfix\s+(?:the\s+)?(?:first|second|selected|found)\b",
        r"\b(?:commit|push|merge|deploy|release|ship|publish|migrate)\b",
        r"\b(?:run|execute)\s+(?:the\s+)?(?:tests?|suite|benchmark|migration|deploy)\b",
        r"\b(?:production|security|authentication|authorization|billing|payment)\b",
        r"\b(?:multiple|all)\s+(?:files?|modules?|services?|packages?)\b",
    ]
    reference_dependent_patterns = [
        r"\b(?:this|that|these|those|it)\b\s*[.?!]*$",
        r"\b(?:first|second|third|former|latter)\b",
        r"\b(?:above|earlier|previous|prior)\b",
    ]

    # If the text is short AND matches a low complexity pattern
    if len(content) < 500:
        for pattern in high_complexity_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return TaskComplexity.HIGH
        for pattern in reference_dependent_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return TaskComplexity.MEDIUM

        contextual_followup_patterns = [
            r"\b(?:summar(?:y|ize|ise)|explain|rewrite|paraphrase|translate|compare|describe|outline|analy[sz]e)\b",
        ]
        contextual_reference_patterns = [
            r"\bthat\b",
            r"\bthose\b",
            r"\bthese\b",
            r"\bfollowing\b",
            r"\bprevious\b",
            r"\bearlier\b",
            r"\babove\b",
        ]
        if any(
            re.search(pattern, normalized_content, re.IGNORECASE)
            for pattern in contextual_followup_patterns
        ) and any(
            re.search(pattern, normalized_content, re.IGNORECASE)
            for pattern in contextual_reference_patterns
        ):
            return TaskComplexity.MEDIUM

        for pattern in low_complexity_patterns:
            if re.search(pattern, content, re.IGNORECASE) and len(normalized_content.split()) <= 16:
                return TaskComplexity.LOW

        # Short, single-turn informational prompts are good candidates for
        # mini routing; multi-sentence or code/task-heavy asks stay medium.
        if (
            len(content) < 180
            and len(normalized_content.split()) <= 24
            and "\n" not in content
            and normalized_content.count(".") <= 1
        ):
            return TaskComplexity.LOW

    if len(content) > 5000:
        return TaskComplexity.HIGH

    return TaskComplexity.MEDIUM


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
    medium_target: str | None = None
    medium_target_cost_per_mtok: float | None = None


@dataclass
class ModelRouterConfig:
    """Operator config for the model router.

    The default config is empty (no routing). Operators
    populate ``routes`` to opt in.
    """

    enabled: bool = False
    downgrade_when: str = "low_cache_read"
    routes: list[ModelRoute] = field(
        default_factory=lambda: [
            ModelRoute(
                source="claude-3-5-sonnet-20241022",
                target="claude-3-5-haiku-20241022",
            ),
            ModelRoute(
                source="claude-3-5-sonnet-latest",
                target="claude-3-5-haiku-latest",
            ),
            ModelRoute(
                source="gpt-4o",
                target="gpt-4o-mini",
            ),
            ModelRoute(
                source="gpt-4o-2024-08-06",
                target="gpt-4o-mini",
            ),
        ]
    )
    # Workload-classifier thresholds. A request is
    # "downgradeable" when (cache_read_tokens /
    # attempted_input_tokens) < cache_read_threshold
    # AND (tool_calls / num_messages) < tool_complexity_threshold.
    cache_read_threshold: float = 0.5
    tool_complexity_threshold: float = 2.0
    # Targets explicitly verified for account-scoped subscription transports.
    # Generic routes leave this empty and retain the requested model.
    transport_safe_targets: set[str] = field(default_factory=set)

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
            import logging

            logging.getLogger(__name__).warning("CUTCTX_MODEL_ROUTING is not valid JSON: %s", exc)
            return cls()
        routes = [
            ModelRoute(
                source=r["source"],
                target=r["target"],
                source_cost_per_mtok=r.get("source_cost_per_mtok"),
                target_cost_per_mtok=r.get("target_cost_per_mtok"),
                medium_target=r.get("medium_target"),
                medium_target_cost_per_mtok=r.get("medium_target_cost_per_mtok"),
            )
            for r in payload.get("routes", [])
            if "source" in r and "target" in r
        ]
        return cls(
            enabled=bool(payload.get("enabled", False)),
            downgrade_when=str(payload.get("downgrade_when", "low_cache_read")),
            routes=routes,
            cache_read_threshold=float(payload.get("cache_read_threshold", 0.5)),
            tool_complexity_threshold=float(payload.get("tool_complexity_threshold", 2.0)),
            transport_safe_targets=set(payload.get("transport_safe_targets", [])),
        )

    @classmethod
    def economy_preset(cls) -> ModelRouterConfig:
        """Aggressive downgrade: routes any eligible request to the
        cheapest capable model. Opt-in only — changes response quality
        tradeoffs.

        Adds more source→target pairs beyond the default four, and sets
        lower thresholds so more requests qualify for downgrade.
        """
        return cls(
            enabled=True,
            downgrade_when="always",
            routes=[
                ModelRoute(
                    source="claude-opus-4-5",
                    target="claude-sonnet-4-5",
                ),
                ModelRoute(
                    source="claude-opus-4-5-20250514",
                    target="claude-sonnet-4-5",
                ),
                ModelRoute(
                    source="claude-sonnet-4-5",
                    target="claude-haiku-4-5",
                ),
                ModelRoute(
                    source="claude-sonnet-4-5-20250514",
                    target="claude-haiku-4-5",
                ),
                ModelRoute(
                    source="claude-3-5-sonnet-20241022",
                    target="claude-3-5-haiku-20241022",
                ),
                ModelRoute(
                    source="claude-3-5-sonnet-latest",
                    target="claude-3-5-haiku-latest",
                ),
                ModelRoute(
                    source="gpt-4o",
                    target="gpt-4o-mini",
                ),
                ModelRoute(
                    source="gpt-4o-2024-08-06",
                    target="gpt-4o-mini",
                ),
                ModelRoute(
                    source="gpt-4o-mini",
                    target="gpt-4o-mini",  # already cheapest — identity route
                ),
                ModelRoute(
                    source="gemini-2.5-pro",
                    target="gemini-2.5-flash",
                ),
            ],
            cache_read_threshold=0.8,  # route even when cache-read share is high
            tool_complexity_threshold=5.0,  # route even moderately complex requests
        )

    @classmethod
    def codex_gpt54mini_high_preset(cls) -> ModelRouterConfig:
        """Keep GPT-5-tier models as the requested surface for serious work,
        but opportunistically route lightweight Codex turns to GPT-5.4 mini
        with high reasoning effort.

        This preset is intentionally conservative: it only activates on
        ``low_complexity`` text prompts so complex coding/review tasks stay on
        the original heavy model. It is also fully opt-in to avoid silently
        changing behavior for existing deployments.
        """

        return cls(
            enabled=True,
            downgrade_when="low_complexity",
            routes=[
                ModelRoute(
                    source="claude-opus-4-5",
                    target="claude-sonnet-4-5",
                    source_cost_per_mtok=15.0,
                    target_cost_per_mtok=3.0,
                ),
                ModelRoute(
                    source="claude-opus-4-5-20250514",
                    target="claude-sonnet-4-5",
                    source_cost_per_mtok=15.0,
                    target_cost_per_mtok=3.0,
                ),
                ModelRoute(
                    source="claude-sonnet-4-5",
                    target="claude-haiku-4-5",
                    source_cost_per_mtok=3.0,
                    target_cost_per_mtok=0.8,
                ),
                ModelRoute(
                    source="claude-sonnet-4-5-20250514",
                    target="claude-haiku-4-5",
                    source_cost_per_mtok=3.0,
                    target_cost_per_mtok=0.8,
                ),
                ModelRoute(
                    source="gpt-5.5",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=10.0,
                    target_cost_per_mtok=1.0,
                    medium_target="gpt-5.6-luna",
                    medium_target_cost_per_mtok=5.0,
                ),
                ModelRoute(
                    source="gpt-5.6-terra",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=10.0,
                    target_cost_per_mtok=1.0,
                    medium_target="gpt-5.6-luna",
                    medium_target_cost_per_mtok=5.0,
                ),
                ModelRoute(
                    source="gpt-5.6-sol",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=10.0,
                    target_cost_per_mtok=1.0,
                    medium_target="gpt-5.6-luna",
                    medium_target_cost_per_mtok=5.0,
                ),
                ModelRoute(
                    source="gpt-5.6-luna",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=5.0,
                    target_cost_per_mtok=1.0,
                ),
                ModelRoute(
                    source="gpt-5.4",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=5.0,
                    target_cost_per_mtok=1.0,
                ),
                ModelRoute(
                    source="gpt-5",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=5.0,
                    target_cost_per_mtok=1.0,
                ),
            ],
            cache_read_threshold=0.5,
            tool_complexity_threshold=2.0,
            transport_safe_targets={"gpt-5.4-mini", "gpt-5.6-luna"},
        )

    @classmethod
    def codex_opencode_slim_preset(cls) -> ModelRouterConfig:
        """Backward-compatible alias for the newer GPT-5.4-mini preset."""

        return cls.codex_gpt54mini_high_preset()

    @classmethod
    def subrequest_haiku_preset(cls) -> ModelRouterConfig:
        """Routes internal subrequests (tool-loop helpers, summarization calls)
        to Haiku-tier models. Direct downgrade to Haiku, skipping intermediate
        steps. Opt-in only — applies only to requests marked internally as
        subrequests.

        Adds routes that map all capable models directly to their Haiku
        equivalents, and sets high thresholds so all internal requests route.
        """
        return cls(
            enabled=True,
            downgrade_when="always",
            routes=[
                ModelRoute(
                    source="claude-opus-4-5",
                    target="claude-haiku-4-5",
                ),
                ModelRoute(
                    source="claude-opus-4-5-20250514",
                    target="claude-haiku-4-5",
                ),
                ModelRoute(
                    source="claude-sonnet-4-5",
                    target="claude-haiku-4-5",
                ),
                ModelRoute(
                    source="claude-sonnet-4-5-20250514",
                    target="claude-haiku-4-5",
                ),
                ModelRoute(
                    source="claude-3-5-sonnet-20241022",
                    target="claude-3-5-haiku-20241022",
                ),
                ModelRoute(
                    source="claude-3-5-sonnet-latest",
                    target="claude-3-5-haiku-latest",
                ),
                ModelRoute(
                    source="claude-haiku-4-5",
                    target="claude-haiku-4-5",  # already Haiku — identity route
                ),
                ModelRoute(
                    source="claude-3-5-haiku-20241022",
                    target="claude-3-5-haiku-20241022",  # already Haiku — identity route
                ),
                ModelRoute(
                    source="claude-3-5-haiku-latest",
                    target="claude-3-5-haiku-latest",  # already Haiku — identity route
                ),
                ModelRoute(
                    source="gpt-4o",
                    target="gpt-4o-mini",
                ),
                ModelRoute(
                    source="gpt-4o-2024-08-06",
                    target="gpt-4o-mini",
                ),
                ModelRoute(
                    source="gpt-4o-mini",
                    target="gpt-4o-mini",  # already cheapest — identity route
                ),
                ModelRoute(
                    source="gemini-2.5-pro",
                    target="gemini-2.5-flash",
                ),
            ],
            cache_read_threshold=0.8,  # route even when cache-read share is high
            tool_complexity_threshold=5.0,  # route even moderately complex requests
        )

    @classmethod
    def from_preset_name(cls, preset: str | None) -> ModelRouterConfig | None:
        """Return a named preset config, or ``None`` when no preset is set.

        ``None`` / empty / ``default`` preserve the historical behavior where
        routing only activates when the operator provides explicit JSON routes.
        We also accept older preset aliases so existing local setups keep
        working while the product-facing name tracks the actual behavior.
        """

        normalized = (preset or "").strip().lower()
        if normalized in {"", "default", "none"}:
            return None
        if normalized == "economy":
            return cls.economy_preset()
        if normalized == "subrequest-haiku":
            return cls.subrequest_haiku_preset()
        if normalized in {
            "codex-gpt54mini-high",
            "codex-opencode-slim",
            "oh-my-opencode-slim",
        }:
            return cls.codex_gpt54mini_high_preset()
        return None


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
    request_overrides: dict[str, Any] | None = None


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
        task_complexity: TaskComplexity | None = None,
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
        target_model = route.target
        target_cost_override = route.target_cost_per_mtok
        if task_complexity == TaskComplexity.MEDIUM:
            if not route.medium_target:
                return RoutingDecision(
                    source_model=requested_model,
                    reason="workload_not_downgradeable",
                )
            target_model = route.medium_target
            target_cost_override = route.medium_target_cost_per_mtok

        # Compute the savings. Both costs are USD per million
        # input tokens (LiteLLM convention).
        src_cost = route.source_cost_per_mtok
        tgt_cost = target_cost_override
        if src_cost is None or tgt_cost is None:
            src_cost, tgt_cost = self._lookup_costs(route.source, target_model)
        if src_cost is None or tgt_cost is None or src_cost <= tgt_cost:
            # Could not compute a positive savings. Skip.
            return RoutingDecision(
                source_model=requested_model,
                reason="cost_lookup_failed",
            )
        # The caller computes the actual token savings in a follow-up
        # step once the request has completed.
        return RoutingDecision(
            target_model=target_model,
            source_model=route.source,
            routing_applied=True,
            tokens_saved=0,  # filled by caller after the request
            usd_saved=0.0,  # filled by caller after the request
            reason="downgrade_applied",
            request_overrides=self._request_overrides_for_target(target_model),
        )

    def _request_overrides_for_target(self, target_model: str) -> dict[str, Any] | None:
        if target_model == "gpt-5.4-mini":
            return {"reasoning": {"effort": "high"}}
        return None

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
        if decision.target_model == route.medium_target:
            tgt_cost = route.medium_target_cost_per_mtok
        else:
            tgt_cost = route.target_cost_per_mtok
        if src_cost is None or tgt_cost is None:
            src_cost, tgt_cost = self._lookup_costs(route.source, decision.target_model)
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

    def is_text_downgradeable(self, messages: list[dict[str, Any]]) -> bool:
        """Check if the text content of the messages is simple enough to downgrade."""
        if self.config.downgrade_when != "low_complexity":
            return True
        complexity = classify_task_complexity(messages)
        return complexity != TaskComplexity.HIGH

    def _lookup_costs(self, source: str, target: str) -> tuple[float | None, float | None]:
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
    messages: list[dict[str, Any]] | None = None,
    request_id: str = "",
    client: str | None = None,
    assignment_identity_source: str = "caller",
    assignment_sticky: bool = True,
    transport_provider: str | None = None,
    implicit_downgrade_allowed: bool = True,
) -> tuple[str, dict[str, dict[str, Any]] | None]:
    """Apply an enabled router and attach placeholder routing metadata."""

    updated_metadata = dict(request_savings_metadata or {})
    routing_context = updated_metadata.pop("__orchestration__", {})
    role_alias = ""
    if requested_model.lower().startswith("role:"):
        role_alias = requested_model.split(":", 1)[1].strip()
    role = str(routing_context.get("role") or role_alias).strip()
    orchestration = getattr(handler, "_orchestration_service", None)
    if orchestration is not None and role:
        from cutctx.orchestration import RoutingRequest, RoutingUnavailableError

        orchestration_decision = orchestration.route(
            RoutingRequest(
                role=role,
                required_capabilities=set(routing_context.get("required_capabilities", [])),
                selectors={
                    str(key): str(value)
                    for key, value in routing_context.get("selectors", {}).items()
                },
                mode=routing_context.get("mode"),
                policy=routing_context.get("policy"),
                request_id=request_id,
            )
        )
        if transport_provider and orchestration_decision.provider != transport_provider:
            raise RoutingUnavailableError(
                "The assigned provider cannot be executed through this compatibility endpoint; "
                "use a canonical executor configured for the assigned provider",
                assigned_model=orchestration_decision.assigned_model,
                reason="transport_mismatch",
            )
        transport_account_id = getattr(handler, "_orchestration_account_id", None)
        if (
            orchestration_decision.account_id
            and orchestration_decision.account_id != transport_account_id
        ):
            raise RoutingUnavailableError(
                "The assigned provider account cannot be proven through this compatibility "
                "endpoint; configure the endpoint for the exact account",
                assigned_model=orchestration_decision.assigned_model,
                reason="account_transport_mismatch",
            )
        target_model = orchestration_decision.actual_model
        updated_metadata["model_routing"] = {
            "source_model": requested_model,
            "target_model": target_model,
            "assigned_model": orchestration_decision.assigned_model,
            "provider": orchestration_decision.provider,
            "role": orchestration_decision.role,
            "binding_id": orchestration_decision.binding_id,
            "reason": orchestration_decision.reason,
            "fallback_used": orchestration_decision.fallback_used,
            "fallback_trigger": orchestration_decision.fallback_trigger,
            "tokens_saved": 0,
            "usd_saved": 0.0,
        }
        # Role bindings prove provider/account transport compatibility above,
        # but not wire-mode compatibility (e.g. Codex Responses Lite). When
        # the caller can't prove the assigned model supports this transport,
        # keep the requested model and only surface the would-be assignment
        # for observability.
        if not implicit_downgrade_allowed and target_model != requested_model:
            updated_metadata["model_routing"]["target_model"] = requested_model
            updated_metadata["model_routing"]["reason"] = "downgrade_blocked_unproven_transport"
            return requested_model, updated_metadata
        if target_model == "gpt-5.4-mini":
            updated_metadata["model_routing"]["request_overrides"] = {
                "reasoning": {"effort": "high"}
            }
        return target_model, updated_metadata
    canary_model_routing = False
    try:
        from cutctx.proxy.savings_canary import (
            CanaryStateError,
            get_savings_canary_coordinator,
        )

        assignment = get_savings_canary_coordinator().assign(
            request_id,
            client=client,
            model=requested_model,
            identity_source=assignment_identity_source,
            sticky=assignment_sticky,
        )
        if assignment.enabled:
            updated_metadata["savings_canary"] = assignment.to_dict()
            if assignment.eligible and assignment.arm != "model_routing":
                return requested_model, updated_metadata
            canary_model_routing = assignment.eligible and assignment.arm == "model_routing"
    except CanaryStateError:
        raise
    except Exception:  # noqa: BLE001
        pass

    router = getattr(handler, "_model_router", None)
    if canary_model_routing and (
        router is None or not getattr(getattr(router, "config", None), "enabled", False)
    ):
        # A model-routing canary must exercise the named treatment even when
        # broad model routing is disabled. The preset still keeps complex work
        # on the requested model and routes only low-complexity GPT tasks.
        router = ModelRouter(config=ModelRouterConfig.codex_gpt54mini_high_preset())
    if router is None:
        return requested_model, updated_metadata or request_savings_metadata

    try:
        task_complexity = classify_task_complexity(messages) if messages else None
        # If text downgrade check fails, abort routing
        if messages and hasattr(router, "is_text_downgradeable"):
            if not router.is_text_downgradeable(messages):
                return requested_model, updated_metadata or request_savings_metadata

        decision = router.maybe_route(
            requested_model,
            cache_read_tokens=cache_read_tokens,
            attempted_input_tokens=attempted_input_tokens,
            tool_calls=tool_calls,
            num_messages=num_messages,
            task_complexity=task_complexity,
        )
    except Exception:  # noqa: BLE001
        return requested_model, updated_metadata or request_savings_metadata

    if not decision.routing_applied or not decision.target_model:
        return requested_model, updated_metadata or request_savings_metadata

    if not implicit_downgrade_allowed:
        safe_targets = set(getattr(router.config, "transport_safe_targets", set()))
        if decision.target_model not in safe_targets:
            return requested_model, updated_metadata or request_savings_metadata

    updated_metadata["model_routing"] = {
        "source_model": decision.source_model or requested_model,
        "target_model": decision.target_model,
        "reason": decision.reason,
        "tokens_saved": 0,
        "usd_saved": 0.0,
    }
    if decision.request_overrides:
        updated_metadata["model_routing"]["request_overrides"] = decision.request_overrides
    return decision.target_model, updated_metadata


__all__ = [
    "ModelRouter",
    "ModelRouterConfig",
    "ModelRoute",
    "RoutingDecision",
    "prepare_model_routing",
]

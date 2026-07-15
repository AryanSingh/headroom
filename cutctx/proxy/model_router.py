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
from typing import Any, Literal, Protocol

logger = logging.getLogger("cutctx.proxy.model_router")

ModelRoutingMode = Literal["off", "balanced", "aggressive", "custom"]
MODEL_ROUTING_SCORER_ARTIFACT_ENV = "CUTCTX_MODEL_ROUTING_SCORER_ARTIFACT"

_BALANCED_PRESET_NAMES = {
    "codex-gpt54mini-high",
    "codex-opencode-slim",
    "oh-my-opencode-slim",
}
_AGGRESSIVE_PRESET_NAMES = {"economy"}
_OFF_MODE_NAMES = {"", "off", "disabled", "false", "0", "none"}


def normalize_model_routing_mode(mode: str | None) -> str:
    """Normalize a routing mode or preset string to a dashboard mode."""
    normalized = (mode or "").strip().lower()
    if normalized in _OFF_MODE_NAMES:
        return "off"
    if normalized in {"balanced", "default"} | _BALANCED_PRESET_NAMES:
        return "balanced"
    if normalized in {"aggressive"} | _AGGRESSIVE_PRESET_NAMES:
        return "aggressive"
    return "custom"


def model_routing_preset_for_mode(
    mode: str | None,
    *,
    current_preset: str | None = None,
) -> str | None:
    """Map a dashboard mode back to the preset string to persist."""
    normalized = normalize_model_routing_mode(mode)
    if normalized == "off":
        return current_preset
    if normalized == "balanced":
        return "codex-gpt54mini-high"
    if normalized == "aggressive":
        return "economy"
    return current_preset


def model_routing_mode_for_state(
    *,
    enabled: bool,
    preset: str | None,
    route_count: int | None = None,
) -> str:
    """Infer the effective routing mode from runtime state."""
    if not enabled:
        return "off"
    normalized_preset = (preset or "").strip().lower()
    if normalized_preset in _BALANCED_PRESET_NAMES:
        return "balanced"
    if normalized_preset in _AGGRESSIVE_PRESET_NAMES:
        return "aggressive"
    if normalized_preset in _OFF_MODE_NAMES:
        return "custom" if route_count and route_count > 0 else "off"
    if route_count and route_count > 0:
        return "custom"
    return "balanced"


class TaskComplexity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass(frozen=True)
class TaskComplexityAssessment:
    """An explainable complexity score used before a model downgrade.

    ``confidence`` is confidence in the tier assignment, not predicted answer
    quality.  A custom scorer can use embeddings or a trained model later,
    while the default stays deterministic and dependency-free.
    """

    complexity: TaskComplexity
    confidence: float
    source: str = "heuristic"
    signals: tuple[str, ...] = ()


def _recent_context_window(
    messages: list[dict[str, Any]], *, size: int = 8
) -> list[dict[str, Any]]:
    """Return the context most likely to affect the current turn.

    Old tool results should not permanently pin a long-running agent session to
    the strongest model.  A bounded recent window keeps current tool loops safe
    while allowing a later, self-contained question to use a smaller model.
    """

    return messages[-size:]


_TOOL_CONTEXT_TYPES = {
    "function",
    "function_call",
    "tool_call",
    "tool_result",
    "tool_use",
}


def _contains_tool_context(value: Any) -> bool:
    """Return whether a provider-native value represents tool activity."""
    if isinstance(value, dict):
        if value.get("role") == "tool":
            return True
        item_type = value.get("type")
        if isinstance(item_type, str) and (
            item_type in _TOOL_CONTEXT_TYPES
            or item_type.endswith("_call")
            or item_type.endswith("_call_output")
        ):
            return True
        if value.get("tool_calls"):
            return True
        if value.get("function_call"):
            return True
        return any(_contains_tool_context(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_tool_context(item) for item in value)
    return False


class TaskComplexityScorer(Protocol):
    """Pluggable scorer contract for model-routing eligibility."""

    def assess(self, messages: list[dict[str, Any]]) -> TaskComplexityAssessment: ...


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

    recent_messages = _recent_context_window(messages)
    if any(_contains_tool_context(message) for message in recent_messages):
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
        r"\b(?:race|deadlock|concurren(?:cy|t)|distributed|multi[- ]tenant|consistency)\b",
        r"\b(?:database|schema|sql|transaction|rollback|data loss|destructive)\b",
        r"\b(?:credential|secret|permission|privacy|pii|compliance|legal|medical)\b",
        r"\b(?:performance|latency|throughput|memory leak|profil(?:e|ing)|benchmark)\b",
        r"\b(?:delete|drop|remove|rotate|revoke)\b.*\b(?:production|database|table|bucket|account|key|secret)\b",
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

        # Multiple requested actions are a better difficulty signal than raw
        # prompt length.  Keep compound execution work on the requested model.
        action_verbs = re.findall(
            r"\b(?:find|inspect|analy[sz]e|design|plan|implement|fix|test|verify|commit|push|deploy|publish|migrate|refactor|optimi[sz]e|review|audit)\b",
            normalized_content,
        )
        if len(set(action_verbs)) >= 2:
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


def assess_task_complexity(messages: list[dict[str, Any]]) -> TaskComplexityAssessment:
    """Return the deterministic tier together with its routing confidence.

    The legacy classifier remains the source of truth for the tier so this is
    safe to introduce without changing existing presets.  Confidence lets an
    operator opt into abstention for borderline classifications and gives a
    future trained scorer one small, stable interface to replace.
    """

    complexity = classify_task_complexity(messages)
    recent_messages = _recent_context_window(messages)
    has_recent_tool_context = any(_contains_tool_context(message) for message in recent_messages)
    if complexity == TaskComplexity.HIGH:
        signals = ("recent_tool_context",) if has_recent_tool_context else ("strong_model_gate",)
        return TaskComplexityAssessment(complexity, 1.0, signals=signals)

    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
    content = last_user.get("content", "")
    if not isinstance(content, str):
        return TaskComplexityAssessment(
            TaskComplexity.HIGH, 1.0, signals=("structured_or_multimodal_content",)
        )
    normalized = content.strip().lower()

    if complexity == TaskComplexity.MEDIUM:
        return TaskComplexityAssessment(complexity, 0.85, signals=("context_dependent",))
    if normalized in {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay"}:
        return TaskComplexityAssessment(complexity, 1.0, signals=("trivial_conversation",))
    explicit_low_signals = (
        "typo",
        "docstring",
        "type hint",
        "lint",
        "rename",
        "format",
        "summar",
        "explain",
        "what is",
        "how do i",
        "where is",
        "list",
        "show",
        "give me",
    )
    confidence = 0.9 if any(signal in normalized for signal in explicit_low_signals) else 0.75
    signal = "explicit_low_complexity" if confidence >= 0.9 else "short_self_contained"
    return TaskComplexityAssessment(complexity, confidence, signals=(signal,))


class HeuristicTaskComplexityScorer:
    """Dependency-free default scorer used by existing deployments."""

    def assess(self, messages: list[dict[str, Any]]) -> TaskComplexityAssessment:
        return assess_task_complexity(messages)


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
    # Confidence below this value abstains from an automatic downgrade.  The
    # default preserves current routing behavior; operators can raise it while
    # calibrating a custom or trained scorer.
    minimum_confidence: float = 0.0
    require_calibrated_scorer: bool = False
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
            minimum_confidence=float(payload.get("minimum_confidence", 0.0)),
            require_calibrated_scorer=bool(payload.get("require_calibrated_scorer", False)),
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
                    source="claude-sonnet-5",
                    target="claude-haiku-5-20260101",
                    source_cost_per_mtok=3.0,
                    target_cost_per_mtok=0.8,
                ),
                ModelRoute(
                    source="claude-sonnet-5-20260101",
                    target="claude-haiku-5-20260101",
                    source_cost_per_mtok=3.0,
                    target_cost_per_mtok=0.8,
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
                    source="gpt-5.6-terra",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=10.0,
                    target_cost_per_mtok=1.0,
                ),
                ModelRoute(
                    source="gpt-5.6-sol",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=10.0,
                    target_cost_per_mtok=1.0,
                ),
                ModelRoute(
                    source="gpt-5.6-luna",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=5.0,
                    target_cost_per_mtok=1.0,
                ),
                ModelRoute(
                    source="gpt-5.5",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=10.0,
                    target_cost_per_mtok=1.0,
                ),
                ModelRoute(
                    source="gpt-5.4",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=5.0,
                    target_cost_per_mtok=1.0,
                ),
                ModelRoute(
                    source="gpt-5.3",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=5.0,
                    target_cost_per_mtok=1.0,
                ),
                ModelRoute(
                    source="gpt-5.2",
                    target="gpt-5.4-mini",
                    source_cost_per_mtok=5.0,
                    target_cost_per_mtok=1.0,
                ),
                ModelRoute(
                    source="gpt-5.1",
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
                ModelRoute(
                    source="gemini-2.5-pro",
                    target="gemini-2.5-flash",
                ),
            ],
            cache_read_threshold=0.8,  # route even when cache-read share is high
            tool_complexity_threshold=5.0,  # route even moderately complex requests
            transport_safe_targets={"gpt-5.4-mini"},
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
    def claude_three_tier_eval_preset(cls) -> ModelRouterConfig:
        """Evidence-gated Claude Opus→Sonnet→Haiku routing graph."""

        return cls(
            enabled=True,
            downgrade_when="low_complexity",
            require_calibrated_scorer=True,
            routes=[
                ModelRoute(
                    source="claude-opus-4-5",
                    target="claude-haiku-4-5",
                    medium_target="claude-sonnet-4-5",
                    source_cost_per_mtok=15.0,
                    target_cost_per_mtok=0.8,
                    medium_target_cost_per_mtok=3.0,
                ),
                ModelRoute(
                    source="claude-opus-4-5-20250514",
                    target="claude-haiku-4-5",
                    medium_target="claude-sonnet-4-5",
                    source_cost_per_mtok=15.0,
                    target_cost_per_mtok=0.8,
                    medium_target_cost_per_mtok=3.0,
                ),
                ModelRoute(
                    source="claude-sonnet-4-5",
                    target="claude-haiku-4-5",
                    source_cost_per_mtok=3.0,
                    target_cost_per_mtok=0.8,
                ),
            ],
        )

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
        if normalized == "claude-three-tier-eval":
            return cls.claude_three_tier_eval_preset()
        return None

    @classmethod
    def from_mode_name(
        cls,
        mode: str | None,
        *,
        current_preset: str | None = None,
    ) -> ModelRouterConfig | None:
        preset = model_routing_preset_for_mode(mode, current_preset=current_preset)
        if preset is None:
            return None
        return cls.from_preset_name(preset)


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
    confidence: float | None = None
    scorer: str | None = None
    signals: tuple[str, ...] = ()


class ModelRouter:
    """Cost-based model router.

    Constructed with a config; ``maybe_route`` is the
    request-time entry point.
    """

    def __init__(
        self,
        config: ModelRouterConfig | None = None,
        *,
        scorer: TaskComplexityScorer | None = None,
    ) -> None:
        self.config = config or ModelRouterConfig.from_env()
        self.scorer = scorer or self._configured_scorer()
        artifact = getattr(self.scorer, "artifact", None)
        artifact_threshold = float(getattr(artifact, "minimum_confidence", 0.0) or 0.0)
        self.minimum_confidence = max(self.config.minimum_confidence, artifact_threshold)

    @staticmethod
    def _configured_scorer() -> TaskComplexityScorer:
        artifact_path = os.environ.get(MODEL_ROUTING_SCORER_ARTIFACT_ENV, "").strip()
        if not artifact_path:
            return HeuristicTaskComplexityScorer()
        try:
            from cutctx.proxy.model_routing_training import (
                LinearCalibratedTaskComplexityScorer,
                LinearRoutingArtifact,
            )

            artifact = LinearRoutingArtifact.load(artifact_path)
            return LinearCalibratedTaskComplexityScorer(
                artifact,
                source=f"linear-calibrated:{artifact_path}",
            )
        except Exception as exc:  # noqa: BLE001 - fail closed to deterministic scorer
            logger.warning(
                "Failed to load model-routing scorer artifact %r: %s", artifact_path, exc
            )
            return HeuristicTaskComplexityScorer()

    def maybe_route(
        self,
        requested_model: str,
        *,
        cache_read_tokens: int = 0,
        attempted_input_tokens: int = 0,
        tool_calls: int = 0,
        num_messages: int = 0,
        task_complexity: TaskComplexity | None = None,
        task_assessment: TaskComplexityAssessment | None = None,
        client: str | None = None,
    ) -> RoutingDecision:
        """Decide whether to downgrade this request to a cheaper
        model.

        Returns a ``RoutingDecision`` whose ``target_model`` is
        either None (no downgrade) or a string (the target
        model name). The caller is responsible for actually
        overriding the upstream call.
        """
        assessment = task_assessment
        if assessment is not None:
            task_complexity = assessment.complexity
        if not self.config.enabled:
            return RoutingDecision(
                source_model=requested_model,
                reason="router_disabled",
            )
        if self.config.require_calibrated_scorer and getattr(self.scorer, "artifact", None) is None:
            return RoutingDecision(
                source_model=requested_model,
                reason="calibrated_scorer_required",
            )
        # Find a route for the requested model.
        route = self._find_route(requested_model)
        if route is None:
            return RoutingDecision(
                source_model=requested_model,
                reason="no_route_for_model",
            )
        if assessment is not None and assessment.complexity == TaskComplexity.HIGH:
            return RoutingDecision(
                source_model=requested_model,
                reason="workload_not_downgradeable",
                confidence=assessment.confidence,
                scorer=assessment.source,
                signals=assessment.signals,
            )
        # Workload classifier.
        if not self._is_downgradeable(
            cache_read_tokens=cache_read_tokens,
            attempted_input_tokens=attempted_input_tokens,
            tool_calls=tool_calls,
            num_messages=num_messages,
        ):
            if task_complexity in {TaskComplexity.LOW, TaskComplexity.MEDIUM}:
                pass
            else:
                return RoutingDecision(
                    source_model=requested_model,
                    reason="workload_not_downgradeable",
                    confidence=assessment.confidence if assessment else None,
                    scorer=assessment.source if assessment else None,
                    signals=assessment.signals if assessment else (),
                )
        target_model = route.target
        target_cost_override = route.target_cost_per_mtok
        if task_complexity == TaskComplexity.MEDIUM:
            if not route.medium_target:
                return RoutingDecision(
                    source_model=requested_model,
                    reason="workload_not_downgradeable",
                    confidence=assessment.confidence if assessment else None,
                    scorer=assessment.source if assessment else None,
                    signals=assessment.signals if assessment else (),
                )
            target_model = route.medium_target
            target_cost_override = route.medium_target_cost_per_mtok
        minimum_confidence = self._minimum_confidence_for(
            client=client,
            source_model=requested_model,
            target_model=target_model,
        )
        if assessment is not None and assessment.confidence < minimum_confidence:
            return RoutingDecision(
                source_model=requested_model,
                reason="confidence_below_threshold",
                confidence=assessment.confidence,
                scorer=assessment.source,
                signals=assessment.signals,
            )

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
                confidence=assessment.confidence if assessment else None,
                scorer=assessment.source if assessment else None,
                signals=assessment.signals if assessment else (),
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
            confidence=assessment.confidence if assessment else None,
            scorer=assessment.source if assessment else None,
            signals=assessment.signals if assessment else (),
        )

    def _request_overrides_for_target(self, target_model: str) -> dict[str, Any] | None:
        if target_model == "gpt-5.4-mini":
            return {"reasoning": {"effort": "high"}}
        return None

    def _minimum_confidence_for(
        self,
        *,
        client: str | None,
        source_model: str,
        target_model: str,
    ) -> float:
        artifact = getattr(self.scorer, "artifact", None)
        thresholds = getattr(artifact, "segment_thresholds", {})
        if not isinstance(thresholds, dict):
            return self.minimum_confidence
        model_pair = f"{source_model}->{target_model}"
        pair_threshold = (thresholds.get("model_pair") or {}).get(model_pair)
        normalized_client = (client or "").strip().lower()
        client_threshold = (thresholds.get("client") or {}).get(normalized_client)
        for value in (pair_threshold, client_threshold):
            if value is not None:
                return max(self.config.minimum_confidence, float(value))
        return self.minimum_confidence

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
            confidence=decision.confidence,
            scorer=decision.scorer,
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
                return False  # no data; fail closed on ambiguous turns
            cache_share = cache_read_tokens / max(attempted_input_tokens, 1)
            if cache_share > self.config.cache_read_threshold:
                return False
        if self.config.downgrade_when == "low_complexity":
            if num_messages <= 0:
                return False
            tool_ratio = tool_calls / max(num_messages, 1)
            if tool_ratio > self.config.tool_complexity_threshold:
                return False
        return True

    def is_text_downgradeable(self, messages: list[dict[str, Any]]) -> bool:
        """Check if the text content of the messages is simple enough to downgrade."""
        if self.config.downgrade_when != "low_complexity":
            return True
        if not messages:
            return False
        assessment = self.scorer.assess(messages)
        return (
            assessment.complexity != TaskComplexity.HIGH
            and assessment.confidence >= self.minimum_confidence
        )

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

    from cutctx.proxy.model_routing_trace import (
        ModelRoutingDecisionTrace,
        attach_model_routing_trace,
    )

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
        transport_account_id = getattr(handler, "_orchestration_account_id", None)
        transport_state = {
            "provider": transport_provider,
            "provider_proven": not transport_provider
            or orchestration_decision.provider == transport_provider,
            "account_id": transport_account_id,
            "account_proven": not orchestration_decision.account_id
            or orchestration_decision.account_id == transport_account_id,
            "implicit_downgrade_allowed": implicit_downgrade_allowed,
        }
        if transport_provider and orchestration_decision.provider != transport_provider:
            trace = ModelRoutingDecisionTrace(
                request_id=request_id,
                mechanism="deterministic_orchestration",
                requested_model=requested_model,
                effective_model=requested_model,
                assigned_model=orchestration_decision.assigned_model,
                provider=orchestration_decision.provider,
                account_id=orchestration_decision.account_id,
                role=orchestration_decision.role,
                binding_id=orchestration_decision.binding_id,
                policy=orchestration_decision.policy,
                mode=orchestration_decision.mode,
                reason="transport_mismatch",
                applied=False,
                candidates=list(orchestration_decision.candidates),
                rejected_candidates=[
                    {"model": orchestration_decision.actual_model, "reason": "transport_mismatch"}
                ],
                required_capabilities=sorted(orchestration_decision.required_capabilities),
                fallback_used=orchestration_decision.fallback_used,
                fallback_trigger=orchestration_decision.fallback_trigger,
                fallback_from=orchestration_decision.fallback_from,
                attempted_deployments=list(orchestration_decision.attempted_deployments),
                transport=transport_state,
                selection_evidence=dict(getattr(orchestration_decision, "selection_evidence", {})),
            )
            raise RoutingUnavailableError(
                "The assigned provider cannot be executed through this compatibility endpoint; "
                "use a canonical executor configured for the assigned provider",
                assigned_model=orchestration_decision.assigned_model,
                reason="transport_mismatch",
                decision_trace=trace.to_dict(),
            )
        if (
            orchestration_decision.account_id
            and orchestration_decision.account_id != transport_account_id
        ):
            trace = ModelRoutingDecisionTrace(
                request_id=request_id,
                mechanism="deterministic_orchestration",
                requested_model=requested_model,
                effective_model=requested_model,
                assigned_model=orchestration_decision.assigned_model,
                provider=orchestration_decision.provider,
                account_id=orchestration_decision.account_id,
                role=orchestration_decision.role,
                binding_id=orchestration_decision.binding_id,
                policy=orchestration_decision.policy,
                mode=orchestration_decision.mode,
                reason="account_transport_mismatch",
                applied=False,
                candidates=list(orchestration_decision.candidates),
                rejected_candidates=[
                    {
                        "model": orchestration_decision.actual_model,
                        "reason": "account_transport_mismatch",
                    }
                ],
                required_capabilities=sorted(orchestration_decision.required_capabilities),
                fallback_used=orchestration_decision.fallback_used,
                fallback_trigger=orchestration_decision.fallback_trigger,
                fallback_from=orchestration_decision.fallback_from,
                attempted_deployments=list(orchestration_decision.attempted_deployments),
                transport=transport_state,
                selection_evidence=dict(getattr(orchestration_decision, "selection_evidence", {})),
            )
            raise RoutingUnavailableError(
                "The assigned provider account cannot be proven through this compatibility "
                "endpoint; configure the endpoint for the exact account",
                assigned_model=orchestration_decision.assigned_model,
                reason="account_transport_mismatch",
                decision_trace=trace.to_dict(),
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
            attach_model_routing_trace(
                updated_metadata,
                ModelRoutingDecisionTrace(
                    request_id=request_id,
                    mechanism="deterministic_orchestration",
                    requested_model=requested_model,
                    effective_model=requested_model,
                    assigned_model=orchestration_decision.assigned_model,
                    provider=orchestration_decision.provider,
                    account_id=orchestration_decision.account_id,
                    role=orchestration_decision.role,
                    binding_id=orchestration_decision.binding_id,
                    policy=orchestration_decision.policy,
                    mode=orchestration_decision.mode,
                    reason="downgrade_blocked_unproven_transport",
                    applied=False,
                    candidates=list(orchestration_decision.candidates),
                    rejected_candidates=[{"model": target_model, "reason": "unproven_wire_mode"}],
                    required_capabilities=sorted(orchestration_decision.required_capabilities),
                    fallback_used=orchestration_decision.fallback_used,
                    fallback_trigger=orchestration_decision.fallback_trigger,
                    fallback_from=orchestration_decision.fallback_from,
                    attempted_deployments=list(orchestration_decision.attempted_deployments),
                    transport=transport_state,
                    selection_evidence=dict(
                        getattr(orchestration_decision, "selection_evidence", {})
                    ),
                ),
            )
            return requested_model, updated_metadata
        if target_model == "gpt-5.4-mini":
            updated_metadata["model_routing"]["request_overrides"] = {
                "reasoning": {"effort": "high"}
            }
        attach_model_routing_trace(
            updated_metadata,
            ModelRoutingDecisionTrace(
                request_id=request_id,
                mechanism="deterministic_orchestration",
                requested_model=requested_model,
                effective_model=target_model,
                assigned_model=orchestration_decision.assigned_model,
                provider=orchestration_decision.provider,
                account_id=orchestration_decision.account_id,
                role=orchestration_decision.role,
                binding_id=orchestration_decision.binding_id,
                policy=orchestration_decision.policy,
                mode=orchestration_decision.mode,
                reason=orchestration_decision.reason,
                applied=target_model != requested_model,
                candidates=list(orchestration_decision.candidates),
                required_capabilities=sorted(orchestration_decision.required_capabilities),
                fallback_used=orchestration_decision.fallback_used,
                fallback_trigger=orchestration_decision.fallback_trigger,
                fallback_from=orchestration_decision.fallback_from,
                attempted_deployments=list(orchestration_decision.attempted_deployments),
                transport=transport_state,
                selection_evidence=dict(getattr(orchestration_decision, "selection_evidence", {})),
            ),
        )
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
        task_assessment = router.scorer.assess(messages) if messages else None
        task_complexity = task_assessment.complexity if task_assessment else None
        decision = router.maybe_route(
            requested_model,
            cache_read_tokens=cache_read_tokens,
            attempted_input_tokens=attempted_input_tokens,
            tool_calls=tool_calls,
            num_messages=num_messages,
            task_complexity=task_complexity,
            task_assessment=task_assessment,
            client=client,
        )
    except Exception as exc:  # noqa: BLE001
        attach_model_routing_trace(
            updated_metadata,
            ModelRoutingDecisionTrace(
                request_id=request_id,
                mechanism="optimization_preset",
                requested_model=requested_model,
                effective_model=requested_model,
                reason="router_error",
                applied=False,
                rejected_candidates=[{"model": requested_model, "reason": type(exc).__name__}],
                transport={
                    "provider": transport_provider,
                    "implicit_downgrade_allowed": implicit_downgrade_allowed,
                },
            ),
        )
        return requested_model, updated_metadata

    if not decision.routing_applied or not decision.target_model:
        # Keep externally supplied routing savings intact.  A retained local
        # decision adds observability fields but must not erase savings already
        # attributed by an upstream gateway or harness.
        routing_metadata = updated_metadata.get("model_routing")
        if not isinstance(routing_metadata, dict):
            routing_metadata = {}
            updated_metadata["model_routing"] = routing_metadata
        routing_metadata.update(
            {
                "source_model": requested_model,
                "target_model": requested_model,
                "reason": decision.reason,
            }
        )
        routing_metadata.setdefault("tokens_saved", 0)
        routing_metadata.setdefault("usd_saved", 0.0)
        if decision.confidence is not None:
            routing_metadata["confidence"] = decision.confidence
        if decision.scorer:
            routing_metadata["scorer"] = decision.scorer
        if decision.signals:
            routing_metadata["signals"] = list(decision.signals)
        attach_model_routing_trace(
            updated_metadata,
            ModelRoutingDecisionTrace(
                request_id=request_id,
                mechanism="optimization_preset",
                requested_model=requested_model,
                effective_model=requested_model,
                reason=decision.reason,
                applied=False,
                scorer=decision.scorer,
                confidence=decision.confidence,
                candidates=[requested_model],
                rejected_candidates=[{"model": requested_model, "reason": decision.reason}],
                transport={
                    "provider": transport_provider,
                    "implicit_downgrade_allowed": implicit_downgrade_allowed,
                },
            ),
        )
        return requested_model, updated_metadata

    if not implicit_downgrade_allowed:
        safe_targets = set(getattr(router.config, "transport_safe_targets", set()))
        if decision.target_model not in safe_targets:
            attach_model_routing_trace(
                updated_metadata,
                ModelRoutingDecisionTrace(
                    request_id=request_id,
                    mechanism="optimization_preset",
                    requested_model=requested_model,
                    effective_model=requested_model,
                    reason="downgrade_blocked_unproven_transport",
                    applied=False,
                    scorer=decision.scorer,
                    confidence=decision.confidence,
                    candidates=[requested_model, decision.target_model],
                    rejected_candidates=[
                        {"model": decision.target_model, "reason": "target_not_transport_safe"}
                    ],
                    transport={
                        "provider": transport_provider,
                        "implicit_downgrade_allowed": False,
                        "safe_targets": sorted(safe_targets),
                        "target_proven": False,
                    },
                ),
            )
            return requested_model, updated_metadata

    updated_metadata["model_routing"] = {
        "source_model": decision.source_model or requested_model,
        "target_model": decision.target_model,
        "reason": decision.reason,
        "tokens_saved": 0,
        "usd_saved": 0.0,
    }
    if decision.confidence is not None:
        updated_metadata["model_routing"]["confidence"] = decision.confidence
    if decision.scorer:
        updated_metadata["model_routing"]["scorer"] = decision.scorer
    if decision.signals:
        updated_metadata["model_routing"]["signals"] = list(decision.signals)
    if decision.request_overrides:
        updated_metadata["model_routing"]["request_overrides"] = decision.request_overrides
    attach_model_routing_trace(
        updated_metadata,
        ModelRoutingDecisionTrace(
            request_id=request_id,
            mechanism="optimization_preset",
            requested_model=requested_model,
            effective_model=decision.target_model,
            reason=decision.reason,
            applied=True,
            scorer=decision.scorer,
            confidence=decision.confidence,
            candidates=[requested_model, decision.target_model],
            transport={
                "provider": transport_provider,
                "implicit_downgrade_allowed": implicit_downgrade_allowed,
                "target_proven": implicit_downgrade_allowed
                or decision.target_model
                in set(getattr(router.config, "transport_safe_targets", set())),
            },
        ),
    )
    return decision.target_model, updated_metadata


__all__ = [
    "ModelRouter",
    "ModelRouterConfig",
    "ModelRoute",
    "ModelRoutingMode",
    "MODEL_ROUTING_SCORER_ARTIFACT_ENV",
    "HeuristicTaskComplexityScorer",
    "RoutingDecision",
    "TaskComplexityAssessment",
    "TaskComplexityScorer",
    "assess_task_complexity",
    "model_routing_mode_for_state",
    "model_routing_preset_for_mode",
    "normalize_model_routing_mode",
    "prepare_model_routing",
]

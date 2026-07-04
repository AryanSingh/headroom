"""Intelligence Pipeline — orchestrates all 6 intelligence layer modules.

Integrates task-aware compression, semantic dedup, context budgeting,
cross-session profiles, multi-agent shared state, and cost forecasting
into the proxy request pipeline at two points:

1. Pre-compression: extract task, load profile, evaluate policy, check shared context
2. Post-compression: dedup, context budget, record stats, cost forecast, store shared

The 6 features:
1. Task-Aware Compression — score each message by relevance to current task,
   apply differential compression (high-relevance → preserve, low → crush)
2. Semantic Dedup — rolling hash index, replace repeated content with CCR pointers
3. Context Budget — set token budget per session, progressive compression as budget fills
4. Cross-Session Profiles — learn compression patterns per workspace, apply to future sessions
5. Multi-Agent Shared State — shared compression cache so agent B reuses agent A's work
6. Cost Forecasting + Policy Engine — pre-task cost estimation, policy-driven compression

Usage in handler:
    pipeline = IntelligencePipeline.from_config(config)
    ctx = pipeline.pre_compression(messages, model, request_id)
    # ... existing compression stages ...
    messages = pipeline.post_compression(messages, original_messages, ctx)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from cutctx.proxy.autopilot import (
    AutopilotConfig,
    AutopilotController,
    LevelAdjustment,
    QualitySignal,
)

logger = logging.getLogger("cutctx.intelligence")

# ── Runtime flag store ────────────────────────────────────────────────────────
# Module-level mutable dict. The /admin/config/flags endpoint writes here;
# from_config() reads it per-request to allow live toggling without restart.
_RUNTIME_FLAGS: dict[str, Any] = {}


def set_runtime_flag(key: str, value: Any) -> None:
    """Set a runtime override for an intelligence feature flag."""
    _RUNTIME_FLAGS[key] = value


def get_runtime_flag(key: str, default: Any = None) -> Any:
    """Get a runtime flag value, returning default if not set."""
    return _RUNTIME_FLAGS.get(key, default)


def get_all_runtime_flags() -> dict[str, Any]:
    """Return a copy of all current runtime flag overrides."""
    return dict(_RUNTIME_FLAGS)


def clear_runtime_flag(key: str) -> None:
    """Remove a runtime override, reverting to config default."""
    _RUNTIME_FLAGS.pop(key, None)


@dataclass
class PipelineContext:
    """Context carried between pre_compression and post_compression."""

    task: str | None = None
    task_extracted_at: float = 0.0
    dedup_count: int = 0
    tokens_saved_by_dedup: int = 0
    budget_zone: str = "GREEN"
    budget_compression_applied: bool = False
    cost_estimate_usd: float = 0.0
    cost_savings_usd: float = 0.0
    profile_loaded: bool = False
    profile_recommendations: dict[str, float] = field(default_factory=dict)
    policy_strategy: str = "light"
    policy_compression_ratio: float = 0.70
    policy_rationale: str = ""
    shared_context_hit: bool = False
    total_latency_ms: float = 0.0

    # Per-message relevance scores (task-aware)
    message_relevance_scores: list[float] = field(default_factory=list)
    autopilot_task_type: str = "general"
    autopilot_level: int | None = None
    autopilot_biases: dict[int, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "dedup_count": self.dedup_count,
            "tokens_saved_by_dedup": self.tokens_saved_by_dedup,
            "budget_zone": self.budget_zone,
            "budget_compression_applied": self.budget_compression_applied,
            "cost_estimate_usd": round(self.cost_estimate_usd, 6),
            "cost_savings_usd": round(self.cost_savings_usd, 6),
            "profile_loaded": self.profile_loaded,
            "profile_recommendations": self.profile_recommendations,
            "policy_strategy": self.policy_strategy,
            "policy_compression_ratio": self.policy_compression_ratio,
            "policy_rationale": self.policy_rationale,
            "shared_context_hit": self.shared_context_hit,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "message_relevance_scores": self.message_relevance_scores,
            "autopilot_task_type": self.autopilot_task_type,
            "autopilot_level": self.autopilot_level,
        }


class IntelligencePipeline:
    """Orchestrates intelligence layer modules in the proxy pipeline.

    Instances should be long-lived (per-proxy, not per-request) so that
    stateful components (deduplicator, budget controller, cost tracker)
    accumulate across requests within a session.
    """

    def __init__(
        self,
        *,
        task_aware: bool = False,
        dedup: bool = False,
        context_budget: bool = False,
        context_budget_max_tokens: int = 100_000,
        context_budget_policy: str = "balanced",
        profiles: bool = False,
        shared_context: bool = False,
        cost_forecast: bool = False,
        autopilot: bool = False,
        autopilot_config: AutopilotConfig | None = None,
        model: str = "claude-3-5-sonnet-20241022",
    ):
        self.task_aware = task_aware
        self.dedup = dedup
        self.context_budget = context_budget
        self.context_budget_max_tokens = context_budget_max_tokens
        self.context_budget_policy = context_budget_policy
        self.profiles = profiles
        self.shared_context = shared_context
        self.cost_forecast = cost_forecast
        self.autopilot = autopilot
        self.autopilot_config = autopilot_config or AutopilotConfig()
        self.model = model

        # Stateful instances — persist across requests within same pipeline
        self._deduplicator: Any = None
        self._budget_controller: Any = None
        self._cost_tracker: Any = None
        self._profile: Any = None
        self._coordinator: Any = None
        self._autopilot_controller: AutopilotController | None = None
        self._autopilot_level_history: list[dict[str, Any]] = []
        self._autopilot_adjustments: list[dict[str, Any]] = []
        self._autopilot_history_limit = 24

    def sync_from_config(self, config: Any) -> IntelligencePipeline:
        """Refresh live flags from ProxyConfig/runtime overrides without losing state."""

        def _flag(key: str, default: bool = False) -> bool:
            if key in _RUNTIME_FLAGS:
                return bool(_RUNTIME_FLAGS[key])
            value = getattr(config, key, default)
            if type(value).__module__.startswith("unittest.mock"):
                return default
            return bool(value)

        def _get_int(key: str, default: int) -> int:
            value = getattr(config, key, default)
            if type(value).__module__.startswith("unittest.mock"):
                return default
            if isinstance(value, bool):
                return default
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        def _get_str(key: str, default: str) -> str:
            value = getattr(config, key, default)
            if type(value).__module__.startswith("unittest.mock"):
                return default
            return value if isinstance(value, str) and value else default

        self.task_aware = _flag("task_aware_enabled")
        self.dedup = _flag("dedup_enabled")
        self.context_budget = _flag("context_budget_enabled")
        self.context_budget_max_tokens = _get_int("context_budget_max_tokens", 100_000)
        self.context_budget_policy = _get_str("context_budget_policy", "balanced")
        self.profiles = _flag("profiles_enabled")
        self.shared_context = _flag("shared_context_enabled")
        self.cost_forecast = _flag("cost_forecast_enabled")
        self.autopilot = _flag("autopilot_enabled")
        self.model = _get_str("default_model", self.model)

        next_autopilot_config = AutopilotConfig(
            enabled=self.autopilot,
            min_level=_get_int("autopilot_min_level", 1),
            max_level=_get_int("autopilot_max_level", 5),
            hysteresis_window=_get_int("autopilot_hysteresis_window", 10),
        )
        if self.autopilot_config != next_autopilot_config:
            self.autopilot_config = next_autopilot_config
            if self._autopilot_controller is not None:
                self._autopilot_controller.config = next_autopilot_config
        return self

    @classmethod
    def from_config(cls, config: Any) -> IntelligencePipeline:
        """Create pipeline from ProxyConfig, with runtime flag overrides applied."""
        return cls().sync_from_config(config)

    def any_enabled(self) -> bool:
        """Check if any intelligence feature is enabled."""
        return any(
            [
                self.task_aware,
                self.dedup,
                self.context_budget,
                self.profiles,
                self.shared_context,
                self.cost_forecast,
                self.autopilot,
            ]
        )

    def _get_deduplicator(self) -> Any:
        """Get or create the session-scoped deduplicator."""
        if self._deduplicator is None:
            from cutctx.dedup import SessionDeduplicator

            self._deduplicator = SessionDeduplicator()
        return self._deduplicator

    def _get_budget_controller(self) -> Any:
        """Get or create the session-scoped budget controller."""
        if self._budget_controller is None:
            from cutctx.context_budget import ContextBudgetController

            self._budget_controller = ContextBudgetController(
                max_tokens=self.context_budget_max_tokens,
                model=self.model,
                policy=self.context_budget_policy,
            )
        return self._budget_controller

    def _get_cost_tracker(self) -> Any:
        """Get or create the session-scoped cost tracker."""
        if self._cost_tracker is None:
            from cutctx.cost_forecast import SessionCostTracker

            self._cost_tracker = SessionCostTracker(model=self.model)
        return self._cost_tracker

    def _get_profile(self) -> Any:
        """Get or load the workspace compression profile (cached)."""
        if self._profile is None:
            from cutctx.profiles import CompressionProfile

            self._profile = CompressionProfile.load()
        return self._profile

    def _get_coordinator(self) -> Any:
        """Get or create the multi-agent coordinator (singleton)."""
        if self._coordinator is None:
            from cutctx.shared_context import MultiAgentCoordinator

            self._coordinator = MultiAgentCoordinator.get_instance()
        return self._coordinator

    def _get_autopilot_controller(self) -> AutopilotController:
        """Get or create the WS19 controller."""
        if self._autopilot_controller is None:
            self._autopilot_controller = AutopilotController(self.autopilot_config)
        return self._autopilot_controller

    def _classify_autopilot_task_type(self, task: str | None) -> str:
        if not task:
            return "general"
        lowered = task.lower()
        if any(
            token in lowered
            for token in ("debug", "fix", "edit", "refactor", "implement", "code", "test")
        ):
            return "code"
        if any(
            token in lowered for token in ("search", "find", "grep", "lookup", "trace", "locate")
        ):
            return "search"
        if any(
            token in lowered for token in ("summarize", "summarise", "report", "overview", "list")
        ):
            return "summarize"
        return "general"

    def _bias_for_level(self, level: int) -> float:
        span = max(1, self.autopilot_config.max_level - self.autopilot_config.min_level)
        midpoint = self.autopilot_config.min_level + span / 2
        normalized = (level - midpoint) / max(span / 2, 1)
        return round(1.0 - (0.25 * normalized), 3)

    def _record_autopilot_level(self, task_type: str, level: int, timestamp_seconds: float) -> None:
        self._autopilot_level_history.append(
            {
                "task_type": task_type,
                "level": level,
                "timestamp": timestamp_seconds,
            }
        )
        if len(self._autopilot_level_history) > self._autopilot_history_limit:
            self._autopilot_level_history = self._autopilot_level_history[
                -self._autopilot_history_limit :
            ]

    @staticmethod
    def merge_biases(
        base_biases: dict[int, float] | None,
        extra_biases: dict[int, float] | None,
    ) -> dict[int, float] | None:
        if not base_biases and not extra_biases:
            return None
        if not base_biases:
            return dict(extra_biases or {})
        if not extra_biases:
            return dict(base_biases)

        merged = dict(base_biases)
        for index, value in extra_biases.items():
            merged[index] = merged.get(index, 1.0) * value
        return merged

    def record_quality_signal(
        self,
        task_type: str,
        outcome: str,
        *,
        timestamp_seconds: float | None = None,
    ) -> LevelAdjustment | None:
        if not self.autopilot:
            return None

        controller = self._get_autopilot_controller()
        signal_timestamp = time.time() if timestamp_seconds is None else timestamp_seconds
        adjustment = controller.ingest(
            signal=QualitySignal(
                task_type=task_type,
                outcome=outcome,
                timestamp_seconds=signal_timestamp,
            )
        )
        current_level = controller.current_level(task_type)
        self._record_autopilot_level(task_type, current_level, signal_timestamp)
        if adjustment is not None:
            self._autopilot_adjustments.append(
                {
                    "task_type": adjustment.task_type,
                    "old_level": adjustment.old_level,
                    "new_level": adjustment.new_level,
                    "signal_kind": adjustment.signal_kind,
                    "timestamp": adjustment.timestamp_seconds,
                }
            )
            if len(self._autopilot_adjustments) > self._autopilot_history_limit:
                self._autopilot_adjustments = self._autopilot_adjustments[
                    -self._autopilot_history_limit :
                ]
        return adjustment

    def autopilot_snapshot(self) -> dict[str, Any]:
        controller = self._autopilot_controller
        task_levels: dict[str, int] = {}
        task_stats: dict[str, dict[str, int]] = {}
        if controller is not None:
            for task_type, stats in controller._stats.items():
                task_levels[task_type] = controller.current_level(task_type)
                task_stats[task_type] = {
                    "signal_count": stats.signal_count,
                    "clean_count": stats.clean_count,
                    "adjustment_count": stats.adjustment_count,
                }
        return {
            "enabled": self.autopilot,
            "min_level": self.autopilot_config.min_level,
            "max_level": self.autopilot_config.max_level,
            "hysteresis_window": self.autopilot_config.hysteresis_window,
            "task_levels": task_levels,
            "task_stats": task_stats,
            "recent_levels": list(self._autopilot_level_history),
            "recent_adjustments": list(self._autopilot_adjustments),
        }

    # ----------------------------------------------------------------
    # Pre-compression: runs BEFORE existing compression stages
    # ----------------------------------------------------------------

    def pre_compression(
        self,
        messages: list[dict[str, Any]],
        model: str,
        request_id: str = "",
    ) -> PipelineContext:
        """Run pre-compression intelligence steps.

        1. Task extraction — identify the agent's current goal
        2. Profile loading — load workspace-specific compression preferences
        3. Policy evaluation — select compression strategy based on budget+context
        4. Shared context check — see if other agents have cached results
        5. Per-message relevance scoring — if task-aware, score each message
        """
        ctx = PipelineContext()
        t0 = time.monotonic()

        # 1. Task extraction (cheapest — always try if enabled)
        if self.task_aware:
            try:
                from cutctx.compression.task_aware import TaskExtractor

                ctx.task = TaskExtractor.extract_task(messages)
                ctx.task_extracted_at = time.monotonic()
                if ctx.task:
                    logger.debug(
                        "[%s] Intelligence: task extracted: %.80s",
                        request_id,
                        ctx.task,
                    )
            except Exception as e:
                logger.debug("[%s] Intelligence: task extraction failed: %s", request_id, e)

        # 2. Profile-guided compression settings (reads from disk, cached)
        if self.profiles:
            try:
                profile = self._get_profile()
                ctx.profile_loaded = True
                # Collect per-type recommendations
                for content_type, stats in profile.stats.items():
                    ctx.profile_recommendations[content_type] = stats.recommended_ratio
                logger.debug(
                    "[%s] Intelligence: profile loaded (%d content types)",
                    request_id,
                    len(profile.stats),
                )
            except Exception as e:
                logger.debug("[%s] Intelligence: profile load failed: %s", request_id, e)

        # 3. Policy evaluation — use cost forecast to select compression strategy
        if self.cost_forecast:
            try:
                from cutctx.cost_forecast import PolicyEngine

                engine = PolicyEngine(model=self.model)

                # Estimate input tokens (rough: 4 chars per token)
                total_chars = sum(len(str(m.get("content", ""))) for m in messages)
                input_tokens = max(1, total_chars // 4)

                # Check budget from cost tracker
                budget_remaining = 100.0
                tracker = self._get_cost_tracker()
                if tracker._budget_usd is not None:
                    snap = tracker.snapshot()
                    budget_remaining = snap.budget_remaining_usd or 100.0

                decision = engine.evaluate(
                    input_tokens=input_tokens,
                    budget_remaining_usd=budget_remaining,
                )
                ctx.policy_strategy = decision.strategy.value
                ctx.policy_compression_ratio = decision.compression_ratio
                ctx.policy_rationale = decision.rationale
                ctx.cost_estimate_usd = decision.estimated_savings_usd

                logger.debug(
                    "[%s] Intelligence: policy=%s ratio=%.2f (%s)",
                    request_id,
                    decision.strategy.value,
                    decision.compression_ratio,
                    decision.rationale,
                )
            except Exception as e:
                logger.debug("[%s] Intelligence: policy evaluation failed: %s", request_id, e)

        # 4. Shared context check — see if another agent compressed this content
        if self.shared_context:
            try:
                coordinator = self._get_coordinator()
                # Register proxy as an agent
                coordinator.register_agent("proxy", {"type": "proxy", "model": self.model})

                # Check if there are cache hits for recent content
                agent_ctx = coordinator.get_agent_context("proxy")
                if agent_ctx and agent_ctx.total_items_compressed > 0:
                    ctx.shared_context_hit = True
                    logger.debug(
                        "[%s] Intelligence: shared context has %d compressed items",
                        request_id,
                        agent_ctx.total_items_compressed,
                    )
            except Exception as e:
                logger.debug("[%s] Intelligence: shared context check failed: %s", request_id, e)

        # 5. Per-message relevance scoring (task-aware)
        if self.task_aware and ctx.task:
            try:
                from cutctx.compression.task_aware import RelevanceModulator

                modulator = RelevanceModulator(use_bm25=True)
                ctx.message_relevance_scores = []
                for msg in messages:
                    content = msg.get("content", "")
                    if isinstance(content, str) and len(content) > 20:
                        score = modulator.score(content, ctx.task)
                        ctx.message_relevance_scores.append(score)
                    else:
                        ctx.message_relevance_scores.append(1.0)  # Short/structured: fully relevant
                logger.debug(
                    "[%s] Intelligence: scored %d messages, avg relevance=%.2f",
                    request_id,
                    len(ctx.message_relevance_scores),
                    sum(ctx.message_relevance_scores) / max(1, len(ctx.message_relevance_scores)),
                )
            except Exception as e:
                logger.debug("[%s] Intelligence: relevance scoring failed: %s", request_id, e)

        if self.autopilot:
            try:
                controller = self._get_autopilot_controller()
                ctx.autopilot_task_type = self._classify_autopilot_task_type(ctx.task)
                ctx.autopilot_level = controller.current_level(ctx.autopilot_task_type)
                bias = self._bias_for_level(ctx.autopilot_level)
                ctx.autopilot_biases = dict.fromkeys(range(len(messages)), bias)
                self._record_autopilot_level(
                    ctx.autopilot_task_type,
                    ctx.autopilot_level,
                    time.time(),
                )
            except Exception as e:
                logger.debug(
                    "[%s] Intelligence: autopilot pre-compression failed: %s", request_id, e
                )

        ctx.total_latency_ms = (time.monotonic() - t0) * 1000
        return ctx

    # ----------------------------------------------------------------
    # Post-compression: runs AFTER existing compression stages
    # ----------------------------------------------------------------

    def post_compression(
        self,
        messages: list[dict[str, Any]],
        original_messages: list[dict[str, Any]],
        ctx: PipelineContext,
        request_id: str = "",
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        routing_log: list[dict] | None = None,
    ) -> list[dict[str, Any]]:
        """Run post-compression intelligence steps.

        1. Semantic dedup — replace duplicate content with CCR pointers
        2. Context budget — progressive compression if approaching limits
        3. Cost estimation — track costs and savings
        4. Profile recording — update workspace profile with session stats
           Uses ``routing_log`` when provided to record per-section stats
           instead of a single ``"mixed"`` entry.
        5. Shared context — store compressed result for other agents
        """
        t0 = time.monotonic()
        result = messages

        # 1. Semantic dedup (replaces duplicate content with CCR pointers)
        if self.dedup:
            try:
                deduplicator = self._get_deduplicator()
                dedup_result = deduplicator.process(result)
                if dedup_result.dedup_count > 0:
                    ctx.dedup_count = dedup_result.dedup_count
                    ctx.tokens_saved_by_dedup = dedup_result.tokens_saved
                    result = dedup_result.messages
                    logger.info(
                        "[%s] Intelligence: dedup saved %d tokens (%d duplicates)",
                        request_id,
                        dedup_result.tokens_saved,
                        dedup_result.dedup_count,
                    )
            except Exception as e:
                logger.debug("[%s] Intelligence: dedup failed: %s", request_id, e)

        # 2. Context budget (progressive compression when context fills)
        if self.context_budget:
            try:
                budget_controller = self._get_budget_controller()
                before_count = len(result)
                result = budget_controller.apply(result)
                status = budget_controller.status
                ctx.budget_zone = status.zone.value
                ctx.budget_compression_applied = status.compression_applied
                if status.compression_applied:
                    logger.info(
                        "[%s] Intelligence: context budget %s zone — compressed %d→%d messages",
                        request_id,
                        status.zone.value,
                        before_count,
                        len(result),
                    )
            except Exception as e:
                logger.debug("[%s] Intelligence: context budget failed: %s", request_id, e)

        # 3. Cost estimation — record this request's costs
        if self.cost_forecast:
            try:
                tracker = self._get_cost_tracker()
                # Use actual token counts if available, else estimate
                tokens_before = sum(len(str(m.get("content", ""))) // 4 for m in original_messages)
                tokens_after = sum(len(str(m.get("content", ""))) // 4 for m in result)
                actual_input = input_tokens or tokens_before
                actual_output = output_tokens

                compressed_input = tokens_after if tokens_after < tokens_before else None
                estimate = tracker.record_request(
                    input_tokens=actual_input,
                    output_tokens=actual_output,
                    compressed_input_tokens=compressed_input,
                )
                ctx.cost_estimate_usd = estimate.total_usd
                ctx.cost_savings_usd = estimate.compression_savings_usd
                logger.debug(
                    "[%s] Intelligence: cost $%.6f (savings $%.6f)",
                    request_id,
                    estimate.total_usd,
                    estimate.compression_savings_usd,
                )
            except Exception as e:
                logger.debug("[%s] Intelligence: cost forecast failed: %s", request_id, e)

        # 4. Profile recording — update workspace profile with this session's stats
        if self.profiles:
            try:
                profile = self._get_profile()
                # Compute compression stats per content type
                stats_entries = []
                if routing_log:
                    # Use per-section routing decisions for granular stats
                    for section in routing_log:
                        ct = section.get("content_type", "mixed")
                        orig_tok = section.get("original_count", 0) or section.get(
                            "original_tokens", 0
                        )
                        comp_tok = section.get("compressed_count", 0) or section.get(
                            "compressed_tokens", 0
                        )
                        if orig_tok > 0:
                            stats_entries.append(
                                {
                                    "content_type": ct,
                                    "original_count": orig_tok,
                                    "compressed_count": comp_tok,
                                    "was_retrieved": False,
                                }
                            )
                else:
                    # Fall back to aggregate estimate when routing_log is not available
                    orig_tokens = sum(
                        len(str(m.get("content", ""))) // 4 for m in original_messages
                    )
                    comp_tokens = sum(len(str(m.get("content", ""))) // 4 for m in result)
                    if orig_tokens > 0:
                        stats_entries.append(
                            {
                                "content_type": "mixed",
                                "original_count": orig_tokens,
                                "compressed_count": comp_tokens,
                                "was_retrieved": False,
                            }
                        )
                if stats_entries:
                    profile.record_session(
                        session_id=request_id,
                        stats=stats_entries,
                    )
                    profile.save()
            except Exception as e:
                logger.debug("[%s] Intelligence: profile record failed: %s", request_id, e)

        # 5. Shared context — store compressed result for other agents
        if self.shared_context:
            try:
                coordinator = self._get_coordinator()
                # Store a summary of what this request compressed
                if result and len(result) > 0:
                    summary_content = str(result[-1].get("content", ""))[:500]
                    coordinator.compress_shared(
                        content=summary_content,
                        agent_id="proxy",
                        workspace_key=self.model,
                    )
            except Exception as e:
                logger.debug("[%s] Intelligence: shared context store failed: %s", request_id, e)

        if self.autopilot and ctx.autopilot_task_type:
            try:
                self.record_quality_signal(ctx.autopilot_task_type, "clean")
            except Exception as e:
                logger.debug("[%s] Intelligence: autopilot clean-signal failed: %s", request_id, e)

        ctx.total_latency_ms += (time.monotonic() - t0) * 1000
        return result

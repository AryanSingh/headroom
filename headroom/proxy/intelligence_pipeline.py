"""Intelligence Pipeline — orchestrates all 6 intelligence layer modules.

Integrates task-aware compression, semantic dedup, context budgeting,
cross-session profiles, multi-agent shared state, and cost forecasting
into the proxy request pipeline at two points:

1. Pre-compression: extract task, load profile, check shared context
2. Post-compression: dedup, context budget, record stats, cost forecast

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

logger = logging.getLogger("headroom.intelligence")


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
    profile_loaded: bool = False
    total_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "dedup_count": self.dedup_count,
            "tokens_saved_by_dedup": self.tokens_saved_by_dedup,
            "budget_zone": self.budget_zone,
            "budget_compression_applied": self.budget_compression_applied,
            "cost_estimate_usd": round(self.cost_estimate_usd, 6),
            "profile_loaded": self.profile_loaded,
            "total_latency_ms": round(self.total_latency_ms, 2),
        }


class IntelligencePipeline:
    """Orchestrates intelligence layer modules in the proxy pipeline."""

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
        self.model = model

        # Lazy-initialized module instances (per-request or shared)
        self._deduplicator: Any = None
        self._budget_controller: Any = None

    @classmethod
    def from_config(cls, config: Any) -> IntelligencePipeline:
        """Create pipeline from ProxyConfig."""
        return cls(
            task_aware=getattr(config, "task_aware_enabled", False),
            dedup=getattr(config, "dedup_enabled", False),
            context_budget=getattr(config, "context_budget_enabled", False),
            context_budget_max_tokens=getattr(config, "context_budget_max_tokens", 100_000),
            context_budget_policy=getattr(config, "context_budget_policy", "balanced"),
            profiles=getattr(config, "profiles_enabled", False),
            shared_context=getattr(config, "shared_context_enabled", False),
            cost_forecast=getattr(config, "cost_forecast_enabled", False),
            model=getattr(config, "default_model", "claude-3-5-sonnet-20241022"),
        )

    def any_enabled(self) -> bool:
        """Check if any intelligence feature is enabled."""
        return any([
            self.task_aware, self.dedup, self.context_budget,
            self.profiles, self.shared_context, self.cost_forecast,
        ])

    def pre_compression(
        self,
        messages: list[dict[str, Any]],
        model: str,
        request_id: str = "",
    ) -> PipelineContext:
        """Run pre-compression intelligence steps.

        Extracts task from messages, loads workspace profile, checks shared context.
        Returns a PipelineContext that post_compression will use.
        """
        ctx = PipelineContext()
        t0 = time.monotonic()

        # 1. Task extraction (cheapest — always try if enabled)
        if self.task_aware:
            try:
                from headroom.compression.task_aware import TaskExtractor
                ctx.task = TaskExtractor.extract_task(messages)
                ctx.task_extracted_at = time.monotonic()
                if ctx.task:
                    logger.debug(
                        "[%s] Intelligence: task extracted: %.60s...",
                        request_id, ctx.task,
                    )
            except Exception as e:
                logger.debug("[%s] Intelligence: task extraction failed: %s", request_id, e)

        # 2. Profile-guided compression settings (reads from disk, cached)
        if self.profiles:
            try:
                from headroom.profiles import CompressionProfile
                profile = CompressionProfile.load()
                ctx.profile_loaded = True
                # Profile data is available for downstream use
                logger.debug(
                    "[%s] Intelligence: profile loaded (%d content types)",
                    request_id, len(profile.stats),
                )
            except Exception as e:
                logger.debug("[%s] Intelligence: profile load failed: %s", request_id, e)

        # 3. Shared context check
        if self.shared_context:
            try:
                from headroom.shared_context import MultiAgentCoordinator
                coordinator = MultiAgentCoordinator()
                agent_context = coordinator.get_agent_context("proxy")
                if agent_context:
                    logger.debug(
                        "[%s] Intelligence: shared context has %d entries",
                        request_id, len(agent_context),
                    )
            except Exception as e:
                logger.debug("[%s] Intelligence: shared context check failed: %s", request_id, e)

        ctx.total_latency_ms = (time.monotonic() - t0) * 1000
        return ctx

    def post_compression(
        self,
        messages: list[dict[str, Any]],
        original_messages: list[dict[str, Any]],
        ctx: PipelineContext,
        request_id: str = "",
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> list[dict[str, Any]]:
        """Run post-compression intelligence steps.

        Applies semantic dedup and context budget compression.
        Records cost estimate and profile stats.
        Returns optimized messages.
        """
        t0 = time.monotonic()
        result = messages

        # 1. Semantic dedup (replaces duplicate content with CCR pointers)
        if self.dedup:
            try:
                from headroom.dedup import SessionDeduplicator
                if self._deduplicator is None:
                    self._deduplicator = SessionDeduplicator()
                dedup_result = self._deduplicator.process(result)
                if dedup_result.dedup_count > 0:
                    ctx.dedup_count = dedup_result.dedup_count
                    ctx.tokens_saved_by_dedup = dedup_result.tokens_saved
                    result = dedup_result.messages
                    logger.info(
                        "[%s] Intelligence: dedup saved %d tokens (%d duplicates)",
                        request_id, dedup_result.tokens_saved, dedup_result.dedup_count,
                    )
            except Exception as e:
                logger.debug("[%s] Intelligence: dedup failed: %s", request_id, e)

        # 2. Context budget (progressive compression when context fills)
        if self.context_budget:
            try:
                from headroom.context_budget import ContextBudgetController
                if self._budget_controller is None:
                    self._budget_controller = ContextBudgetController(
                        max_tokens=self.context_budget_max_tokens,
                        model=self.model,
                        policy=self.context_budget_policy,
                    )
                before_count = len(result)
                result = self._budget_controller.apply(result)
                status = self._budget_controller.status
                ctx.budget_zone = status.zone.value
                ctx.budget_compression_applied = status.compression_applied
                if status.compression_applied:
                    logger.info(
                        "[%s] Intelligence: context budget %s zone — "
                        "compressed %d→%d messages",
                        request_id, status.zone.value,
                        before_count, len(result),
                    )
            except Exception as e:
                logger.debug("[%s] Intelligence: context budget failed: %s", request_id, e)

        # 3. Cost estimation
        if self.cost_forecast and (input_tokens > 0 or output_tokens > 0):
            try:
                from headroom.cost_forecast import CostEstimator
                estimator = CostEstimator(self.model)
                tokens_before = sum(
                    len(str(m.get("content", ""))) // 4
                    for m in original_messages
                )
                tokens_after = sum(
                    len(str(m.get("content", ""))) // 4
                    for m in result
                )
                compression_ratio = (
                    1.0 - (tokens_after / tokens_before)
                    if tokens_before > 0 else 0.0
                )
                estimate = estimator.estimate(
                    input_tokens=input_tokens or tokens_after,
                    output_tokens=output_tokens,
                    compression_ratio=compression_ratio,
                )
                ctx.cost_estimate_usd = estimate.total_usd
                logger.debug(
                    "[%s] Intelligence: cost estimate $%.6f "
                    "(compression %.0f%%)",
                    request_id, estimate.total_usd,
                    compression_ratio * 100,
                )
            except Exception as e:
                logger.debug("[%s] Intelligence: cost forecast failed: %s", request_id, e)

        # 4. Profile recording
        if self.profiles:
            try:
                from headroom.profiles import CompressionProfile
                profile = CompressionProfile.load()
                profile.record_session(
                    session_id=request_id,
                    stats=[{
                        "content_type": "mixed",
                        "original_count": len(original_messages),
                        "compressed_count": len(result),
                        "was_retrieved": False,
                    }],
                )
                profile.save()
            except Exception as e:
                logger.debug("[%s] Intelligence: profile record failed: %s", request_id, e)

        # 5. Shared context: store compressed result for other agents
        if self.shared_context:
            try:
                from headroom.shared_context import MultiAgentCoordinator
                coordinator = MultiAgentCoordinator()
                coordinator.compress_shared(
                    agent_id="proxy",
                    messages=result,
                )
            except Exception as e:
                logger.debug("[%s] Intelligence: shared context store failed: %s", request_id, e)

        ctx.total_latency_ms += (time.monotonic() - t0) * 1000
        return result

"""``RequestOutcome``: the canonical value type for "what happened during
one completed proxy request."

Per the P0 audit (``docs/superpowers/specs/P0-proxy-pipeline-audit.md``),
18 ``metrics.record_request`` call sites across four handler files
disagreed on argument shape — 9 of 18 omitted ``cached=``, 7 of 18
omitted ``attempted_input_tokens=``, only 4 sites emitted a structured
PERF log at all. This module is the structural fix: every handler
converges on building a :class:`RequestOutcome` at end-of-request and
hands it to :func:`emit_request_outcome` (also exposed as
:meth:`CutctxProxy._record_request_outcome`), which owns the four
downstream effects (Prometheus, cost tracker, request logger, PERF
log).

Note: this is **output unification, not input unification**. Provider
APIs (Anthropic ``/v1/messages``, OpenAI Responses WS, Gemini
``generateContent``, Bedrock, Vertex) stay wildly different — the proxy
talks each upstream in its native dialect. This dataclass standardises
only the *observation* about a completed request. Provider-specific
concepts (Anthropic's 5m/1h cache TTL splits, OpenAI's
inferred-write flag, Gemini's read-only cache count) live as optional
fields with neutral defaults; handlers populate what their provider
actually reports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from cutctx.proxy.decision_receipt import (
    build_decision_receipt,
    build_minimal_decision_receipt,
)

if TYPE_CHECKING:
    from cutctx.savings import RequestSavingsBreakdown

logger = logging.getLogger("cutctx.proxy")
_CUTCTX_REATTRIBUTABLE_SOURCES = {
    "tool_schema_compaction",
    "api_surface_slimming",
}
_OBSERVED_PROVIDER_SOURCES = {"provider_prompt_cache"}
_DECLINE_REASON_ALIASES = {
    "cache_protected": "cache_protection",
    "prefix_cache_protected": "cache_protection",
    "too_small": "below_threshold",
    "below_min_tokens": "below_threshold",
    "disabled": "feature_disabled",
    "compression_disabled": "feature_disabled",
    "unsupported": "unsupported_request",
    "guardrail": "quality_guardrail",
    "empty": "no_eligible_content",
    "no_messages": "no_eligible_content",
}


def normalize_decline_reason(value: str | None) -> str | None:
    if not value:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return _DECLINE_REASON_ALIASES.get(normalized, normalized)


def _normalize_model_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _models_equivalent(actual: Any, expected: Any) -> bool:
    """Return True when two model labels refer to the same routed model.

    Providers occasionally add a build suffix to the actual response model
    name. Treat exact matches and hyphen-delimited suffixes as equivalent, so
    we do not drop legitimate savings just because the backend reported a
    versioned variant of the routed target.
    """

    actual_norm = _normalize_model_name(actual)
    expected_norm = _normalize_model_name(expected)
    if not actual_norm or not expected_norm:
        return False
    if actual_norm == expected_norm:
        return True
    return actual_norm.startswith(f"{expected_norm}-") or expected_norm.startswith(
        f"{actual_norm}-"
    )


def _summarize_transforms(transforms: list[str]) -> str:
    """Collapse repeated transform labels without importing cost tracking.

    Outcome emission runs in streaming and WebSocket completion paths. The
    cost module has optional provider-facing dependencies, so importing it in
    this hot path can stall completion while those dependencies initialize.
    """

    if not transforms:
        return "none"
    counts: dict[str, int] = {}
    for transform in transforms:
        counts[transform] = counts.get(transform, 0) + 1
    return " ".join(
        f"{transform}*{count}" if count > 1 else transform for transform, count in counts.items()
    )


@dataclass(frozen=True)
class RequestOutcome:
    """Immutable, value-equal snapshot of a completed request.

    Construction policy: every field that downstream consumers read MUST
    be either required (no default) or have a neutral default that makes
    the consumer's behaviour identical to "field not present". This keeps
    the contract honest — a handler that forgets a field doesn't silently
    produce wrong metrics; it produces zeros, which the dashboard can
    surface as a missing-data condition (P3 follow-up).
    """

    # ── Identity ──────────────────────────────────────────────────────
    request_id: str
    provider: str
    model: str

    # ── Tokens (required — every site has these) ──────────────────────
    # original_tokens: pre-compression request size, for `tok_before`
    # optimized_tokens: post-compression bytes actually forwarded, for
    #     ``input_tokens`` and ``tok_after``
    # output_tokens: response tokens from upstream
    # tokens_saved: original - optimized (or 0 if compression bypassed)
    # attempted_input_tokens: denominator for active-savings-percent.
    #     The compressible portion only — excludes user messages, system
    #     prompts, prior assistant turns, frozen prefix bytes. This is the
    #     field 7 of 18 audit sites forgot to pass, collapsing
    #     ``active_savings_percent`` to 0 (#454 / #455).
    original_tokens: int
    optimized_tokens: int
    output_tokens: int
    tokens_saved: int
    attempted_input_tokens: int

    # ── Ghost Token Auditing ──────────────────────────────────────────
    scaffolding_tokens: int = 0
    ghost_tokens: int = 0

    # ── Cache (provider-agnostic; unused fields stay 0) ───────────────
    # Anthropic populates all five (read + write + 5m + 1h + uncached).
    # OpenAI populates read + inferred-write + uncached, and sets
    # ``cache_inferred=True`` so the dashboard can warn that the write
    # column is an estimate rather than an upstream-reported counter.
    # Gemini populates read only.
    # Bedrock mirrors Anthropic (it forwards Anthropic-shape usage).
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0
    uncached_input_tokens: int = 0
    cache_inferred: bool = False
    provider_cache_observed: bool = False
    # Response-cache hit (Cutctx's own semantic cache served the
    # response from a prior call — completely distinct from
    # upstream-prompt-cache `cache_read_tokens`). True means the proxy
    # never reached the provider at all. Used to drive the
    # Prometheus ``cached`` counter and dashboard "response cache" row.
    from_response_cache: bool = False

    # ── Savings sources beyond provider cache (Phase 1.4) ────────────────
    # Each field carries the raw counter / dollar value as known at the
    # source of truth. The funnel (emit_request_outcome) is the single
    # place that converts these into a unified ``RequestSavingsBreakdown``
    # so handlers do not duplicate the merge logic. Every field defaults
    # to 0 / None so old call sites that do not set them keep working.
    #
    # semantic_cache_avoided_tokens: tokens that did not need to be
    #   re-processed because the response was served from a prior
    #   near-duplicate request. Set by the handler when it returns a
    #   cached response. Independent of ``from_response_cache`` because
    #   semantic hits can also be reported when the proxy did forward
    #   the request (e.g. a partial reuse).
    # semantic_cache_hit: True when the proxy served the response from
    #   a prior similar request. Distinct from ``from_response_cache``
    #   so dashboards can render "hit" vs "saved tokens" separately.
    semantic_cache_avoided_tokens: int = 0
    semantic_cache_hit: bool = False
    semantic_cache_evaluated: bool = False
    # self_hosted_prefix_cache_hits: tokens served from a self-hosted
    #   prefix cache such as vLLM APC. Independent of
    #   ``cache_read_tokens`` (which is provider-prompt-cache only).
    self_hosted_prefix_cache_hits: int = 0
    self_hosted_prefix_cache_evaluated: bool = False
    # model_routing_tokens_saved: input tokens that were served by a
    #   cheaper model than the user requested. model_routing_usd_saved:
    #   the dollar delta computed at routing time. Independent of
    #   ``tokens_saved`` (Cutctx compression) and of
    #   ``cache_read_tokens`` (provider cache).
    model_routing_tokens_saved: int = 0
    model_routing_usd_saved: float = 0.0
    # WS11 (memoization): tool calls served from the memoization cache
    #   rather than making an upstream round-trip. memoization_hits is
    #   the count of fabricated tool results; memoization_tokens_saved
    #   is an estimate of the input tokens that were avoided (content
    #   of the memoized tool result, estimated).
    memoization_hits: int = 0
    memoization_tokens_saved: int = 0
    # WS10 (output optimization): output tokens removed by the output
    #   optimizer. The value from OutputOptimizeDecision.estimated_tokens_saved.
    output_optimization_tokens_saved: int = 0
    # WS13 (batch routing): dollars saved by routing via a batch queue
    #   at a discounted rate (50% of list price). Tokens field is the
    #   input tokens that were batch-routed; usd is the computed delta.
    batch_routing_tokens_saved: int = 0
    batch_routing_usd_saved: float = 0.0
    # Optional escape hatch for sources that do not yet have a
    # dedicated field. Keys are stable lowercase source ids, values
    # are dicts with at least ``tokens`` and optionally ``usd``. The
    # funnel merges these into the breakdown after the typed fields
    # have been applied.
    savings_metadata: dict[str, dict[str, Any]] | None = None

    # Canonical attribution and opportunity-funnel fields.  These are
    # deliberately explicit rather than inferred from lifetime counters.
    savings_basis: str = "estimated"
    pricing_basis: str = "model_input_list_price"
    eligible_input_tokens: int = 0
    cache_protected_tokens: int = 0
    cache_protection_evaluated: bool = False
    compressed_tokens: int = 0
    decline_reason: str | None = None
    canary_arm: str = "control"
    canary_eligible: bool = False
    quality_success: bool | None = None
    retry_count: int = 0
    user_corrections: int = 0

    # ── Timing ────────────────────────────────────────────────────────
    # total_latency_ms: wall-clock end-to-end for this request
    # overhead_ms: time spent in compression dispatch only (subset of total)
    # ttfb_ms: time to first upstream byte for streaming paths; 0 for
    #     non-streaming or when unmeasured (no None — convention is 0)
    # pipeline_timing: optional per-stage breakdown surfaced on dashboards
    total_latency_ms: float = 0.0
    overhead_ms: float = 0.0
    ttfb_ms: float = 0.0
    pipeline_timing: dict[str, float] | None = None

    # ── Transforms + diagnostics ──────────────────────────────────────
    # transforms_applied: tuple (immutable) of every transform that ran.
    #     RequestLog still wants list[str]; the funnel converts at the
    #     boundary.
    # waste_signals: per-router signals captured during routing (counts
    #     of skipped vs applied units etc.); dashboards summarise.
    # num_messages: messages in the original request (for ``msgs=N`` in
    #     PERF), counted from body.input/body.messages.
    # turn_id: stable hash of the conversation prefix; used by
    #     dashboards to group multi-turn sessions.
    # request_messages: only populated when ``config.log_full_messages``
    #     is enabled (off by default — message bodies are sensitive).
    # tags: client-provided routing/identification tags.
    # client: identified harness driving the request (codex /
    #     claude-code / aider / cursor / opencode / zed / ...).
    #     ``None`` when neither the ``X-Client`` header nor the
    #     User-Agent matched a known harness. Populated by handlers
    #     via :func:`cutctx.proxy.auth_mode.classify_client`. The
    #     funnel surfaces this in the PERF log (``client=X``) and
    #     copies it into ``RequestLog.tags["client"]`` so dashboards
    #     can slice by harness without a separate column. This is the
    #     one-field-add that proves the refactor pays out: per-
    #     harness visibility appears across EVERY handler with zero
    #     new bookkeeping at the call sites.
    transforms_applied: tuple[str, ...] = ()
    waste_signals: dict[str, int] | None = None
    num_messages: int = 0
    turn_id: str | None = None
    request_messages: list[dict[str, Any]] | None = None
    # Post-compression messages actually sent upstream, paired with
    # ``request_messages`` (pre-compression) so consumers can diff the two.
    # Only populated when a caller threads in the pre-compression snapshot
    # (``original_messages``); otherwise ``request_messages`` carries the sent
    # body for backward compatibility and this stays ``None``.
    compressed_messages: list[dict[str, Any]] | None = None
    tags: dict[str, str] = field(default_factory=dict)
    client: str | None = None
    project: str | None = None
    ccr_references: tuple[dict[str, Any], ...] = ()
    ccr_retrieval_outcome: str | None = None

    # ── Derived (computed once, no caching needed — properties are cheap) ─

    @property
    def cache_hit(self) -> bool:
        """True iff EITHER upstream reported a cache read OR the response
        was served from Cutctx's own response cache.

        Two distinct concepts collapsed into one observable boolean for
        downstream consumers (Prometheus ``cached`` counter, RequestLog
        ``cache_hit`` flag). The dataclass tracks them separately so
        dashboards can split them; the derived property unifies them.

        Pre-refactor 9 of 18 sites hardcoded this to False — this property
        makes "I forgot to compute it" structurally impossible.
        """
        return self.cache_read_tokens > 0 or self.from_response_cache

    @property
    def cache_hit_pct(self) -> int:
        """Cache read share of (read + write), rounded to int percent.

        Returns 0 when neither read nor write fired (a request that did no
        cache work; distinguishing this from "0% hit rate on real cache
        work" requires looking at the absolute values, not the ratio).
        """
        denom = self.cache_read_tokens + self.cache_write_tokens
        if denom <= 0:
            return 0
        return round(self.cache_read_tokens / denom * 100)

    @property
    def savings_pct(self) -> float:
        """Compression savings as a fraction of the original request size.

        This is the proxy-side ratio: ``tokens_saved / original_tokens``.
        The dashboard headline "active savings percent" uses a different
        ratio (``tokens_saved / attempted_input_tokens``) — see the
        Prometheus metric for the active calculation.
        """
        if self.original_tokens <= 0:
            return 0.0
        return self.tokens_saved / self.original_tokens * 100.0

    @classmethod
    def from_stream(
        cls,
        *,
        body: dict[str, Any],
        provider: str,
        model: str,
        request_id: str,
        original_tokens: int,
        optimized_tokens: int,
        output_tokens: int,
        tokens_saved: int,
        transforms_applied: list[str] | tuple[str, ...],
        total_latency_ms: float,
        overhead_ms: float,
        tags: dict[str, str] | None,
        client: str | None,
        log_full_messages: bool = False,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        cache_write_5m_tokens: int = 0,
        cache_write_1h_tokens: int = 0,
        uncached_input_tokens: int = 0,
        cache_inferred: bool = False,
        provider_cache_observed: bool | None = None,
        ttfb_ms: float = 0.0,
        pipeline_timing: dict[str, float] | None = None,
        waste_signals: dict[str, int] | None = None,
        original_messages: list[dict] | None = None,
        savings_metadata: dict[str, dict[str, Any]] | None = None,
        # High-23 (production-audit-progress-2026-06-20.md): the
        # per-source savings fields (semantic_cache_avoided_tokens,
        # self_hosted_prefix_cache_hits, model_routing_tokens_saved,
        # model_routing_usd_saved) used to be settable only via the
        # savings_metadata escape hatch. Streaming traffic is the
        # dominant shape for Anthropic SSE and OpenAI Chat
        # Completions, so without typed-field params here, the
        # funnel's per-source merge was forced through the
        # metadata path even when the streaming finalizer had the
        # data in hand. The new params let streaming finalizers
        # populate the typed fields directly.
        semantic_cache_avoided_tokens: int = 0,
        self_hosted_prefix_cache_hits: int = 0,
        model_routing_tokens_saved: int = 0,
        model_routing_usd_saved: float = 0.0,
    ) -> RequestOutcome:
        """Construct an outcome from the locals available at streaming
        finalize. Three streaming finalizers
        (``_finalize_stream_response``, ``_stream_response_bedrock``,
        ``_stream_openai_via_backend``) each duplicated the same body- and
        config-derived fields inline. This classmethod is the single
        construction point so derivation logic can't drift apart again.

        Centralises six derivations:

          * ``attempted_input_tokens = optimized_tokens + tokens_saved``
          * ``num_messages = len(body["messages"])``
          * ``request_messages`` conditional on ``log_full_messages``
          * ``turn_id`` via ``compute_turn_id`` — pre-refactor only the
            Bedrock site computed this; sites 1 and 3 silently dropped it,
            breaking multi-turn-session grouping on Anthropic-SSE and
            OpenAI-via-backend traffic
          * ``transforms_applied`` list → tuple (frozen-dataclass contract)
          * ``tags or {}`` normalization
        """
        from cutctx.proxy.helpers import compute_turn_id

        request_items = body.get("messages")
        turn_messages = request_items
        if request_items is None:
            request_items = body.get("contents", [])
            if isinstance(request_items, list):
                turn_messages = []
                for item in request_items:
                    if not isinstance(item, dict):
                        continue
                    parts = item.get("parts")
                    text = ""
                    if isinstance(parts, list):
                        text = "\n".join(
                            str(part.get("text"))
                            for part in parts
                            if isinstance(part, dict) and part.get("text")
                        )
                    role = "assistant" if item.get("role") == "model" else "user"
                    turn_messages.append({"role": role, "content": text})
        system = body.get("system")
        if system is None:
            system = body.get("systemInstruction")

        from cutctx.ccr.markers import extract_marker_hashes_from_payload

        ccr_references = tuple(
            {
                "hash": hash_key,
                "availability": "unobserved",
                "expires_at": None,
            }
            for hash_key in extract_marker_hashes_from_payload(body)
        )

        # ``request_items`` is ``body["messages"]`` (or ``body["contents"]``
        # for Gemini, falling back to ``[]``) — the post-compression list the
        # caller already mutated in place before finalize. When a
        # caller threads in ``original_messages`` (the pre-compression
        # snapshot), log it as ``request_messages`` and the sent body as
        # ``compressed_messages`` so the two sides stay diffable. Callers that
        # don't thread it in (gemini ``contents``, OpenAI-via-backend) keep the
        # prior behaviour: sent body under ``request_messages``, no compressed
        # side. Both sides share the ``log_full_messages`` gate.
        if not log_full_messages:
            log_request_messages = None
            log_compressed_messages = None
        elif original_messages is not None:
            log_request_messages = original_messages
            log_compressed_messages = request_items
        else:
            log_request_messages = request_items
            log_compressed_messages = None

        return cls(
            request_id=request_id,
            provider=provider,
            model=model,
            original_tokens=original_tokens,
            optimized_tokens=optimized_tokens,
            output_tokens=output_tokens,
            tokens_saved=tokens_saved,
            attempted_input_tokens=optimized_tokens + tokens_saved,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            cache_write_5m_tokens=cache_write_5m_tokens,
            cache_write_1h_tokens=cache_write_1h_tokens,
            uncached_input_tokens=uncached_input_tokens,
            cache_inferred=cache_inferred,
            provider_cache_observed=(
                bool(provider_cache_observed)
                if provider_cache_observed is not None
                else bool(cache_read_tokens or cache_write_tokens or uncached_input_tokens)
            ),
            total_latency_ms=total_latency_ms,
            overhead_ms=overhead_ms,
            ttfb_ms=ttfb_ms,
            pipeline_timing=pipeline_timing,
            transforms_applied=tuple(transforms_applied),
            waste_signals=waste_signals,
            num_messages=len(request_items) if isinstance(request_items, list) else 0,
            turn_id=compute_turn_id(model, system, turn_messages),
            tags=tags or {},
            client=client,
            request_messages=log_request_messages,
            compressed_messages=log_compressed_messages,
            savings_metadata=savings_metadata,
            # Per-source savings typed fields (High-23 fix).
            semantic_cache_avoided_tokens=semantic_cache_avoided_tokens,
            self_hosted_prefix_cache_hits=self_hosted_prefix_cache_hits,
            model_routing_tokens_saved=model_routing_tokens_saved,
            model_routing_usd_saved=model_routing_usd_saved,
            ccr_references=ccr_references,
        )


# ── The funnel ───────────────────────────────────────────────────────


def _build_savings_breakdown(
    outcome: RequestOutcome,
) -> tuple[
    dict[str, int],
    dict[str, float],
    RequestSavingsBreakdown | None,
]:
    """Merge the tracked savings sources on a ``RequestOutcome`` into a
    by-source dict, a by-source USD dict, and the breakdown object.

    The funnel calls this once so the Prometheus / SavingsTracker
    persistence path and the cost_tracker orchestrator see the same
    numbers. Handlers do not call this directly — they set the typed
    fields on the outcome (``cache_read_tokens``,
    ``semantic_cache_avoided_tokens``, etc.) and let the funnel do the
    merge.
    """
    # A protocol-only response event can legitimately have no usage, savings,
    # or request payload (for example a bare ``response.completed`` frame on
    # a Codex WebSocket). Do not cold-import the savings package just to
    # construct an all-zero breakdown; callers receive the same empty maps
    # and no cost-ledger entry would be emitted for it.
    if (
        outcome.original_tokens == 0
        and outcome.optimized_tokens == 0
        and outcome.output_tokens == 0
        and outcome.tokens_saved == 0
        and outcome.cache_read_tokens == 0
        and outcome.cache_write_tokens == 0
        and outcome.semantic_cache_avoided_tokens == 0
        and outcome.self_hosted_prefix_cache_hits == 0
        and outcome.model_routing_tokens_saved == 0
        and outcome.model_routing_usd_saved == 0
        and outcome.memoization_tokens_saved == 0
        and outcome.memoization_hits == 0
        and outcome.output_optimization_tokens_saved == 0
        and outcome.batch_routing_tokens_saved == 0
        and outcome.batch_routing_usd_saved == 0
        and not outcome.savings_metadata
    ):
        return {}, {}, None

    from cutctx.savings import (
        RequestSavingsBreakdown,
        SavingsSource,
    )

    semantic_tokens = int(outcome.semantic_cache_avoided_tokens or 0)
    self_hosted_tokens = int(outcome.self_hosted_prefix_cache_hits or 0)
    routing_applied = False
    model_routing_tokens = int(outcome.model_routing_tokens_saved or 0)
    model_routing_usd = float(outcome.model_routing_usd_saved or 0.0)
    provider_cache_tokens = int(outcome.cache_read_tokens or 0)
    memoization_tokens = int(outcome.memoization_tokens_saved or 0)
    memoization_hits = int(outcome.memoization_hits or 0)
    output_optimization_tokens = int(outcome.output_optimization_tokens_saved or 0)
    batch_routing_tokens = int(outcome.batch_routing_tokens_saved or 0)
    batch_routing_usd = float(outcome.batch_routing_usd_saved or 0.0)

    # Promote savings_metadata to the typed fields BEFORE the
    # residual calculation. The audit (production-audit-2026-06-20.md)
    # found that handlers that only set savings_metadata (not the
    # typed fields) led to over-attribution: prefix_cache_self_hosted
    # and model_routing were added on top of an undiminished
    # cutctx_compression residual, double-counting up to 100% of
    # total tokens_saved. The fix promotes metadata values into
    # the typed fields so the residual calculation subtracts them
    # correctly.
    extra_meta = outcome.savings_metadata or {}
    if isinstance(extra_meta, dict):
        # Self-hosted prefix cache tokens
        sh_meta = extra_meta.get("prefix_cache_self_hosted") or extra_meta.get("vllm_apc")
        if isinstance(sh_meta, dict):
            sh_tokens = int(sh_meta.get("tokens", 0) or 0)
            if sh_tokens > self_hosted_tokens:
                self_hosted_tokens = sh_tokens
        # Model routing tokens / USD
        mr_meta = extra_meta.get("model_routing")
        if isinstance(mr_meta, dict):
            model_routing_tokens = int(outcome.model_routing_tokens_saved or 0)
            model_routing_usd = float(outcome.model_routing_usd_saved or 0.0)
            source_model = str(mr_meta.get("source_model") or "").strip()
            target_model = str(mr_meta.get("target_model") or "").strip()
            routing_applied = bool(
                source_model
                and target_model
                and source_model != target_model
                and _models_equivalent(outcome.model, target_model)
            )
            mr_tokens = max(
                int(mr_meta.get("tokens", 0) or 0),
                int(mr_meta.get("tokens_routed", 0) or 0),
                int(mr_meta.get("tokens_saved", 0) or 0),
            )
            mr_usd = max(
                float(mr_meta.get("usd", 0.0) or 0.0),
                float(mr_meta.get("usd_saved", 0.0) or 0.0),
            )
            # Upstream gateways may report model-routing savings even when the
            # local router retained the requested model.  Keep that explicit
            # telemetry instead of treating local source==target observability
            # fields as an instruction to discard it.
            if routing_applied or not (source_model or target_model) or mr_tokens > 0 or mr_usd > 0:
                if mr_tokens > model_routing_tokens:
                    model_routing_tokens = mr_tokens
                if mr_usd > model_routing_usd:
                    model_routing_usd = mr_usd
        # Semantic cache tokens
        sc_meta = extra_meta.get("semantic_cache") or extra_meta.get("gptcache")
        if isinstance(sc_meta, dict):
            sc_tokens = int(sc_meta.get("tokens", 0) or 0)
            if sc_tokens > semantic_tokens:
                semantic_tokens = sc_tokens

    breakdown = RequestSavingsBreakdown(
        raw_input_tokens=int(outcome.original_tokens or 0),
        post_cutctx_tokens=int(outcome.optimized_tokens or 0),
        provider_cached_tokens=provider_cache_tokens,
        semantic_cache_avoided_tokens=semantic_tokens,
        total_tokens_saved=int(outcome.tokens_saved or 0),
    )

    by_source_tokens: dict[str, int] = {}
    by_source_usd: dict[str, float] = {}

    # 1. Provider prompt cache.
    if provider_cache_tokens > 0:
        breakdown.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, provider_cache_tokens)
        by_source_tokens[SavingsSource.PROVIDER_PROMPT_CACHE.value] = provider_cache_tokens

    # Track already-attributed tokens so the Cutctx bucket does not
    # double-count when the same tokens are also a cache hit, a
    # semantic hit, a self-hosted hit, or a routed model hit.
    already_accounted = (
        provider_cache_tokens + semantic_tokens + self_hosted_tokens + model_routing_tokens
    )

    # 2. Cutctx compression.
    if breakdown.total_tokens_saved > 0:
        cutctx_tokens = max(0, breakdown.total_tokens_saved - already_accounted)
        if cutctx_tokens > 0:
            breakdown.by_source.add(SavingsSource.CUTCTX_COMPRESSION, cutctx_tokens)
            by_source_tokens[SavingsSource.CUTCTX_COMPRESSION.value] = cutctx_tokens

    # 3. Semantic cache.
    if semantic_tokens > 0:
        breakdown.by_source.add(SavingsSource.SEMANTIC_CACHE, semantic_tokens)
        by_source_tokens[SavingsSource.SEMANTIC_CACHE.value] = semantic_tokens

    # 4. Self-hosted prefix cache (vLLM APC, etc.).
    if self_hosted_tokens > 0:
        breakdown.by_source.add(SavingsSource.PREFIX_CACHE_SELF_HOSTED, self_hosted_tokens)
        by_source_tokens[SavingsSource.PREFIX_CACHE_SELF_HOSTED.value] = self_hosted_tokens

    # 5. Model routing (tokens + USD).
    if model_routing_tokens > 0 or model_routing_usd > 0:
        breakdown.by_source.add(
            SavingsSource.MODEL_ROUTING,
            model_routing_tokens,
            model_routing_usd,
        )
        by_source_tokens[SavingsSource.MODEL_ROUTING.value] = model_routing_tokens
        if model_routing_usd > 0:
            by_source_usd[SavingsSource.MODEL_ROUTING.value] = model_routing_usd

    # 6. Memoization (WS11).
    if memoization_hits > 0 or memoization_tokens > 0:
        breakdown.by_source.add(SavingsSource.MEMOIZATION, memoization_tokens)
        by_source_tokens[SavingsSource.MEMOIZATION.value] = memoization_tokens

    # 7. Output optimization (WS10).
    if output_optimization_tokens > 0:
        breakdown.by_source.add(SavingsSource.OUTPUT_OPTIMIZATION, output_optimization_tokens)
        by_source_tokens[SavingsSource.OUTPUT_OPTIMIZATION.value] = output_optimization_tokens

    # 8. Batch routing (WS13) — tokens + USD.
    if batch_routing_tokens > 0 or batch_routing_usd > 0:
        breakdown.by_source.add(
            SavingsSource.BATCH_ROUTING,
            batch_routing_tokens,
            batch_routing_usd,
        )
        by_source_tokens[SavingsSource.BATCH_ROUTING.value] = batch_routing_tokens
        if batch_routing_usd > 0:
            by_source_usd[SavingsSource.BATCH_ROUTING.value] = batch_routing_usd

    # 9. Escape hatch: extra sources via savings_metadata dict.
    # The promotion block above already merged the typed fields
    # with the metadata values, so by the time we reach this block,
    # any source that the metadata also named is already accounted
    # for in the typed fields. We must NOT add the metadata again
    # or the per-source totals would be double-counted. To avoid
    # double-counting, we track which sources were promoted (i.e.
    # the metadata carried a value larger than the typed field)
    # and skip the escape-hatch add for those sources.
    promoted_sources: set[str] = set()
    if isinstance(extra_meta, dict):
        for raw_name, payload in extra_meta.items():
            if not isinstance(payload, dict):
                continue
            tokens = int(payload.get("tokens", 0) or 0)
            usd = float(payload.get("usd", 0.0) or 0.0)
            if tokens > 0 or usd > 0:
                promoted_sources.add(str(raw_name).strip().lower())
            if tokens > 0:
                # Map alias → canonical.
                canonical = str(raw_name).strip().lower()
                if canonical == "vllm_apc":
                    promoted_sources.add("prefix_cache_self_hosted")
                elif canonical == "litellm":
                    promoted_sources.add("provider_prompt_cache")
                elif canonical == "gptcache":
                    promoted_sources.add("semantic_cache")

    extra = outcome.savings_metadata or {}
    if isinstance(extra, dict):
        for raw_name, payload in extra.items():
            if not isinstance(payload, dict):
                continue
            try:
                src = SavingsSource.from_str(str(raw_name))
            except Exception:
                src = SavingsSource.CUTCTX_COMPRESSION
            tokens = int(payload.get("tokens", 0) or 0)
            usd = float(payload.get("usd", 0.0) or 0.0)
            if tokens <= 0 and usd <= 0:
                continue
            # If the typed-field promotion block already accounted
            # for this source, skip the escape-hatch add to avoid
            # double-counting. The exception is cutctx_compression
            # which is the RESIDUAL — for that source, the escape
            # hatch can re-attribute tokens that were already
            # counted in the residual.
            canonical = src.value
            if (
                canonical in promoted_sources
                and canonical != SavingsSource.CUTCTX_COMPRESSION.value
            ):
                # Already accounted via the promotion block.
                # Only the USD value, if not already in by_source_usd,
                # needs adding (the typed-field promotion only
                # captured model_routing usd).
                if usd > 0 and canonical == SavingsSource.MODEL_ROUTING.value:
                    if by_source_usd.get(canonical, 0.0) < usd:
                        by_source_usd[canonical] = usd
                continue
            # If the extra source re-attributes tokens that were
            # already counted in the Cutctx bucket, roll them back so
            # the extra source is the only place that gets credit.
            if tokens > 0 and (
                src == SavingsSource.CUTCTX_COMPRESSION
                or src.value in _CUTCTX_REATTRIBUTABLE_SOURCES
            ):
                cutctx_bucket = breakdown.by_source.get_tokens(SavingsSource.CUTCTX_COMPRESSION)
                if cutctx_bucket >= tokens:
                    breakdown.by_source.add(SavingsSource.CUTCTX_COMPRESSION, -tokens)
                    by_source_tokens[SavingsSource.CUTCTX_COMPRESSION.value] = (
                        by_source_tokens.get(SavingsSource.CUTCTX_COMPRESSION.value, 0) - tokens
                    )
            breakdown.by_source.add(src, tokens, usd)
            by_source_tokens[src.value] = by_source_tokens.get(src.value, 0) + tokens
            if usd > 0:
                by_source_usd[src.value] = by_source_usd.get(src.value, 0.0) + usd

    from cutctx.proxy.savings_pricing import value_tokens_usd

    for source, tokens in by_source_tokens.items():
        if source not in by_source_usd and tokens > 0:
            usd_val = value_tokens_usd(outcome.model, tokens)
            if usd_val > 0:
                by_source_usd[source] = usd_val

    return by_source_tokens, by_source_usd, breakdown


async def emit_request_outcome(handler: Any, outcome: RequestOutcome) -> None:
    """Single funnel for per-request bookkeeping. The contract.

    Owns the four downstream effects in canonical order:

      1. ``handler.metrics.record_request(...)`` — Prometheus / SavingsTracker
      2. ``handler.cost_tracker.record_tokens(...)`` — cost dashboard
         (skipped when cost_tracker is None, i.e. ``--no-cost``)
      3. ``handler.logger.log(RequestLog(...))`` — per-request log feed
         (skipped when logger is None, i.e. ``--no-request-logging``)
      4. structured PERF log line — consumed by ``cutctx perf``

    Takes the handler as a free argument rather than ``self`` so this
    function is callable from:
    * ``CutctxProxy._record_request_outcome`` (production)
    * any test dummy that has the three required attributes
      (``metrics``, ``cost_tracker``, optionally ``logger``)
    * any provider handler mixin

    The handler argument is structurally typed (duck-typed); no formal
    Protocol — the requirement is simply that ``handler.metrics`` exists
    and is awaitable-compatible. We could lift this to a typing.Protocol
    if/when another contract surface emerges, but YAGNI.
    """
    # Audit-Deep-2026-06-21 Blocker 1: when the ModelRouter is enabled
    # and a routing decision was made (signaled by savings_metadata carrying
    # a "model_routing" entry with target_model), populate the typed
    # model_routing_* fields. This was previously dead code: the
    # ModelRouter was bound to proxy._model_router at server boot but
    # never invoked from the request path, so the model's
    # model_routing_tokens_saved and model_routing_usd_saved sources
    # were structurally zero in production.
    if getattr(handler, "_model_router", None) is not None:
        try:
            sm = outcome.savings_metadata or {}
            if "model_routing" in sm:
                meta = sm["model_routing"]
                source_model = str(meta.get("source_model", "")).strip()
                target_model = str(meta.get("target_model", "")).strip()
                routing_applied = bool(
                    source_model
                    and target_model
                    and source_model != target_model
                    and _models_equivalent(outcome.model, target_model)
                )
                # If the handler attached placeholder zeros, finalize
                # the savings now using the actual input-token count.
                tokens_saved = int(meta.get("tokens_saved", 0))
                usd_saved = float(meta.get("usd_saved", 0.0))
                if routing_applied and tokens_saved == 0 and usd_saved == 0.0:
                    try:
                        # Re-derive the decision and finalize with the
                        # actual token count.
                        from cutctx.proxy.model_router import (
                            RoutingDecision,
                        )

                        # The model router uses a Decision internally;
                        # we synthesize a placeholder to call
                        # finalize_savings with the real token count.
                        decision = RoutingDecision(
                            source_model=source_model,
                            target_model=target_model,
                            routing_applied=True,
                            reason=meta.get("reason", ""),
                        )
                        input_tokens = int(
                            outcome.attempted_input_tokens or outcome.optimized_tokens or 0
                        )
                        if input_tokens > 0:
                            finalized = handler._model_router.finalize_savings(
                                decision,
                                input_tokens=input_tokens,
                                output_tokens=int(outcome.output_tokens or 0),
                            )
                            tokens_saved = int(getattr(finalized, "tokens_saved", 0) or 0)
                            usd_saved = float(getattr(finalized, "usd_saved", 0.0) or 0.0)
                    except Exception:
                        # Router not usable here (e.g. LiteLLM not
                        # installed in tests). Leave at 0.
                        tokens_saved = 0
                        usd_saved = 0.0
                if (
                    routing_applied
                    and (tokens_saved > 0 or usd_saved > 0.0)
                    and (outcome.model_routing_tokens_saved == 0)
                ):
                    # Mutate a copy so we don't poison caller state.
                    from dataclasses import replace as _dc_replace

                    outcome = _dc_replace(
                        outcome,
                        model_routing_tokens_saved=tokens_saved,
                        model_routing_usd_saved=usd_saved,
                    )
        except Exception:
            # The model router is best-effort; never let a failure
            # here poison the funnel.
            pass

    # Project attribution: explicit outcome field wins, else the value the
    # HTTP middleware / WS accept captured from ``X-Cutctx-Project``.
    project = outcome.project
    if project is None:
        # Defer request-attribution imports from the stream-completion hot
        # path until middleware attribution is actually needed.
        from cutctx.proxy.project_context import get_current_project

        project = get_current_project()

    # Phase 1.3 + 1.4: build the unified savings breakdown once so
    # both step 1 (Prometheus / SavingsTracker persistence) and
    # step 2a (cost_tracker orchestrator) see the same numbers. This
    # is the only place in the code path that knows how to merge the
    # tracked savings sources; handlers just set the typed fields.
    _savings_by_source_tokens, _savings_by_source_usd, _savings_meta = _build_savings_breakdown(
        outcome
    )
    created_savings_tokens = sum(
        value
        for source, value in _savings_by_source_tokens.items()
        if source not in _OBSERVED_PROVIDER_SOURCES
    )
    observed_provider_savings_tokens = sum(
        value
        for source, value in _savings_by_source_tokens.items()
        if source in _OBSERVED_PROVIDER_SOURCES
    )
    created_savings_usd = sum(
        value
        for source, value in _savings_by_source_usd.items()
        if source not in _OBSERVED_PROVIDER_SOURCES
    )
    observed_provider_savings_usd = sum(
        value
        for source, value in _savings_by_source_usd.items()
        if source in _OBSERVED_PROVIDER_SOURCES
    )
    eligible_input_tokens = max(
        0,
        int(
            outcome.eligible_input_tokens
            or outcome.attempted_input_tokens
            or outcome.original_tokens
        ),
    )
    cache_protected_tokens = max(
        0,
        int(outcome.cache_protected_tokens or outcome.cache_read_tokens),
    )
    compressed_tokens = max(
        0,
        int(outcome.compressed_tokens or (outcome.original_tokens - outcome.optimized_tokens)),
    )
    decline_reason = normalize_decline_reason(
        outcome.decline_reason
        or outcome.tags.get("decline_reason")
        or outcome.tags.get("passthrough_reason")
    )
    canary_meta = (outcome.savings_metadata or {}).get("savings_canary") or {}
    canary_arm = (
        str(canary_meta.get("arm") or outcome.canary_arm or "control")
        if isinstance(canary_meta, dict)
        else outcome.canary_arm
    )
    canary_eligible = (
        bool(canary_meta.get("eligible"))
        if isinstance(canary_meta, dict) and "eligible" in canary_meta
        else outcome.canary_eligible
    )
    canary_enabled = bool(canary_meta.get("enabled")) if isinstance(canary_meta, dict) else False
    canary_identity_source = (
        str(canary_meta.get("assignment_identity_source") or "unknown")
        if isinstance(canary_meta, dict)
        else "unknown"
    )
    canary_assignment_sticky = (
        bool(canary_meta.get("assignment_sticky")) if isinstance(canary_meta, dict) else False
    )
    audit_meta = (outcome.savings_metadata or {}).get("ghost_token_audit") or {}
    scaffolding_tokens = max(
        0,
        int(
            getattr(outcome, "scaffolding_tokens", 0)
            or audit_meta.get("scaffolding_tokens", 0)
            or 0
        ),
    )
    ghost_tokens = max(
        0,
        int(getattr(outcome, "ghost_tokens", 0) or audit_meta.get("ghost_tokens", 0) or 0),
    )

    # 1. Prometheus / SavingsTracker.
    await handler.metrics.record_request(
        provider=outcome.provider,
        model=outcome.model,
        input_tokens=outcome.optimized_tokens,
        output_tokens=outcome.output_tokens,
        tokens_saved=outcome.tokens_saved,
        latency_ms=outcome.total_latency_ms,
        cached=outcome.cache_hit,
        overhead_ms=outcome.overhead_ms,
        ttfb_ms=outcome.ttfb_ms,
        pipeline_timing=outcome.pipeline_timing,
        waste_signals=outcome.waste_signals,
        cache_read_tokens=outcome.cache_read_tokens,
        cache_write_tokens=outcome.cache_write_tokens,
        cache_write_5m_tokens=outcome.cache_write_5m_tokens,
        cache_write_1h_tokens=outcome.cache_write_1h_tokens,
        uncached_input_tokens=outcome.uncached_input_tokens,
        attempted_input_tokens=outcome.attempted_input_tokens,
        scaffolding_tokens=scaffolding_tokens,
        ghost_tokens=ghost_tokens,
        project=project,
        client=outcome.client,
        # Phase 1.4: extra savings sources.
        semantic_cache_avoided_tokens=int(outcome.semantic_cache_avoided_tokens or 0),
        self_hosted_prefix_cache_hits=int(outcome.self_hosted_prefix_cache_hits or 0),
        model_routing_tokens_saved=int(outcome.model_routing_tokens_saved or 0),
        model_routing_usd_saved=float(outcome.model_routing_usd_saved or 0.0),
        savings_by_source_tokens=_savings_by_source_tokens,
        cache_savings_usd_delta=_savings_by_source_usd.get("provider_prompt_cache"),
        compression_savings_usd_delta=_savings_by_source_usd.get("cutctx_compression"),
        semantic_cache_usd_delta=_savings_by_source_usd.get("semantic_cache"),
        self_hosted_prefix_cache_usd_delta=_savings_by_source_usd.get("prefix_cache_self_hosted"),
        model_routing_usd_delta=_savings_by_source_usd.get("model_routing"),
        tool_schema_compaction_usd_delta=_savings_by_source_usd.get("tool_schema_compaction"),
        api_surface_slimming_usd_delta=_savings_by_source_usd.get("api_surface_slimming"),
        savings_by_source_usd=_savings_by_source_usd,
        created_savings_tokens=created_savings_tokens,
        observed_provider_savings_tokens=observed_provider_savings_tokens,
        eligible_input_tokens=eligible_input_tokens,
        cache_protected_tokens=cache_protected_tokens,
        compressed_tokens=compressed_tokens,
        decline_reason=decline_reason,
        savings_basis=outcome.savings_basis,
        pricing_basis=outcome.pricing_basis,
    )

    # Canary evaluation is fed from the same reconciled per-request values
    # that persistence and the dashboard consume.
    try:
        from cutctx.proxy.savings_canary import get_savings_canary_coordinator

        if canary_enabled and canary_eligible and canary_assignment_sticky:
            get_savings_canary_coordinator().record(
                canary_arm,
                input_tokens=outcome.optimized_tokens,
                created_savings_usd=created_savings_usd,
                observed_provider_savings_usd=observed_provider_savings_usd,
                quality_success=outcome.quality_success,
                retries=outcome.retry_count,
                user_corrections=outcome.user_corrections,
                latency_ms=outcome.total_latency_ms,
            )
    except Exception:
        logger.debug("Savings canary observation failed", exc_info=True)

    # 2. Cost tracker (optional).
    cost_tracker = getattr(handler, "cost_tracker", None)
    if cost_tracker is not None:
        cost_tracker.record_tokens(
            outcome.model,
            outcome.tokens_saved,
            outcome.optimized_tokens,
            cache_read_tokens=outcome.cache_read_tokens,
            cache_write_tokens=outcome.cache_write_tokens,
            cache_write_5m_tokens=outcome.cache_write_5m_tokens,
            cache_write_1h_tokens=outcome.cache_write_1h_tokens,
            uncached_tokens=outcome.uncached_input_tokens,
        )

        # 2a. Phase 1.3 + 1.4: per-request savings breakdown into the
        # unified ledger. The breakdown was already built by
        # ``_build_savings_breakdown`` at the top of the funnel; we just
        # hand it to the cost_tracker orchestrator here. Both this
        # step and step 1 (Prometheus / SavingsTracker persistence)
        # see the same numbers because they share the dict.
        if _savings_meta is not None and (
            _savings_meta.has_any_savings or _savings_meta.raw_input_tokens > 0
        ):
            cost_tracker.record_savings_breakdown(
                _savings_meta,
                provider=outcome.provider,
                model=outcome.model,
                client=outcome.client,
            )

    # 3. Per-request log (optional). The ``client`` outcome field is
    #    copied into ``tags["client"]`` so the dashboard's existing
    #    tag-based filtering surfaces per-harness slicing for free —
    #    no new RequestLog column needed. The original ``outcome.tags``
    #    dict is not mutated (frozen dataclass + defensive copy).
    request_logger = getattr(handler, "logger", None)
    if request_logger is not None:
        log_tags = dict(outcome.tags)
        if outcome.client:
            log_tags["client"] = outcome.client
        if project:
            log_tags["project"] = project
        cache_saved_tokens = max(0, int(outcome.cache_read_tokens))
        semantic_cache_saved_tokens = max(0, int(outcome.semantic_cache_avoided_tokens))
        self_hosted_prefix_cache_saved_tokens = max(0, int(outcome.self_hosted_prefix_cache_hits))
        model_routing_saved_tokens = max(0, int(outcome.model_routing_tokens_saved))
        tool_schema_saved_tokens = max(
            0,
            int(
                ((outcome.savings_metadata or {}).get("tool_schema_compaction") or {}).get(
                    "tokens",
                    0,
                )
                or 0
            ),
        )
        total_saved_tokens = (
            max(0, int(outcome.tokens_saved))
            + cache_saved_tokens
            + semantic_cache_saved_tokens
            + self_hosted_prefix_cache_saved_tokens
            + model_routing_saved_tokens
        )
        total_savings_percent = (
            (total_saved_tokens / outcome.original_tokens) * 100.0
            if outcome.original_tokens > 0
            else 0.0
        )
    request_cost_usd: float | None = None
    if cost_tracker is not None:
        if outcome.from_response_cache:
            request_cost_usd = 0.0
        else:
            uncached_input_tokens = max(0, int(outcome.uncached_input_tokens))
            cache_read_tokens = max(0, int(outcome.cache_read_tokens))
            cache_write_tokens = max(0, int(outcome.cache_write_tokens))
            input_tokens_for_cost = uncached_input_tokens

            # Fall back to the optimized prompt tokens when the provider
            # did not report cache split counters for this request.
            if input_tokens_for_cost <= 0 and cache_read_tokens <= 0 and cache_write_tokens <= 0:
                input_tokens_for_cost = max(0, int(outcome.optimized_tokens))

            request_cost_usd = cost_tracker.estimate_cost(
                outcome.model,
                input_tokens_for_cost,
                max(0, int(outcome.output_tokens)),
                cache_read_tokens=cache_read_tokens,
                cache_write_tokens=cache_write_tokens,
            )

    if request_logger is not None:
        # RequestLog imports optional provider-facing configuration. It is
        # only needed when per-request persistence is enabled.
        from cutctx.proxy.models import RequestLog

        routing_meta = None
        model_routing_meta = (outcome.savings_metadata or {}).get("model_routing") or {}
        if isinstance(model_routing_meta, dict) and model_routing_meta:
            source_model = str(model_routing_meta.get("source_model") or "").strip()
            target_model = str(model_routing_meta.get("target_model") or outcome.model).strip()
            routing_applied = bool(
                source_model
                and target_model
                and source_model != target_model
                and _models_equivalent(outcome.model, target_model)
            )
            routing_meta = {
                "requested_model": source_model or outcome.model,
                "actual_model": outcome.model,
                "routed": routing_applied,
                "source_model": source_model or outcome.model,
                "target_model": target_model or outcome.model,
                "reason": model_routing_meta.get("reason"),
                "request_overrides": model_routing_meta.get("request_overrides") or None,
                "saved_tokens": model_routing_saved_tokens,
                "saved_usd": float(outcome.model_routing_usd_saved or 0.0),
            }

        fallback_meta = None
        fallback_reason = log_tags.get("fallback_reason") or log_tags.get("fallback_error")
        fallback_attempted = log_tags.get("fallback_attempted")
        fallback_provider = log_tags.get("fallback_provider") or log_tags.get("upstream_provider")
        fallback_meta_candidate: dict[str, Any] = {}
        if fallback_provider not in (None, ""):
            fallback_meta_candidate["provider"] = fallback_provider
        if fallback_reason not in (None, ""):
            fallback_meta_candidate["reason"] = fallback_reason
        if fallback_attempted is not None:
            fallback_meta_candidate["attempted"] = str(fallback_attempted).lower() == "true"
        circuit_state = log_tags.get("circuit_breaker_state")
        if circuit_state not in (None, ""):
            fallback_meta_candidate["circuit_breaker_state"] = circuit_state
        circuit_retry_after = log_tags.get("circuit_breaker_retry_after_s")
        if circuit_retry_after not in (None, ""):
            try:
                fallback_meta_candidate["circuit_breaker_retry_after_s"] = float(
                    circuit_retry_after
                )
            except (TypeError, ValueError):
                pass
        circuit_failures = log_tags.get("circuit_breaker_consecutive_failures")
        if circuit_failures not in (None, ""):
            try:
                fallback_meta_candidate["circuit_breaker_consecutive_failures"] = int(
                    circuit_failures
                )
            except (TypeError, ValueError):
                pass
        active_provider = log_tags.get("failover_active_provider")
        if active_provider not in (None, ""):
            fallback_meta_candidate["active_provider"] = active_provider
        active_base_url = log_tags.get("failover_active_base_url")
        if active_base_url not in (None, ""):
            fallback_meta_candidate["active_base_url"] = active_base_url
        active_healthy = log_tags.get("failover_active_healthy")
        if active_healthy not in (None, ""):
            fallback_meta_candidate["active_healthy"] = str(active_healthy).lower() == "true"
        if fallback_meta_candidate:
            fallback_meta = fallback_meta_candidate

        cache_protection_evaluated = bool(
            outcome.cache_protection_evaluated or eligible_input_tokens > 0
        )
        payload_capture = (
            "captured" if getattr(request_logger, "log_full_messages", False) else "disabled"
        )
        try:
            extra_metadata = outcome.savings_metadata or {}
            routing_trace = extra_metadata.get("model_routing_trace")
            decision_receipt = build_decision_receipt(
                {
                    "request_id": outcome.request_id,
                    "requested_model": (routing_meta or {}).get("requested_model") or outcome.model,
                    "effective_model": outcome.model,
                    "routing_trace": routing_trace if isinstance(routing_trace, dict) else None,
                    "routing_summary": routing_meta,
                    "input_tokens_original": outcome.original_tokens,
                    "input_tokens_forwarded": outcome.optimized_tokens,
                    "direct_tokens_saved": _savings_by_source_tokens.get("cutctx_compression", 0),
                    "transforms": list(outcome.transforms_applied),
                    "decline_reason": decline_reason,
                    "cache_protected_tokens": cache_protected_tokens,
                    "cache_protection_evaluated": cache_protection_evaluated,
                    "provider_cache_observed": outcome.provider_cache_observed,
                    "provider_cache_read_tokens": outcome.cache_read_tokens,
                    "provider_cache_write_tokens": outcome.cache_write_tokens,
                    "provider_cache_inferred": outcome.cache_inferred,
                    "semantic_cache_evaluated": bool(
                        outcome.semantic_cache_evaluated
                        or outcome.semantic_cache_hit
                        or outcome.from_response_cache
                    ),
                    "semantic_cache_hit": outcome.semantic_cache_hit or outcome.from_response_cache,
                    "semantic_cache_saved_tokens": semantic_cache_saved_tokens,
                    "prefix_cache_evaluated": bool(
                        outcome.self_hosted_prefix_cache_evaluated
                        or self_hosted_prefix_cache_saved_tokens > 0
                    ),
                    "prefix_cache_saved_tokens": self_hosted_prefix_cache_saved_tokens,
                    "ccr_references": list(outcome.ccr_references),
                    "ccr_retrieval_outcome": outcome.ccr_retrieval_outcome,
                    "total_saved_tokens": total_saved_tokens,
                    "created_savings_tokens": created_savings_tokens,
                    "observed_provider_savings_tokens": observed_provider_savings_tokens,
                    "by_source_tokens": dict(_savings_by_source_tokens),
                    "by_source_usd": dict(_savings_by_source_usd),
                    "savings_basis": outcome.savings_basis,
                    "pricing_basis": outcome.pricing_basis,
                },
                config=getattr(handler, "config", None),
                payload_capture=payload_capture,
            )
        except Exception as exc:
            logger.warning(
                "[%s] decision receipt construction failed type=%s",
                outcome.request_id,
                type(exc).__name__,
            )
            decision_receipt = build_minimal_decision_receipt(
                outcome.request_id,
                payload_capture=payload_capture,
                failure="receipt_builder_failed",
            )

        request_logger.log(
            RequestLog(
                request_id=outcome.request_id,
                timestamp=datetime.now().isoformat(),
                provider=outcome.provider,
                model=outcome.model,
                input_tokens_original=outcome.original_tokens,
                input_tokens_optimized=outcome.optimized_tokens,
                output_tokens=outcome.output_tokens,
                tokens_saved=outcome.tokens_saved,
                savings_percent=outcome.savings_pct,
                optimization_latency_ms=outcome.overhead_ms,
                total_latency_ms=outcome.total_latency_ms,
                tags=log_tags,
                cache_hit=outcome.cache_hit,
                transforms_applied=list(outcome.transforms_applied),
                cache_saved_tokens=cache_saved_tokens,
                provider_cache_observed=outcome.provider_cache_observed,
                provider_cache_write_tokens=max(0, int(outcome.cache_write_tokens)),
                provider_cache_inferred=outcome.cache_inferred,
                semantic_cache_saved_tokens=semantic_cache_saved_tokens,
                semantic_cache_evaluated=bool(
                    outcome.semantic_cache_evaluated
                    or outcome.semantic_cache_hit
                    or outcome.from_response_cache
                ),
                self_hosted_prefix_cache_saved_tokens=self_hosted_prefix_cache_saved_tokens,
                self_hosted_prefix_cache_evaluated=bool(
                    outcome.self_hosted_prefix_cache_evaluated
                    or self_hosted_prefix_cache_saved_tokens > 0
                ),
                cache_protection_evaluated=cache_protection_evaluated,
                model_routing_saved_tokens=model_routing_saved_tokens,
                tool_schema_saved_tokens=tool_schema_saved_tokens,
                scaffolding_tokens=scaffolding_tokens,
                ghost_tokens=ghost_tokens,
                total_saved_tokens=total_saved_tokens,
                total_savings_percent=total_savings_percent,
                request_cost_usd=request_cost_usd,
                savings_by_source_tokens=dict(_savings_by_source_tokens),
                savings_by_source_usd=dict(_savings_by_source_usd),
                waste_signals=outcome.waste_signals,
                pipeline_timing=outcome.pipeline_timing,
                decline_reason=decline_reason,
                routing_metadata=routing_meta,
                fallback=fallback_meta,
                ccr_references=list(outcome.ccr_references),
                ccr_retrieval_outcome=outcome.ccr_retrieval_outcome,
                decision_receipt=decision_receipt,
                created_savings_tokens=created_savings_tokens,
                observed_provider_savings_tokens=observed_provider_savings_tokens,
                created_savings_usd=created_savings_usd,
                observed_provider_savings_usd=observed_provider_savings_usd,
                savings_basis=outcome.savings_basis,
                pricing_basis=outcome.pricing_basis,
                opportunity_funnel={
                    "eligible_input_tokens": eligible_input_tokens,
                    "cache_protected_tokens": cache_protected_tokens,
                    "compressed_tokens": compressed_tokens,
                    "declined_tokens": max(
                        eligible_input_tokens - cache_protected_tokens - compressed_tokens,
                        0,
                    ),
                },
                canary={
                    "arm": canary_arm,
                    "eligible": canary_eligible,
                    "enabled": canary_enabled,
                    "assignment_identity_source": canary_identity_source,
                    "assignment_sticky": canary_assignment_sticky,
                },
                request_messages=outcome.request_messages,
                compressed_messages=outcome.compressed_messages,
                turn_id=outcome.turn_id,
            )
        )

    # 4. Structured PERF log line. ``client=X`` is appended only when
    #    a harness was identified — keeps the unidentified-traffic
    #    line unchanged, and gives ``cutctx perf --client X``
    #    parsers a clean key to filter on.
    client_part = f" client={outcome.client}" if outcome.client else ""
    logger.info(
        f"[{outcome.request_id}] PERF "
        f"model={outcome.model} msgs={outcome.num_messages} "
        f"tok_before={outcome.original_tokens} tok_after={outcome.optimized_tokens} "
        f"tok_saved={outcome.tokens_saved} "
        f"cache_read={outcome.cache_read_tokens} cache_write={outcome.cache_write_tokens} "
        f"cache_hit_pct={outcome.cache_hit_pct} "
        f"opt_ms={outcome.overhead_ms:.0f} "
        f"transforms={_summarize_transforms(list(outcome.transforms_applied))}"
        f"{client_part}"
    )

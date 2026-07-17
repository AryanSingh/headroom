"""Durable proxy savings and display-session tracking.

Persists cumulative proxy compression savings plus a canonical display session
window to a local JSON file so historical charts and dashboard session stats
survive proxy restarts and can be shared by multiple Cutctx frontends.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import logging
import os
import random
import re
import tempfile
import threading
import time
from collections.abc import Callable
from csv import DictWriter
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from cutctx import paths as _paths

logger = logging.getLogger(__name__)

CUTCTX_SAVINGS_PATH_ENV_VAR = _paths.CUTCTX_SAVINGS_PATH_ENV
DEFAULT_SAVINGS_DIR = ".cutctx"
DEFAULT_SAVINGS_FILE = "proxy_savings.json"
SCHEMA_VERSION = 6
DEFAULT_MAX_HISTORY_POINTS = 5000
DEFAULT_MAX_PROJECTS = 50
DEFAULT_MAX_MODELS = 50
DEFAULT_MAX_CLIENTS = 50
PROJECT_NAME_MAX_LENGTH = 128
DEFAULT_MAX_HISTORY_AGE_DAYS = 365
DEFAULT_MAX_RESPONSE_HISTORY_POINTS = 500
DEFAULT_DISPLAY_SESSION_INACTIVITY_MINUTES = 60
DEFAULT_SAVINGS_FLUSH_INTERVAL_SECONDS = 0.25

# Commercial-readiness runbook Task 1 (Savings Validation Protocol / shadow
# mode). Every normal per-request/history savings row is an *estimate*
# (token-count delta x list price). Shadow mode replays a sampled fraction
# of requests upstream with compression disabled and compares the actual
# provider-billed cost of the compressed vs. uncompressed call, recording
# that empirical comparison as a ``savings_basis="measured"`` data point
# alongside (never replacing) the normal ``"estimated"`` rows. Configuration
# is via environment variables, following the same pattern as
# ``circuit_breaker.py`` (no config-schema change):
#   * ``CUTCTX_SHADOW_MODE`` - "1"/"true"/"yes"/"on" enables shadow mode
#     (default: disabled).
#   * ``CUTCTX_SHADOW_SAMPLE_RATE`` - fraction (0.0-1.0) of eligible
#     requests to shadow-check (default 0.0, i.e. none even when enabled).
SAVINGS_BASIS_ESTIMATED = "estimated"
SAVINGS_BASIS_MEASURED = "measured"
DEFAULT_SHADOW_SAMPLE_RATE = 0.0
DEFAULT_MAX_SHADOW_CHECKS = 2000
OBSERVED_PROVIDER_SAVINGS_SOURCES = frozenset(
    {
        "provider_prompt_cache",
    }
)
_VERSION_SUFFIX_RE = re.compile(r"^(?P<base>.+?)-(?:(?:\d{4}-\d{2}-\d{2})|(?:\d{8}))$")


def _empty_opportunity_funnel() -> dict[str, Any]:
    return {
        "eligible_input_tokens": 0,
        "cache_protected_tokens": 0,
        "compressed_tokens": 0,
        "declined_tokens": 0,
        "decline_reasons": {},
    }


def _compression_pricing_candidates(model: str) -> list[str]:
    candidates: list[str] = []

    def add(candidate: str | None) -> None:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    def add_variants(value: str) -> None:
        add(value)
        if "/" in value:
            provider, stripped = value.split("/", 1)
            add(stripped)
            match = _VERSION_SUFFIX_RE.match(stripped)
            if match:
                add(f"{provider}/{match.group('base')}")
                add(match.group("base"))
        match = _VERSION_SUFFIX_RE.match(value)
        if match:
            add(match.group("base"))

    add_variants(model)
    if "/" not in model:
        match = _VERSION_SUFFIX_RE.match(model)
        base = match.group("base") if match else model
        for prefix in ("openai/", "anthropic/", "google/", "mistral/", "deepseek/"):
            add(f"{prefix}{model}")
            if base != model:
                add(f"{prefix}{base}")

    return candidates


def _coverage_payload(attributed: int, legacy: int) -> dict[str, Any]:
    total = max(0, int(attributed)) + max(0, int(legacy))
    percent = (max(0, int(attributed)) / total * 100.0) if total else 100.0
    return {
        "attributed_requests": max(0, int(attributed)),
        "legacy_unattributed_requests": max(0, int(legacy)),
        "coverage_percent": round(percent, 2),
        "complete": legacy == 0,
    }


def shadow_mode_enabled_from_env() -> bool:
    """Read ``CUTCTX_SHADOW_MODE`` (default: disabled)."""
    raw = os.environ.get("CUTCTX_SHADOW_MODE", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def shadow_sample_rate_from_env() -> float:
    """Read ``CUTCTX_SHADOW_SAMPLE_RATE`` (default 0.0), clamped to [0, 1]."""
    raw = os.environ.get("CUTCTX_SHADOW_SAMPLE_RATE")
    if not raw:
        return DEFAULT_SHADOW_SAMPLE_RATE
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "event=shadow_mode_bad_env var=CUTCTX_SHADOW_SAMPLE_RATE value=%r; using default %.2f",
            raw,
            DEFAULT_SHADOW_SAMPLE_RATE,
        )
        return DEFAULT_SHADOW_SAMPLE_RATE
    return min(max(value, 0.0), 1.0)


def should_run_shadow_check(
    sample_rate: float,
    rng: Callable[[], float] | None = None,
) -> bool:
    """Deterministic sampling decision for a shadow-mode duplicate upstream call.

    ``sample_rate`` <= 0 always returns ``False``; ``sample_rate`` >= 1
    always returns ``True`` (both short-circuit before drawing from
    ``rng``, so callers never need to inject an rng just to exercise the
    boundary cases). For a rate strictly between 0 and 1, ``rng`` — a
    zero-arg callable returning a value in ``[0, 1)`` — is compared
    against the rate. Defaults to ``random.random`` in production; tests
    inject any deterministic callable (e.g. ``lambda: 0.3``) instead of
    monkeypatching the ``random`` module, so the decision is exercised
    without real randomness.
    """
    rate = sample_rate if isinstance(sample_rate, int | float) else 0.0
    if rate <= 0.0:
        return False
    if rate >= 1.0:
        return True
    draw = (rng or random.random)()
    return draw < rate


PERSISTED_SAVINGS_SOURCES = (
    "provider_prompt_cache",
    "cutctx_compression",
    "tool_schema_compaction",
    "api_surface_slimming",
    "semantic_cache",
    "prefix_cache_self_hosted",
    "model_routing",
    "rtk_cli_filtering",
    "normalization",
    "memoization",
    "output_optimization",
    "batch_routing",
)

SESSION_SAVINGS_USD_FIELDS = (
    "cache_savings_usd",
    "cache_savings_observed_usd",
    "semantic_cache_savings_usd",
    "semantic_cache_savings_observed_usd",
    "self_hosted_prefix_cache_savings_usd",
    "self_hosted_prefix_cache_savings_observed_usd",
    "model_routing_savings_usd",
    "model_routing_savings_observed_usd",
    "tool_schema_compaction_savings_usd",
    "tool_schema_compaction_savings_observed_usd",
    "api_surface_slimming_savings_usd",
    "api_surface_slimming_savings_observed_usd",
    "normalization_savings_usd",
    "normalization_savings_observed_usd",
    "memoization_savings_usd",
    "memoization_savings_observed_usd",
    "output_optimization_savings_usd",
    "output_optimization_savings_observed_usd",
    "batch_routing_savings_usd",
    "batch_routing_savings_observed_usd",
)

LITELLM_AVAILABLE = importlib.util.find_spec("litellm") is not None
litellm: Any | None = None


def _get_litellm_module() -> Any | None:
    """Import LiteLLM only when cost metadata is requested."""
    global litellm

    if not LITELLM_AVAILABLE:
        return None
    if litellm is not None:
        return litellm

    try:
        import litellm as imported_litellm
    except Exception:
        # Broad on purpose: litellm's own internal circular-import bugs
        # surface here as AttributeError ("partially initialized module
        # 'litellm' has no attribute 'litellm_core_utils'"), not
        # ImportError — narrowly catching ImportError let that exception
        # propagate out of this best-effort, optional cost-estimation path
        # all the way up through record_request/emit_request_outcome and
        # crash the entire proxy process on essentially any live request
        # that needed a USD estimate. Losing the cost estimate for this
        # request is an acceptable degradation; losing the whole proxy
        # is not. (Reverted once already by a concurrent edit on
        # 2026-07-03 — if you're re-narrowing this, please read the
        # commit history for why it's broad before doing so again.)
        return None

    litellm = imported_litellm
    return litellm


def get_default_savings_storage_path() -> str:
    """Return the configured savings storage path."""
    # Preserve legacy behavior: when CUTCTX_SAVINGS_PATH is set we return
    # the raw string exactly as supplied (no tilde expansion, no
    # path-separator normalization) to match prior behavior and existing tests.
    env_path = os.environ.get(CUTCTX_SAVINGS_PATH_ENV_VAR, "").strip()
    if env_path:
        return env_path
    return str(_paths.savings_path())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _bucket_start(timestamp: datetime, bucket: str) -> datetime:
    if bucket == "hour":
        return timestamp.replace(minute=0, second=0, microsecond=0)
    if bucket == "day":
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "week":
        day_start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        return day_start - timedelta(days=day_start.weekday())
    if bucket == "month":
        return timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"Unsupported savings history bucket: {bucket}")


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return default


def _derive_created_and_observed_savings_usd(
    *,
    savings_by_source_usd: dict[str, float] | None = None,
    created_savings_usd: float | None = None,
    observed_provider_savings_usd: float | None = None,
    compression_savings_usd: float = 0.0,
    cache_savings_usd: float = 0.0,
    semantic_cache_savings_usd: float = 0.0,
    self_hosted_prefix_cache_savings_usd: float = 0.0,
    model_routing_savings_usd: float = 0.0,
    tool_schema_compaction_savings_usd: float = 0.0,
    api_surface_slimming_savings_usd: float = 0.0,
    normalization_savings_usd: float = 0.0,
    memoization_savings_usd: float = 0.0,
    output_optimization_savings_usd: float = 0.0,
    batch_routing_savings_usd: float = 0.0,
) -> tuple[float, float]:
    if isinstance(savings_by_source_usd, dict) and savings_by_source_usd:
        created = sum(
            _coerce_float(value)
            for source, value in savings_by_source_usd.items()
            if source not in OBSERVED_PROVIDER_SAVINGS_SOURCES
        )
        observed = sum(
            _coerce_float(value)
            for source, value in savings_by_source_usd.items()
            if source in OBSERVED_PROVIDER_SAVINGS_SOURCES
        )
        return round(created, 6), round(observed, 6)

    if created_savings_usd is not None or observed_provider_savings_usd is not None:
        return round(_coerce_float(created_savings_usd), 6), round(
            _coerce_float(observed_provider_savings_usd),
            6,
        )

    created = sum(
        (
            _coerce_float(compression_savings_usd),
            _coerce_float(self_hosted_prefix_cache_savings_usd),
            _coerce_float(model_routing_savings_usd),
            _coerce_float(tool_schema_compaction_savings_usd),
            _coerce_float(api_surface_slimming_savings_usd),
            _coerce_float(normalization_savings_usd),
            _coerce_float(memoization_savings_usd),
            _coerce_float(output_optimization_savings_usd),
            _coerce_float(batch_routing_savings_usd),
        )
    )
    observed = sum(
        (
            _coerce_float(cache_savings_usd),
            _coerce_float(semantic_cache_savings_usd),
        )
    )
    return round(created, 6), round(observed, 6)


PROVIDER_UNKNOWN = "unknown"


def _normalize_provider(value: Any) -> str:
    """Normalize a provider label, falling back to a stable sentinel.

    History checkpoints persisted before per-provider attribution existed have
    no provider field, so they collapse into ``PROVIDER_UNKNOWN`` rather than
    silently dropping their savings from the per-provider breakdown.
    """
    if not isinstance(value, str):
        return PROVIDER_UNKNOWN
    cleaned = value.strip()
    return cleaned or PROVIDER_UNKNOWN


MODEL_UNKNOWN = "unknown"


def _normalize_model(value: Any) -> str:
    """Normalize a model label, falling back to a stable sentinel.

    History checkpoints persisted before per-model attribution existed have
    no model field, so they collapse into ``MODEL_UNKNOWN`` rather than
    silently dropping their savings from the per-model breakdown.
    """
    if not isinstance(value, str):
        return MODEL_UNKNOWN
    cleaned = value.strip()
    return cleaned or MODEL_UNKNOWN


def _resolve_litellm_model(model: str) -> str:
    """Resolve model name to one LiteLLM recognizes."""
    litellm = _get_litellm_module()
    if litellm is None:
        return model

    try:
        litellm.cost_per_token(model=model, prompt_tokens=1, completion_tokens=0)
        return model
    except Exception:
        pass

    prefixes = {
        "claude-": "anthropic/",
        "gpt-": "openai/",
        "o1-": "openai/",
        "o3-": "openai/",
        "o4-": "openai/",
        "gemini-": "google/",
    }
    for pattern, prefix in prefixes.items():
        if model.startswith(pattern):
            candidate = f"{prefix}{model}"
            try:
                litellm.cost_per_token(
                    model=candidate,
                    prompt_tokens=1,
                    completion_tokens=0,
                )
                return candidate
            except Exception:
                break

    return model


def _estimate_compression_savings_usd(model: str, tokens_saved: int) -> float:
    """Estimate compression savings in USD from saved input tokens."""
    litellm = _get_litellm_module()
    if tokens_saved <= 0 or litellm is None:
        return 0.0

    try:
        model_cost = getattr(litellm, "model_cost", {}) or {}
        for candidate in _compression_pricing_candidates(model):
            info = model_cost.get(candidate, {})
            input_cost_per_token = info.get("input_cost_per_token")
            if input_cost_per_token:
                return float(tokens_saved) * float(input_cost_per_token)
        return 0.0
    except Exception:
        return 0.0


def _estimate_input_cost_usd(
    model: str,
    input_tokens: int,
    *,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    uncached_input_tokens: int = 0,
) -> float:
    """Estimate input spend in USD for a request.

    Uses provider cache pricing when a complete cache breakdown is available and
    otherwise falls back to list-price input tokens.
    """
    total_input_tokens = _coerce_int(input_tokens)
    litellm = _get_litellm_module()
    if total_input_tokens <= 0 or litellm is None:
        return 0.0

    cache_read = _coerce_int(cache_read_tokens)
    cache_write = _coerce_int(cache_write_tokens)
    uncached = _coerce_int(uncached_input_tokens)

    try:
        resolved = _resolve_litellm_model(model)
        info = litellm.model_cost.get(resolved, {})
        input_cost_per_token = info.get("input_cost_per_token")
        if not input_cost_per_token:
            return 0.0

        if cache_read + cache_write + uncached > 0:
            cache_read_cost = info.get(
                "cache_read_input_token_cost",
                input_cost_per_token,
            )
            cache_write_cost = info.get(
                "cache_creation_input_token_cost",
                input_cost_per_token,
            )
            return (
                float(cache_read) * float(cache_read_cost)
                + float(cache_write) * float(cache_write_cost)
                + float(uncached) * float(input_cost_per_token)
            )

        return float(total_input_tokens) * float(input_cost_per_token)
    except Exception:
        return 0.0


def estimate_request_cost_usd(
    model: str,
    *,
    input_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    uncached_input_tokens: int = 0,
) -> float:
    """Public cache-aware input-cost estimate, in USD.

    Thin public wrapper around :func:`_estimate_input_cost_usd` (the same
    logic the primary savings estimate uses) so shadow mode's compressed-
    vs-uncompressed cost comparison (Task 1, commercial-readiness runbook)
    stays apples-to-apples with the rest of the pricing pipeline instead of
    reimplementing cache-aware pricing. Never raises — returns 0.0 if
    tokens are non-positive or pricing data is unavailable.
    """
    return _estimate_input_cost_usd(
        model,
        input_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        uncached_input_tokens=uncached_input_tokens,
    )


def _normalize_history_entry(entry: Any) -> dict[str, Any] | None:
    """Normalize persisted history entries across schema shapes.

    Phase 1.4: preserves the new savings sources (semantic_cache,
    self_hosted_prefix_cache, model_routing) on reload so the buyer
    report and the dashboard see restart-safe by-source attribution
    for all tracked sources.
    """
    timestamp: datetime | None = None
    total_tokens_saved = 0
    compression_savings_usd = 0.0
    compression_savings_observed_usd = 0.0
    created_savings_usd: float | None = None
    observed_provider_savings_usd: float | None = None
    cache_savings_usd = 0.0
    cache_savings_observed_usd = 0.0
    semantic_cache_savings_usd = 0.0
    semantic_cache_savings_observed_usd = 0.0
    self_hosted_prefix_cache_savings_usd = 0.0
    self_hosted_prefix_cache_savings_observed_usd = 0.0
    model_routing_savings_usd = 0.0
    model_routing_savings_observed_usd = 0.0
    tool_schema_compaction_savings_usd = 0.0
    tool_schema_compaction_savings_observed_usd = 0.0
    api_surface_slimming_savings_usd = 0.0
    api_surface_slimming_savings_observed_usd = 0.0
    total_input_tokens = 0
    total_input_cost_usd = 0.0
    provider = PROVIDER_UNKNOWN
    model = MODEL_UNKNOWN
    delta_tokens_saved = 0
    delta_savings_usd = 0.0
    delta_cache_savings_usd = 0.0
    delta_semantic_cache_usd = 0.0
    delta_self_hosted_prefix_cache_usd = 0.0
    delta_model_routing_usd = 0.0
    delta_tool_schema_compaction_usd = 0.0
    delta_api_surface_slimming_usd = 0.0
    savings_by_source_tokens: dict[str, int] = {}
    savings_by_source_usd: dict[str, float] = {}
    savings_basis = SAVINGS_BASIS_ESTIMATED
    pricing_basis = "model_input_list_price"
    created_savings_tokens = 0
    observed_provider_savings_tokens = 0
    delta_created_savings_tokens = 0
    delta_observed_provider_savings_tokens = 0
    attribution_covered = False
    opportunity_funnel: dict[str, int] = {}
    decline_reason = None

    if isinstance(entry, dict):
        timestamp = _parse_timestamp(entry.get("timestamp"))
        total_tokens_saved = _coerce_int(entry.get("total_tokens_saved"))
        compression_savings_usd = _coerce_float(entry.get("compression_savings_usd"))
        compression_savings_observed_usd = _coerce_float(
            entry.get("compression_savings_observed_usd")
        )
        created_savings_usd = (
            _coerce_float(entry.get("created_savings_usd"))
            if "created_savings_usd" in entry
            else None
        )
        observed_provider_savings_usd = (
            _coerce_float(entry.get("observed_provider_savings_usd"))
            if "observed_provider_savings_usd" in entry
            else None
        )
        cache_savings_usd = _coerce_float(entry.get("cache_savings_usd"))
        cache_savings_observed_usd = _coerce_float(entry.get("cache_savings_observed_usd"))
        semantic_cache_savings_usd = _coerce_float(entry.get("semantic_cache_savings_usd"))
        semantic_cache_savings_observed_usd = _coerce_float(
            entry.get("semantic_cache_savings_observed_usd")
        )
        self_hosted_prefix_cache_savings_usd = _coerce_float(
            entry.get("self_hosted_prefix_cache_savings_usd")
        )
        self_hosted_prefix_cache_savings_observed_usd = _coerce_float(
            entry.get("self_hosted_prefix_cache_savings_observed_usd")
        )
        model_routing_savings_usd = _coerce_float(entry.get("model_routing_savings_usd"))
        model_routing_savings_observed_usd = _coerce_float(
            entry.get("model_routing_savings_observed_usd")
        )
        tool_schema_compaction_savings_usd = _coerce_float(
            entry.get("tool_schema_compaction_savings_usd")
        )
        tool_schema_compaction_savings_observed_usd = _coerce_float(
            entry.get("tool_schema_compaction_savings_observed_usd")
        )
        api_surface_slimming_savings_usd = _coerce_float(
            entry.get("api_surface_slimming_savings_usd")
        )
        api_surface_slimming_savings_observed_usd = _coerce_float(
            entry.get("api_surface_slimming_savings_observed_usd")
        )
        total_input_tokens = _coerce_int(entry.get("total_input_tokens"))
        total_input_cost_usd = _coerce_float(entry.get("total_input_cost_usd"))
        provider = _normalize_provider(entry.get("provider"))
        model = _normalize_model(entry.get("model"))
        delta_tokens_saved = _coerce_int(entry.get("delta_tokens_saved"))
        delta_savings_usd = _coerce_float(entry.get("delta_savings_usd"))
        delta_cache_savings_usd = _coerce_float(entry.get("delta_cache_savings_usd"))
        delta_semantic_cache_usd = _coerce_float(entry.get("delta_semantic_cache_usd"))
        delta_self_hosted_prefix_cache_usd = _coerce_float(
            entry.get("delta_self_hosted_prefix_cache_usd")
        )
        delta_model_routing_usd = _coerce_float(entry.get("delta_model_routing_usd"))
        delta_tool_schema_compaction_usd = _coerce_float(
            entry.get("delta_tool_schema_compaction_usd")
        )
        delta_api_surface_slimming_usd = _coerce_float(entry.get("delta_api_surface_slimming_usd"))
        raw_by_source = entry.get("savings_by_source_tokens") or {}
        if isinstance(raw_by_source, dict):
            savings_by_source_tokens = {
                str(k): _coerce_int(v) for k, v in raw_by_source.items() if _coerce_int(v) > 0
            }
        raw_by_source_usd = entry.get("savings_by_source_usd") or {}
        if isinstance(raw_by_source_usd, dict):
            savings_by_source_usd = {str(k): _coerce_float(v) for k, v in raw_by_source_usd.items()}
        # Task 1 (commercial-readiness runbook): every history row recorded
        # by ``record_request``/``record_compression_savings`` is an
        # estimate (token-count delta x list price); "measured" rows live
        # in the separate ``shadow_checks`` list instead, so any unknown
        # or missing value here defaults to "estimated" rather than
        # silently accepting an unvalidated string.
        savings_basis = entry.get("savings_basis")
        if savings_basis not in (SAVINGS_BASIS_ESTIMATED, SAVINGS_BASIS_MEASURED):
            savings_basis = SAVINGS_BASIS_ESTIMATED
        pricing_basis = str(entry.get("pricing_basis") or "model_input_list_price")
        created_savings_tokens = _coerce_int(entry.get("created_savings_tokens"))
        observed_provider_savings_tokens = _coerce_int(
            entry.get("observed_provider_savings_tokens")
        )
        delta_created_savings_tokens = _coerce_int(entry.get("delta_created_savings_tokens"))
        delta_observed_provider_savings_tokens = _coerce_int(
            entry.get("delta_observed_provider_savings_tokens")
        )
        attribution_covered = (
            "delta_created_savings_tokens" in entry
            and "delta_observed_provider_savings_tokens" in entry
        ) or bool(savings_by_source_tokens)
        raw_funnel = entry.get("opportunity_funnel")
        if isinstance(raw_funnel, dict):
            opportunity_funnel = {
                key: _coerce_int(raw_funnel.get(key))
                for key in (
                    "eligible_input_tokens",
                    "cache_protected_tokens",
                    "compressed_tokens",
                    "declined_tokens",
                )
            }
        decline_reason = str(entry.get("decline_reason") or "") or None

    elif isinstance(entry, list | tuple) and len(entry) >= 2:
        timestamp = _parse_timestamp(entry[0])
        total_tokens_saved = _coerce_int(entry[1])
        if len(entry) >= 3:
            compression_savings_usd = _coerce_float(entry[2])
        if len(entry) >= 4:
            total_input_tokens = _coerce_int(entry[3])
        if len(entry) >= 5:
            total_input_cost_usd = _coerce_float(entry[4])
    else:
        return None

    created_savings_usd, observed_provider_savings_usd = _derive_created_and_observed_savings_usd(
        savings_by_source_usd=savings_by_source_usd,
        created_savings_usd=created_savings_usd,
        observed_provider_savings_usd=observed_provider_savings_usd,
        compression_savings_usd=compression_savings_usd,
        cache_savings_usd=cache_savings_usd,
        semantic_cache_savings_usd=semantic_cache_savings_usd,
        self_hosted_prefix_cache_savings_usd=self_hosted_prefix_cache_savings_usd,
        model_routing_savings_usd=model_routing_savings_usd,
        tool_schema_compaction_savings_usd=tool_schema_compaction_savings_usd,
        api_surface_slimming_savings_usd=api_surface_slimming_savings_usd,
    )

    if timestamp is None:
        return None

    return {
        "timestamp": _to_utc_iso(timestamp),
        "provider": provider,
        "model": model,
        "savings_basis": savings_basis,
        "pricing_basis": pricing_basis,
        "created_savings_tokens": created_savings_tokens,
        "observed_provider_savings_tokens": observed_provider_savings_tokens,
        "delta_created_savings_tokens": delta_created_savings_tokens,
        "delta_observed_provider_savings_tokens": delta_observed_provider_savings_tokens,
        "attribution_covered": attribution_covered,
        "opportunity_funnel": opportunity_funnel,
        "decline_reason": decline_reason,
        "total_tokens_saved": total_tokens_saved,
        "compression_savings_usd": round(compression_savings_usd, 6),
        "compression_savings_observed_usd": round(compression_savings_observed_usd, 6),
        "created_savings_usd": round(created_savings_usd, 6),
        "observed_provider_savings_usd": round(observed_provider_savings_usd, 6),
        "cache_savings_usd": round(cache_savings_usd, 6),
        "cache_savings_observed_usd": round(cache_savings_observed_usd, 6),
        "semantic_cache_savings_usd": round(semantic_cache_savings_usd, 6),
        "semantic_cache_savings_observed_usd": round(semantic_cache_savings_observed_usd, 6),
        "self_hosted_prefix_cache_savings_usd": round(self_hosted_prefix_cache_savings_usd, 6),
        "self_hosted_prefix_cache_savings_observed_usd": round(
            self_hosted_prefix_cache_savings_observed_usd, 6
        ),
        "model_routing_savings_usd": round(model_routing_savings_usd, 6),
        "model_routing_savings_observed_usd": round(model_routing_savings_observed_usd, 6),
        "tool_schema_compaction_savings_usd": round(tool_schema_compaction_savings_usd, 6),
        "tool_schema_compaction_savings_observed_usd": round(
            tool_schema_compaction_savings_observed_usd, 6
        ),
        "api_surface_slimming_savings_usd": round(api_surface_slimming_savings_usd, 6),
        "api_surface_slimming_savings_observed_usd": round(
            api_surface_slimming_savings_observed_usd, 6
        ),
        "total_input_tokens": total_input_tokens,
        "total_input_cost_usd": round(total_input_cost_usd, 6),
        "delta_tokens_saved": delta_tokens_saved,
        "delta_savings_usd": round(delta_savings_usd, 6),
        "delta_cache_savings_usd": round(delta_cache_savings_usd, 6),
        "delta_semantic_cache_usd": round(delta_semantic_cache_usd, 6),
        "delta_self_hosted_prefix_cache_usd": round(delta_self_hosted_prefix_cache_usd, 6),
        "delta_model_routing_usd": round(delta_model_routing_usd, 6),
        "delta_tool_schema_compaction_usd": round(delta_tool_schema_compaction_usd, 6),
        "delta_api_surface_slimming_usd": round(delta_api_surface_slimming_usd, 6),
        "savings_by_source_tokens": savings_by_source_tokens,
        "savings_by_source_usd": savings_by_source_usd,
    }


def _empty_display_session() -> dict[str, Any]:
    return {
        "requests": 0,
        "tokens_saved": 0,
        "compression_savings_usd": 0.0,
        "compression_savings_observed_usd": 0.0,
        "created_savings_usd": 0.0,
        "observed_provider_savings_usd": 0.0,
        "created_savings_tokens": 0,
        "observed_provider_savings_tokens": 0,
        "attribution_coverage": _coverage_payload(0, 0),
        "opportunity_funnel": _empty_opportunity_funnel(),
        "total_input_tokens": 0,
        "total_input_cost_usd": 0.0,
        "savings_percent": 0.0,
        "total_savings_usd": 0.0,
        "savings_by_source_tokens": {},
        "savings_by_source_usd": {},
        "started_at": None,
        "last_activity_at": None,
    }


def sanitize_project_name(value: Any) -> str | None:
    """Normalize a client-supplied project name; ``None`` when unusable.

    Strips control characters, trims whitespace, and caps length so a
    misbehaving client cannot bloat the persisted state or the dashboard.
    """
    if not isinstance(value, str):
        return None
    cleaned = "".join(ch for ch in value if ch.isprintable()).strip()
    if not cleaned:
        return None
    return cleaned[:PROJECT_NAME_MAX_LENGTH]


def _empty_project_entry() -> dict[str, Any]:
    return {
        "requests": 0,
        "tokens_saved": 0,
        "compression_savings_usd": 0.0,
        "cache_savings_usd": 0.0,
        "semantic_cache_savings_usd": 0.0,
        "self_hosted_prefix_cache_savings_usd": 0.0,
        "model_routing_savings_usd": 0.0,
        "tool_schema_compaction_savings_usd": 0.0,
        "api_surface_slimming_savings_usd": 0.0,
        "normalization_savings_usd": 0.0,
        "memoization_savings_usd": 0.0,
        "output_optimization_savings_usd": 0.0,
        "batch_routing_savings_usd": 0.0,
        "created_savings_usd": 0.0,
        "observed_provider_savings_usd": 0.0,
        "total_savings_usd": 0.0,
        "total_input_tokens": 0,
        "total_input_cost_usd": 0.0,
        "last_activity_at": None,
    }


_NAMED_BUCKET_SOURCE_USD_FIELDS: tuple[tuple[str, str], ...] = (
    ("cutctx_compression", "compression_savings_usd"),
    ("provider_prompt_cache", "cache_savings_usd"),
    ("semantic_cache", "semantic_cache_savings_usd"),
    ("prefix_cache_self_hosted", "self_hosted_prefix_cache_savings_usd"),
    ("model_routing", "model_routing_savings_usd"),
    ("tool_schema_compaction", "tool_schema_compaction_savings_usd"),
    ("api_surface_slimming", "api_surface_slimming_savings_usd"),
    ("normalization", "normalization_savings_usd"),
    ("memoization", "memoization_savings_usd"),
    ("output_optimization", "output_optimization_savings_usd"),
    ("batch_routing", "batch_routing_savings_usd"),
)


def _normalize_named_entries(raw: Any, max_entries: int) -> dict[str, dict[str, Any]]:
    """Shared normalizer behind ``_normalize_projects``/``_models``/``_clients``."""
    if not isinstance(raw, dict):
        return {}
    entries: dict[str, dict[str, Any]] = {}
    for name, entry in raw.items():
        cleaned_name = sanitize_project_name(name)
        if cleaned_name is None or not isinstance(entry, dict):
            continue
        normalized = _empty_project_entry()
        normalized["requests"] = _coerce_int(entry.get("requests"))
        normalized["tokens_saved"] = _coerce_int(entry.get("tokens_saved"))
        normalized["compression_savings_usd"] = round(
            _coerce_float(entry.get("compression_savings_usd")), 6
        )
        for _source_key, field_name in _NAMED_BUCKET_SOURCE_USD_FIELDS[1:]:
            normalized[field_name] = round(_coerce_float(entry.get(field_name)), 6)
        created_savings_usd, observed_provider_savings_usd = (
            _derive_created_and_observed_savings_usd(
                created_savings_usd=entry.get("created_savings_usd")
                if "created_savings_usd" in entry
                else None,
                observed_provider_savings_usd=entry.get("observed_provider_savings_usd")
                if "observed_provider_savings_usd" in entry
                else None,
                compression_savings_usd=normalized["compression_savings_usd"],
                cache_savings_usd=normalized["cache_savings_usd"],
                semantic_cache_savings_usd=normalized["semantic_cache_savings_usd"],
                self_hosted_prefix_cache_savings_usd=normalized[
                    "self_hosted_prefix_cache_savings_usd"
                ],
                model_routing_savings_usd=normalized["model_routing_savings_usd"],
                tool_schema_compaction_savings_usd=normalized["tool_schema_compaction_savings_usd"],
                api_surface_slimming_savings_usd=normalized["api_surface_slimming_savings_usd"],
                normalization_savings_usd=normalized["normalization_savings_usd"],
                memoization_savings_usd=normalized["memoization_savings_usd"],
                output_optimization_savings_usd=normalized["output_optimization_savings_usd"],
                batch_routing_savings_usd=normalized["batch_routing_savings_usd"],
            )
        )
        normalized["created_savings_usd"] = created_savings_usd
        normalized["observed_provider_savings_usd"] = observed_provider_savings_usd
        normalized["total_savings_usd"] = round(
            _coerce_float(
                entry.get("total_savings_usd"),
                default=created_savings_usd + observed_provider_savings_usd,
            ),
            6,
        )
        normalized["total_input_tokens"] = _coerce_int(entry.get("total_input_tokens"))
        normalized["total_input_cost_usd"] = round(
            _coerce_float(entry.get("total_input_cost_usd")), 6
        )
        last_activity = _parse_timestamp(entry.get("last_activity_at"))
        normalized["last_activity_at"] = _to_utc_iso(last_activity) if last_activity else None
        entries[cleaned_name] = normalized
    if len(entries) > max_entries:
        # Oversized persisted maps (hand-edited or future versions) would
        # otherwise shrink only one entry per recorded request.
        kept = sorted(
            entries.items(),
            key=lambda item: (item[1]["tokens_saved"], item[1]["last_activity_at"] or ""),
            reverse=True,
        )[:max_entries]
        entries = dict(kept)
    return entries


def _normalize_projects(raw: Any) -> dict[str, dict[str, Any]]:
    return _normalize_named_entries(raw, DEFAULT_MAX_PROJECTS)


def _normalize_models(raw: Any) -> dict[str, dict[str, Any]]:
    return _normalize_named_entries(raw, DEFAULT_MAX_MODELS)


def _normalize_clients(raw: Any) -> dict[str, dict[str, Any]]:
    return _normalize_named_entries(raw, DEFAULT_MAX_CLIENTS)


def _normalize_shadow_check_entry(entry: Any) -> dict[str, Any] | None:
    """Normalize one persisted shadow-mode comparison row (Task 1)."""
    if not isinstance(entry, dict):
        return None
    timestamp = _parse_timestamp(entry.get("timestamp"))
    if timestamp is None:
        return None
    return {
        "timestamp": _to_utc_iso(timestamp),
        "request_id": entry.get("request_id") if isinstance(entry.get("request_id"), str) else None,
        "provider": _normalize_provider(entry.get("provider")),
        "model": _normalize_model(entry.get("model")),
        "savings_basis": SAVINGS_BASIS_MEASURED,
        "estimated_savings_usd": round(_coerce_float(entry.get("estimated_savings_usd")), 6),
        # Measured savings may legitimately be negative (compression cost
        # MORE than the uncompressed baseline, e.g. cache invalidation) —
        # unlike other USD fields in this module, do not clamp to >= 0.
        "measured_savings_usd": round(_safe_float(entry.get("measured_savings_usd")), 6),
        "measured_delta_usd": round(_safe_float(entry.get("measured_delta_usd")), 6),
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Like ``_coerce_float`` but does not clamp negative values to 0."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_shadow_checks(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized = []
    for item in raw:
        entry = _normalize_shadow_check_entry(item)
        if entry is not None:
            normalized.append(entry)
    normalized.sort(key=lambda item: item["timestamp"])
    if len(normalized) > DEFAULT_MAX_SHADOW_CHECKS:
        normalized = normalized[-DEFAULT_MAX_SHADOW_CHECKS:]
    return normalized


def _normalize_display_session(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return _empty_display_session()

    started_at = _parse_timestamp(entry.get("started_at"))
    last_activity_at = _parse_timestamp(entry.get("last_activity_at"))

    if started_at is None or last_activity_at is None or last_activity_at < started_at:
        return _empty_display_session()

    tokens_saved = _coerce_int(entry.get("tokens_saved"))
    total_input_tokens = _coerce_int(entry.get("total_input_tokens"))
    total_before = max(tokens_saved, total_input_tokens)
    savings_percent = round(
        (tokens_saved / total_before * 100) if total_before > 0 else 0.0,
        2,
    )

    session = {
        "requests": _coerce_int(entry.get("requests")),
        "tokens_saved": tokens_saved,
        "compression_savings_usd": round(
            _coerce_float(entry.get("compression_savings_usd")),
            6,
        ),
        "compression_savings_observed_usd": round(
            _coerce_float(entry.get("compression_savings_observed_usd")),
            6,
        ),
        "total_input_tokens": total_input_tokens,
        "total_input_cost_usd": round(
            _coerce_float(entry.get("total_input_cost_usd")),
            6,
        ),
        "scaffolding_tokens": _coerce_int(entry.get("scaffolding_tokens")),
        "ghost_tokens": _coerce_int(entry.get("ghost_tokens")),
        "savings_percent": savings_percent,
        "started_at": _to_utc_iso(started_at),
        "last_activity_at": _to_utc_iso(last_activity_at),
    }
    created_savings_usd, observed_provider_savings_usd = _derive_created_and_observed_savings_usd(
        savings_by_source_usd=entry.get("savings_by_source_usd")
        if isinstance(entry.get("savings_by_source_usd"), dict)
        else None,
        created_savings_usd=entry.get("created_savings_usd")
        if "created_savings_usd" in entry
        else None,
        observed_provider_savings_usd=entry.get("observed_provider_savings_usd")
        if "observed_provider_savings_usd" in entry
        else None,
        compression_savings_usd=_coerce_float(entry.get("compression_savings_usd")),
        cache_savings_usd=_coerce_float(entry.get("cache_savings_usd")),
        semantic_cache_savings_usd=_coerce_float(entry.get("semantic_cache_savings_usd")),
        self_hosted_prefix_cache_savings_usd=_coerce_float(
            entry.get("self_hosted_prefix_cache_savings_usd")
        ),
        model_routing_savings_usd=_coerce_float(entry.get("model_routing_savings_usd")),
        tool_schema_compaction_savings_usd=_coerce_float(
            entry.get("tool_schema_compaction_savings_usd")
        ),
        api_surface_slimming_savings_usd=_coerce_float(
            entry.get("api_surface_slimming_savings_usd")
        ),
        normalization_savings_usd=_coerce_float(entry.get("normalization_savings_usd")),
        memoization_savings_usd=_coerce_float(entry.get("memoization_savings_usd")),
        output_optimization_savings_usd=_coerce_float(entry.get("output_optimization_savings_usd")),
        batch_routing_savings_usd=_coerce_float(entry.get("batch_routing_savings_usd")),
    )
    session["created_savings_usd"] = created_savings_usd
    session["observed_provider_savings_usd"] = observed_provider_savings_usd
    session["created_savings_tokens"] = _coerce_int(entry.get("created_savings_tokens"))
    session["observed_provider_savings_tokens"] = _coerce_int(
        entry.get("observed_provider_savings_tokens")
    )
    coverage = entry.get("attribution_coverage")
    if isinstance(coverage, dict):
        session["attribution_coverage"] = _coverage_payload(
            _coerce_int(coverage.get("attributed_requests")),
            _coerce_int(coverage.get("legacy_unattributed_requests")),
        )
    else:
        # Display sessions are short-lived and fully attributable once the
        # v6 fields exist; older sessions remain explicitly partial.
        has_explicit_tokens = "created_savings_tokens" in entry
        session["attribution_coverage"] = _coverage_payload(
            session["requests"] if has_explicit_tokens else 0,
            0 if has_explicit_tokens else session["requests"],
        )
    raw_funnel = entry.get("opportunity_funnel")
    funnel = _empty_opportunity_funnel()
    if isinstance(raw_funnel, dict):
        for key in (
            "eligible_input_tokens",
            "cache_protected_tokens",
            "compressed_tokens",
            "declined_tokens",
        ):
            funnel[key] = _coerce_int(raw_funnel.get(key))
        reasons = raw_funnel.get("decline_reasons")
        if isinstance(reasons, dict):
            funnel["decline_reasons"] = {
                str(reason): _coerce_int(count)
                for reason, count in reasons.items()
                if _coerce_int(count) > 0
            }
    session["opportunity_funnel"] = funnel
    source_tokens = entry.get("savings_by_source_tokens")
    source_usd = entry.get("savings_by_source_usd")
    session["savings_by_source_tokens"] = (
        {
            str(source): _coerce_int(value)
            for source, value in source_tokens.items()
            if _coerce_int(value) > 0
        }
        if isinstance(source_tokens, dict)
        else {}
    )
    session["savings_by_source_usd"] = (
        {
            str(source): round(_coerce_float(value), 6)
            for source, value in source_usd.items()
            if _coerce_float(value) > 0
        }
        if isinstance(source_usd, dict)
        else {}
    )
    for field in SESSION_SAVINGS_USD_FIELDS:
        value = round(_coerce_float(entry.get(field)), 6)
        if value > 0 or field in entry:
            session[field] = value
    # Pre-compute total_savings_usd so the dashboard's session view
    # (which reads durationData?.total_savings_usd) shows money saved
    # instead of falling back to $0.
    session["total_savings_usd"] = round(
        _coerce_float(session.get("created_savings_usd"))
        + _coerce_float(session.get("observed_provider_savings_usd")),
        4,
    )
    return session


class SavingsTracker:
    """Persist bounded proxy compression savings history."""

    def __init__(
        self,
        path: str | None = None,
        max_history_points: int = DEFAULT_MAX_HISTORY_POINTS,
        max_history_age_days: int = DEFAULT_MAX_HISTORY_AGE_DAYS,
        max_response_history_points: int = DEFAULT_MAX_RESPONSE_HISTORY_POINTS,
        display_session_inactivity_minutes: int = (DEFAULT_DISPLAY_SESSION_INACTIVITY_MINUTES),
        persistence_mode: str = "sync",
        flush_interval_seconds: float = DEFAULT_SAVINGS_FLUSH_INTERVAL_SECONDS,
    ) -> None:
        self._path = Path(path or get_default_savings_storage_path())
        self._journal_path = self._path.with_name(f"{self._path.name}.journal")
        self._max_history_points = max_history_points
        self._max_history_age_days = max_history_age_days
        self._max_response_history_points = max(
            _coerce_int(
                max_response_history_points,
                DEFAULT_MAX_RESPONSE_HISTORY_POINTS,
            ),
            1,
        )
        self._display_session_inactivity_minutes = max(
            _coerce_int(
                display_session_inactivity_minutes,
                DEFAULT_DISPLAY_SESSION_INACTIVITY_MINUTES,
            ),
            1,
        )
        if persistence_mode not in {"sync", "async"}:
            raise ValueError("persistence_mode must be 'sync' or 'async'")
        if flush_interval_seconds <= 0:
            raise ValueError("flush_interval_seconds must be greater than 0")

        self._lock = threading.Lock()
        self._write_condition = threading.Condition(self._lock)
        self._persistence_mode = persistence_mode
        self._flush_interval_seconds = float(flush_interval_seconds)
        self._dirty_generation = 0
        self._persisted_generation = 0
        self._failed_generation: int | None = None
        self._writer_error: BaseException | None = None
        self._flush_generation = 0
        self._writer_stopping = False
        self._writer: threading.Thread | None = None
        self._state = self._load_state()
        self._state = self._replay_journal(self._state)
        self._journal_generation = _coerce_int(self._state.get("journal_generation"))
        self._pending_journal_records: list[dict[str, Any]] = []
        self._loaded_mtime = self._current_mtime()

    @property
    def storage_path(self) -> str:
        return str(self._path)

    def record_compression_savings(
        self,
        *,
        model: str,
        tokens_saved: int,
        provider: str | None = None,
        total_input_tokens: int | None = None,
        total_input_cost_usd: float | None = None,
        timestamp: datetime | str | None = None,
    ) -> bool:
        """Persist a cumulative savings checkpoint when compression changed totals."""
        delta_tokens = _coerce_int(tokens_saved)
        if delta_tokens <= 0:
            return False

        timestamp_dt = (
            _parse_timestamp(timestamp)
            if isinstance(timestamp, str)
            else timestamp.astimezone(timezone.utc)
            if isinstance(timestamp, datetime)
            else _utc_now()
        )
        if timestamp_dt is None:
            timestamp_dt = _utc_now()

        delta_usd = _estimate_compression_savings_usd(model, delta_tokens)

        with self._lock:
            self._reload_if_stale_locked()
            lifetime = self._state["lifetime"]
            lifetime["tokens_saved"] += delta_tokens
            lifetime["compression_savings_usd"] = round(
                lifetime["compression_savings_usd"] + delta_usd, 6
            )
            lifetime["created_savings_usd"] = round(
                lifetime.get("created_savings_usd", 0.0) + delta_usd,
                6,
            )
            lifetime["observed_provider_savings_usd"] = round(
                lifetime.get("observed_provider_savings_usd", 0.0),
                6,
            )
            lifetime["total_input_tokens"] = max(
                lifetime["total_input_tokens"],
                _coerce_int(total_input_tokens, default=lifetime["total_input_tokens"]),
            )
            lifetime["total_input_cost_usd"] = round(
                max(
                    lifetime["total_input_cost_usd"],
                    _coerce_float(
                        total_input_cost_usd,
                        default=lifetime["total_input_cost_usd"],
                    ),
                ),
                6,
            )

            self._state["history"].append(
                {
                    "timestamp": _to_utc_iso(timestamp_dt),
                    "provider": _normalize_provider(provider),
                    "model": _normalize_model(model),
                    "savings_basis": SAVINGS_BASIS_ESTIMATED,
                    "total_tokens_saved": lifetime["tokens_saved"],
                    "compression_savings_usd": lifetime["compression_savings_usd"],
                    "created_savings_usd": lifetime.get("created_savings_usd", 0.0),
                    "observed_provider_savings_usd": lifetime.get(
                        "observed_provider_savings_usd",
                        0.0,
                    ),
                    "total_input_tokens": lifetime["total_input_tokens"],
                    "total_input_cost_usd": lifetime["total_input_cost_usd"],
                }
            )
            self._trim_history_locked(reference_time=timestamp_dt)
            self._save_locked(history_entry=True)
            return True

    def record_request(
        self,
        *,
        model: str,
        input_tokens: int,
        tokens_saved: int,
        provider: str | None = None,
        project: str | None = None,
        client: str | None = None,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        uncached_input_tokens: int = 0,
        scaffolding_tokens: int = 0,
        ghost_tokens: int = 0,
        total_input_tokens: int | None = None,
        total_input_cost_usd: float | None = None,
        timestamp: datetime | str | None = None,
        savings_by_source_tokens: dict[str, int] | None = None,
        cache_savings_usd_delta: float | None = None,
        compression_savings_usd_delta: float | None = None,
        # Phase 1.4: per-source dollar deltas for the new savings
        # sources. Defaults to None so older callers keep working.
        semantic_cache_usd_delta: float | None = None,
        self_hosted_prefix_cache_usd_delta: float | None = None,
        model_routing_usd_delta: float | None = None,
        tool_schema_compaction_usd_delta: float | None = None,
        api_surface_slimming_usd_delta: float | None = None,
        savings_by_source_usd: dict[str, float] | None = None,
        created_savings_tokens: int = 0,
        observed_provider_savings_tokens: int = 0,
        eligible_input_tokens: int = 0,
        cache_protected_tokens: int = 0,
        compressed_tokens: int = 0,
        decline_reason: str | None = None,
        savings_basis: str = SAVINGS_BASIS_ESTIMATED,
        pricing_basis: str = "model_input_list_price",
    ) -> bool:
        """Persist a canonical display-session update for every request.

        Phase 1.3: ``savings_by_source_tokens`` and the per-source
        dollar deltas flow into the history row so the buyer report can
        attribute savings per source across the lifetime of the proxy.
        """
        timestamp_dt = (
            _parse_timestamp(timestamp)
            if isinstance(timestamp, str)
            else timestamp.astimezone(timezone.utc)
            if isinstance(timestamp, datetime)
            else _utc_now()
        )
        if timestamp_dt is None:
            timestamp_dt = _utc_now()

        delta_tokens_saved = _coerce_int(tokens_saved)
        delta_input_tokens = _coerce_int(input_tokens)
        delta_scaffolding_tokens = _coerce_int(scaffolding_tokens)
        delta_ghost_tokens = _coerce_int(ghost_tokens)
        compression_savings_explicit = compression_savings_usd_delta is not None
        delta_savings_usd = (
            _coerce_float(compression_savings_usd_delta)
            if compression_savings_usd_delta is not None
            else _estimate_compression_savings_usd(model, delta_tokens_saved)
        )
        delta_cache_savings_usd = (
            _coerce_float(cache_savings_usd_delta) if cache_savings_usd_delta is not None else 0.0
        )
        delta_semantic_cache_usd = (
            _coerce_float(semantic_cache_usd_delta) if semantic_cache_usd_delta is not None else 0.0
        )
        delta_self_hosted_usd = (
            _coerce_float(self_hosted_prefix_cache_usd_delta)
            if self_hosted_prefix_cache_usd_delta is not None
            else 0.0
        )
        delta_model_routing_usd = (
            _coerce_float(model_routing_usd_delta) if model_routing_usd_delta is not None else 0.0
        )
        delta_tool_schema_compaction_usd = (
            _coerce_float(tool_schema_compaction_usd_delta)
            if tool_schema_compaction_usd_delta is not None
            else 0.0
        )
        delta_api_surface_slimming_usd = (
            _coerce_float(api_surface_slimming_usd_delta)
            if api_surface_slimming_usd_delta is not None
            else 0.0
        )
        delta_input_cost_usd = _estimate_input_cost_usd(
            model,
            delta_input_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            uncached_input_tokens=uncached_input_tokens,
        )

        # Phase 1.3: by-source token breakdown. We always populate this
        # so restart-safe by-source reporting is available even for
        # traffic that the rest of the system does not enrich.
        if savings_by_source_tokens is None:
            savings_by_source_tokens = {}
            if int(cache_read_tokens or 0) > 0:
                savings_by_source_tokens["provider_prompt_cache"] = int(cache_read_tokens)
            cutctx_only = max(
                0,
                delta_tokens_saved - int(cache_read_tokens or 0),
            )
            if cutctx_only > 0:
                savings_by_source_tokens["cutctx_compression"] = cutctx_only
        savings_by_source_tokens = {
            str(k): max(0, int(v)) for k, v in savings_by_source_tokens.items() if v
        }
        # Per-source USD: explicit dict wins; otherwise the explicit
        # per-source deltas.
        if savings_by_source_usd is None:
            savings_by_source_usd = {}
        savings_by_source_usd = {str(k): float(v) for k, v in savings_by_source_usd.items()}

        # Source dictionaries are canonical. Explicit values are accepted as
        # compatibility inputs but never allowed to diverge from them.
        derived_created_tokens = sum(
            value
            for source, value in savings_by_source_tokens.items()
            if source not in OBSERVED_PROVIDER_SAVINGS_SOURCES
        )
        derived_observed_tokens = sum(
            value
            for source, value in savings_by_source_tokens.items()
            if source in OBSERVED_PROVIDER_SAVINGS_SOURCES
        )
        created_savings_tokens = derived_created_tokens
        observed_provider_savings_tokens = derived_observed_tokens
        eligible_input_tokens = _coerce_int(eligible_input_tokens)
        cache_protected_tokens = _coerce_int(cache_protected_tokens)
        compressed_tokens = _coerce_int(compressed_tokens)
        declined_tokens = max(
            eligible_input_tokens - cache_protected_tokens - compressed_tokens,
            0,
        )
        savings_basis = (
            savings_basis
            if savings_basis in (SAVINGS_BASIS_ESTIMATED, SAVINGS_BASIS_MEASURED)
            else SAVINGS_BASIS_ESTIMATED
        )

        if "provider_prompt_cache" not in savings_by_source_usd and delta_cache_savings_usd:
            savings_by_source_usd["provider_prompt_cache"] = delta_cache_savings_usd
        if (
            "cutctx_compression" not in savings_by_source_usd
            and delta_savings_usd
            and (
                compression_savings_explicit
                or int(savings_by_source_tokens.get("cutctx_compression", 0)) > 0
            )
        ):
            savings_by_source_usd["cutctx_compression"] = delta_savings_usd
        if "semantic_cache" not in savings_by_source_usd and delta_semantic_cache_usd:
            savings_by_source_usd["semantic_cache"] = delta_semantic_cache_usd
        if "prefix_cache_self_hosted" not in savings_by_source_usd and delta_self_hosted_usd:
            savings_by_source_usd["prefix_cache_self_hosted"] = delta_self_hosted_usd
        if "model_routing" not in savings_by_source_usd and delta_model_routing_usd:
            savings_by_source_usd["model_routing"] = delta_model_routing_usd
        if (
            "tool_schema_compaction" not in savings_by_source_usd
            and delta_tool_schema_compaction_usd
        ):
            savings_by_source_usd["tool_schema_compaction"] = delta_tool_schema_compaction_usd
        if "api_surface_slimming" not in savings_by_source_usd and delta_api_surface_slimming_usd:
            savings_by_source_usd["api_surface_slimming"] = delta_api_surface_slimming_usd

        created_savings_usd, observed_provider_savings_usd = (
            _derive_created_and_observed_savings_usd(
                savings_by_source_usd=savings_by_source_usd,
                compression_savings_usd=delta_savings_usd,
                cache_savings_usd=delta_cache_savings_usd,
                semantic_cache_savings_usd=delta_semantic_cache_usd,
                self_hosted_prefix_cache_savings_usd=delta_self_hosted_usd,
                model_routing_savings_usd=delta_model_routing_usd,
                tool_schema_compaction_savings_usd=delta_tool_schema_compaction_usd,
                api_surface_slimming_savings_usd=delta_api_surface_slimming_usd,
            )
        )
        compression_source_usd = 0.0
        if "cutctx_compression" in savings_by_source_usd:
            compression_source_usd = _coerce_float(savings_by_source_usd["cutctx_compression"])
        elif (
            compression_savings_explicit
            or int(savings_by_source_tokens.get("cutctx_compression", 0)) > 0
        ):
            compression_source_usd = delta_savings_usd
        delta_semantic_cache_tokens = int(savings_by_source_tokens.get("semantic_cache", 0))
        delta_self_hosted_tokens = int(savings_by_source_tokens.get("prefix_cache_self_hosted", 0))
        delta_model_routing_tokens = int(savings_by_source_tokens.get("model_routing", 0))
        delta_tool_schema_compaction_tokens = int(
            savings_by_source_tokens.get("tool_schema_compaction", 0)
        )
        delta_api_surface_slimming_tokens = int(
            savings_by_source_tokens.get("api_surface_slimming", 0)
        )

        with self._lock:
            self._reload_if_stale_locked()
            lifetime = self._state["lifetime"]
            previous_total_input_tokens = lifetime["total_input_tokens"]
            previous_total_input_cost_usd = lifetime["total_input_cost_usd"]

            next_total_input_tokens = max(
                previous_total_input_tokens + delta_input_tokens,
                _coerce_int(
                    total_input_tokens,
                    default=previous_total_input_tokens + delta_input_tokens,
                ),
            )
            next_total_input_cost_usd = round(
                max(
                    previous_total_input_cost_usd + delta_input_cost_usd,
                    _coerce_float(
                        total_input_cost_usd,
                        default=previous_total_input_cost_usd + delta_input_cost_usd,
                    ),
                ),
                6,
            )
            session_input_tokens_delta = max(
                next_total_input_tokens - previous_total_input_tokens,
                0,
            )
            session_input_cost_delta = round(
                max(next_total_input_cost_usd - previous_total_input_cost_usd, 0.0),
                6,
            )

            lifetime["requests"] += 1
            lifetime["tokens_saved"] += delta_tokens_saved
            lifetime["created_savings_tokens"] = (
                int(lifetime.get("created_savings_tokens", 0)) + created_savings_tokens
            )
            lifetime["observed_provider_savings_tokens"] = (
                int(lifetime.get("observed_provider_savings_tokens", 0))
                + observed_provider_savings_tokens
            )
            lifetime["attributed_requests"] = int(lifetime.get("attributed_requests", 0)) + 1
            lifetime["attribution_coverage"] = _coverage_payload(
                lifetime["attributed_requests"],
                int(lifetime.get("legacy_unattributed_requests", 0)),
            )
            lifetime_funnel = lifetime.setdefault("opportunity_funnel", _empty_opportunity_funnel())
            lifetime_funnel["eligible_input_tokens"] += eligible_input_tokens
            lifetime_funnel["cache_protected_tokens"] += cache_protected_tokens
            lifetime_funnel["compressed_tokens"] += compressed_tokens
            lifetime_funnel["declined_tokens"] += declined_tokens
            if decline_reason:
                reasons = lifetime_funnel.setdefault("decline_reasons", {})
                reasons[decline_reason] = int(reasons.get(decline_reason, 0)) + 1
            lifetime["scaffolding_tokens"] = (
                int(lifetime.get("scaffolding_tokens", 0)) + delta_scaffolding_tokens
            )
            lifetime["ghost_tokens"] = int(lifetime.get("ghost_tokens", 0)) + delta_ghost_tokens
            from cutctx.proxy.savings_pricing import value_tokens_usd

            def _canonical_source_usd(source_key: str, token_delta: int) -> float:
                # The by-source dict is canonical (it feeds the headline
                # created/observed split); the flat re-estimate is a legacy
                # fallback for callers that attach tokens without USD.
                # Re-estimating here priced model_routing at the routed-to
                # model's flat input rate instead of the router's
                # (source − target) delta, so the typed lifetime counter
                # drifted 4x from savings_by_source_usd.model_routing.
                if source_key in savings_by_source_usd:
                    return _coerce_float(savings_by_source_usd[source_key])
                return value_tokens_usd(model, token_delta)

            created_compression = compression_source_usd
            created_cache = _canonical_source_usd(
                "provider_prompt_cache", int(cache_read_tokens or 0)
            )
            created_semantic = _canonical_source_usd("semantic_cache", delta_semantic_cache_tokens)
            created_self_hosted = _canonical_source_usd(
                "prefix_cache_self_hosted", delta_self_hosted_tokens
            )
            created_routing = _canonical_source_usd("model_routing", delta_model_routing_tokens)
            created_tool_schema = _canonical_source_usd(
                "tool_schema_compaction", delta_tool_schema_compaction_tokens
            )
            created_api_surface = _canonical_source_usd(
                "api_surface_slimming", delta_api_surface_slimming_tokens
            )

            lifetime["compression_savings_usd"] = round(
                lifetime.get("compression_savings_usd", 0.0) + created_compression, 6
            )
            lifetime["compression_savings_observed_usd"] = round(
                lifetime.get("compression_savings_observed_usd", 0.0) + delta_savings_usd, 6
            )

            lifetime["cache_savings_usd"] = round(
                lifetime.get("cache_savings_usd", 0.0) + created_cache, 6
            )
            lifetime["cache_savings_observed_usd"] = round(
                lifetime.get("cache_savings_observed_usd", 0.0) + delta_cache_savings_usd, 6
            )

            lifetime["created_savings_usd"] = round(
                lifetime.get("created_savings_usd", 0.0) + created_savings_usd,
                6,
            )
            lifetime["observed_provider_savings_usd"] = round(
                lifetime.get("observed_provider_savings_usd", 0.0) + observed_provider_savings_usd,
                6,
            )

            lifetime["semantic_cache_savings_usd"] = round(
                lifetime.get("semantic_cache_savings_usd", 0.0) + created_semantic, 6
            )
            lifetime["semantic_cache_savings_observed_usd"] = round(
                lifetime.get("semantic_cache_savings_observed_usd", 0.0) + delta_semantic_cache_usd,
                6,
            )

            lifetime["self_hosted_prefix_cache_savings_usd"] = round(
                lifetime.get("self_hosted_prefix_cache_savings_usd", 0.0) + created_self_hosted, 6
            )
            lifetime["self_hosted_prefix_cache_savings_observed_usd"] = round(
                lifetime.get("self_hosted_prefix_cache_savings_observed_usd", 0.0)
                + delta_self_hosted_usd,
                6,
            )

            lifetime["model_routing_savings_usd"] = round(
                lifetime.get("model_routing_savings_usd", 0.0) + created_routing, 6
            )
            lifetime["model_routing_savings_observed_usd"] = round(
                lifetime.get("model_routing_savings_observed_usd", 0.0) + delta_model_routing_usd, 6
            )

            lifetime["tool_schema_compaction_savings_usd"] = round(
                lifetime.get("tool_schema_compaction_savings_usd", 0.0) + created_tool_schema, 6
            )
            lifetime["tool_schema_compaction_savings_observed_usd"] = round(
                lifetime.get("tool_schema_compaction_savings_observed_usd", 0.0)
                + delta_tool_schema_compaction_usd,
                6,
            )

            lifetime["api_surface_slimming_savings_usd"] = round(
                lifetime.get("api_surface_slimming_savings_usd", 0.0) + created_api_surface, 6
            )
            lifetime["api_surface_slimming_savings_observed_usd"] = round(
                lifetime.get("api_surface_slimming_savings_observed_usd", 0.0)
                + delta_api_surface_slimming_usd,
                6,
            )
            # Phase 1.3: lifetime by-source accumulators.
            for src_name, n in savings_by_source_tokens.items():
                key = f"savings_by_source_tokens.{src_name}"
                lifetime[key] = int(lifetime.get(key, 0)) + int(n)
            # Phase 1.4: per-source USD lifetime accumulators.
            for src_name, usd in savings_by_source_usd.items():
                key = f"savings_by_source_usd.{src_name}"
                lifetime[key] = round(float(lifetime.get(key, 0.0)) + float(usd), 6)
            lifetime["total_input_tokens"] = next_total_input_tokens
            lifetime["total_input_cost_usd"] = next_total_input_cost_usd

            session = self._state["display_session"]
            last_activity = _parse_timestamp(session.get("last_activity_at"))
            if last_activity is None or self._is_display_session_expired(
                last_activity,
                reference_time=timestamp_dt,
            ):
                session = _empty_display_session()
                session["started_at"] = _to_utc_iso(timestamp_dt)
                self._state["display_session"] = session

            session["requests"] += 1
            session["tokens_saved"] += delta_tokens_saved
            session["created_savings_tokens"] = (
                int(session.get("created_savings_tokens", 0)) + created_savings_tokens
            )
            session["observed_provider_savings_tokens"] = (
                int(session.get("observed_provider_savings_tokens", 0))
                + observed_provider_savings_tokens
            )
            session["attribution_coverage"] = _coverage_payload(session["requests"], 0)
            session_funnel = session.setdefault("opportunity_funnel", _empty_opportunity_funnel())
            session_funnel["eligible_input_tokens"] += eligible_input_tokens
            session_funnel["cache_protected_tokens"] += cache_protected_tokens
            session_funnel["compressed_tokens"] += compressed_tokens
            session_funnel["declined_tokens"] += declined_tokens
            if decline_reason:
                reasons = session_funnel.setdefault("decline_reasons", {})
                reasons[decline_reason] = int(reasons.get(decline_reason, 0)) + 1
            session["scaffolding_tokens"] = (
                int(session.get("scaffolding_tokens", 0)) + delta_scaffolding_tokens
            )
            session["ghost_tokens"] = int(session.get("ghost_tokens", 0)) + delta_ghost_tokens
            session["compression_savings_usd"] = round(
                session["compression_savings_usd"] + created_compression, 6
            )
            session["compression_savings_observed_usd"] = round(
                session.get("compression_savings_observed_usd", 0.0) + delta_savings_usd, 6
            )

            session["created_savings_usd"] = round(
                session.get("created_savings_usd", 0.0) + created_savings_usd,
                6,
            )
            session["observed_provider_savings_usd"] = round(
                session.get("observed_provider_savings_usd", 0.0) + observed_provider_savings_usd,
                6,
            )

            session["cache_savings_usd"] = round(
                session.get("cache_savings_usd", 0.0) + created_cache, 6
            )
            session["cache_savings_observed_usd"] = round(
                session.get("cache_savings_observed_usd", 0.0) + delta_cache_savings_usd, 6
            )

            session["semantic_cache_savings_usd"] = round(
                session.get("semantic_cache_savings_usd", 0.0) + created_semantic, 6
            )
            session["semantic_cache_savings_observed_usd"] = round(
                session.get("semantic_cache_savings_observed_usd", 0.0) + delta_semantic_cache_usd,
                6,
            )

            session["self_hosted_prefix_cache_savings_usd"] = round(
                session.get("self_hosted_prefix_cache_savings_usd", 0.0) + created_self_hosted, 6
            )
            session["self_hosted_prefix_cache_savings_observed_usd"] = round(
                session.get("self_hosted_prefix_cache_savings_observed_usd", 0.0)
                + delta_self_hosted_usd,
                6,
            )

            session["model_routing_savings_usd"] = round(
                session.get("model_routing_savings_usd", 0.0) + created_routing, 6
            )
            session["model_routing_savings_observed_usd"] = round(
                session.get("model_routing_savings_observed_usd", 0.0) + delta_model_routing_usd, 6
            )

            session["tool_schema_compaction_savings_usd"] = round(
                session.get("tool_schema_compaction_savings_usd", 0.0) + created_tool_schema, 6
            )
            session["tool_schema_compaction_savings_observed_usd"] = round(
                session.get("tool_schema_compaction_savings_observed_usd", 0.0)
                + delta_tool_schema_compaction_usd,
                6,
            )

            session["api_surface_slimming_savings_usd"] = round(
                session.get("api_surface_slimming_savings_usd", 0.0) + created_api_surface, 6
            )
            session["api_surface_slimming_savings_observed_usd"] = round(
                session.get("api_surface_slimming_savings_observed_usd", 0.0)
                + delta_api_surface_slimming_usd,
                6,
            )
            session["total_input_tokens"] += session_input_tokens_delta
            session["total_input_cost_usd"] = round(
                session["total_input_cost_usd"] + session_input_cost_delta,
                6,
            )
            total_before = max(session["total_input_tokens"], session["tokens_saved"])
            session["savings_percent"] = round(
                (session["tokens_saved"] / total_before * 100) if total_before > 0 else 0.0,
                2,
            )
            session["total_savings_usd"] = round(
                session.get("created_savings_usd", 0.0)
                + session.get("observed_provider_savings_usd", 0.0),
                4,
            )
            session_source_tokens = session.setdefault("savings_by_source_tokens", {})
            for source, value in savings_by_source_tokens.items():
                session_source_tokens[source] = int(session_source_tokens.get(source, 0)) + int(
                    value
                )
            session_source_usd = session.setdefault("savings_by_source_usd", {})
            for source, value in savings_by_source_usd.items():
                session_source_usd[source] = round(
                    float(session_source_usd.get(source, 0.0)) + float(value), 6
                )
            session["last_activity_at"] = _to_utc_iso(timestamp_dt)
            if session.get("started_at") is None:
                session["started_at"] = session["last_activity_at"]

            self._record_project_locked(
                project,
                timestamp_dt=timestamp_dt,
                requests_delta=1,
                tokens_saved_delta=delta_tokens_saved,
                savings_usd_delta=delta_savings_usd,
                savings_by_source_usd=savings_by_source_usd,
                created_savings_usd_delta=created_savings_usd,
                observed_provider_savings_usd_delta=observed_provider_savings_usd,
                input_tokens_delta=delta_input_tokens,
                input_cost_usd_delta=delta_input_cost_usd,
            )
            # provider="compress" (`/v1/compress`) never calls an upstream
            # model — `model` there is only a tokenizer hint a client-side
            # plugin passes in (e.g. opencode's cutctx.ts defaults it to
            # "claude-sonnet-4-5" regardless of the user's actual chat
            # model). Bucketing those calls under "models" mislabels real
            # per-model inference savings, so skip this axis for them;
            # project/client attribution above is still meaningful and kept.
            if provider != "compress":
                self._record_model_locked(
                    model,
                    timestamp_dt=timestamp_dt,
                    requests_delta=1,
                    tokens_saved_delta=delta_tokens_saved,
                    savings_usd_delta=delta_savings_usd,
                    savings_by_source_usd=savings_by_source_usd,
                    created_savings_usd_delta=created_savings_usd,
                    observed_provider_savings_usd_delta=observed_provider_savings_usd,
                    input_tokens_delta=delta_input_tokens,
                    input_cost_usd_delta=delta_input_cost_usd,
                )
            self._record_client_locked(
                client,
                timestamp_dt=timestamp_dt,
                requests_delta=1,
                tokens_saved_delta=delta_tokens_saved,
                savings_usd_delta=delta_savings_usd,
                savings_by_source_usd=savings_by_source_usd,
                created_savings_usd_delta=created_savings_usd,
                observed_provider_savings_usd_delta=observed_provider_savings_usd,
                input_tokens_delta=delta_input_tokens,
                input_cost_usd_delta=delta_input_cost_usd,
            )

            # Persist a history row when there is something to record:
            # either Cutctx savings, or any of the tracked savings sources
            # fired (Phase 1.4). The thresholds mirror the source
            # defaults so a request with provider cache + semantic
            # cache + model routing all leaves a row.
            has_provider_cache = int(cache_read_tokens or 0) > 0 or delta_cache_savings_usd > 0
            has_semantic = delta_semantic_cache_tokens > 0 or delta_semantic_cache_usd > 0
            has_self_hosted = delta_self_hosted_tokens > 0 or delta_self_hosted_usd > 0
            has_model_routing = delta_model_routing_tokens > 0 or delta_model_routing_usd > 0
            has_tool_schema_compaction = (
                delta_tool_schema_compaction_tokens > 0 or delta_tool_schema_compaction_usd > 0
            )
            has_api_surface_slimming = (
                delta_api_surface_slimming_tokens > 0 or delta_api_surface_slimming_usd > 0
            )
            if (
                delta_tokens_saved > 0
                or has_provider_cache
                or has_semantic
                or has_self_hosted
                or has_model_routing
                or has_tool_schema_compaction
                or has_api_surface_slimming
            ):
                self._state["history"].append(
                    {
                        "timestamp": _to_utc_iso(timestamp_dt),
                        "provider": _normalize_provider(provider),
                        "model": _normalize_model(model),
                        # Task 1 (commercial-readiness runbook): every row
                        # this method records is a token-count-delta
                        # estimate. Shadow mode's empirical measurements
                        # live in the separate ``shadow_checks`` list
                        # (see ``record_measured_savings``) so they are
                        # never double-counted against these lifetime
                        # running totals.
                        "savings_basis": savings_basis,
                        "pricing_basis": pricing_basis,
                        # Lifetime counters (running totals at this point).
                        "total_tokens_saved": lifetime["tokens_saved"],
                        "compression_savings_usd": lifetime["compression_savings_usd"],
                        "compression_savings_observed_usd": lifetime.get(
                            "compression_savings_observed_usd", 0.0
                        ),
                        "created_savings_usd": round(lifetime.get("created_savings_usd", 0.0), 6),
                        "observed_provider_savings_usd": round(
                            lifetime.get("observed_provider_savings_usd", 0.0),
                            6,
                        ),
                        "created_savings_tokens": int(lifetime.get("created_savings_tokens", 0)),
                        "observed_provider_savings_tokens": int(
                            lifetime.get("observed_provider_savings_tokens", 0)
                        ),
                        "delta_created_savings_tokens": created_savings_tokens,
                        "delta_observed_provider_savings_tokens": observed_provider_savings_tokens,
                        "opportunity_funnel": {
                            "eligible_input_tokens": eligible_input_tokens,
                            "cache_protected_tokens": cache_protected_tokens,
                            "compressed_tokens": compressed_tokens,
                            "declined_tokens": declined_tokens,
                        },
                        "decline_reason": decline_reason,
                        "cache_savings_usd": round(lifetime.get("cache_savings_usd", 0.0), 6),
                        "cache_savings_observed_usd": round(
                            lifetime.get("cache_savings_observed_usd", 0.0), 6
                        ),
                        "semantic_cache_savings_usd": round(
                            lifetime.get("semantic_cache_savings_usd", 0.0), 6
                        ),
                        "semantic_cache_savings_observed_usd": round(
                            lifetime.get("semantic_cache_savings_observed_usd", 0.0), 6
                        ),
                        "self_hosted_prefix_cache_savings_usd": round(
                            lifetime.get("self_hosted_prefix_cache_savings_usd", 0.0),
                            6,
                        ),
                        "self_hosted_prefix_cache_savings_observed_usd": round(
                            lifetime.get("self_hosted_prefix_cache_savings_observed_usd", 0.0),
                            6,
                        ),
                        "model_routing_savings_usd": round(
                            lifetime.get("model_routing_savings_usd", 0.0), 6
                        ),
                        "model_routing_savings_observed_usd": round(
                            lifetime.get("model_routing_savings_observed_usd", 0.0), 6
                        ),
                        "tool_schema_compaction_savings_usd": round(
                            lifetime.get("tool_schema_compaction_savings_usd", 0.0), 6
                        ),
                        "tool_schema_compaction_savings_observed_usd": round(
                            lifetime.get("tool_schema_compaction_savings_observed_usd", 0.0), 6
                        ),
                        "api_surface_slimming_savings_usd": round(
                            lifetime.get("api_surface_slimming_savings_usd", 0.0), 6
                        ),
                        "api_surface_slimming_savings_observed_usd": round(
                            lifetime.get("api_surface_slimming_savings_observed_usd", 0.0), 6
                        ),
                        "scaffolding_tokens": int(lifetime.get("scaffolding_tokens", 0)),
                        "ghost_tokens": int(lifetime.get("ghost_tokens", 0)),
                        "total_input_tokens": lifetime["total_input_tokens"],
                        "total_input_cost_usd": lifetime["total_input_cost_usd"],
                        # Phase 1.3 + 1.4: per-request deltas plus
                        # by_source breakdown. The buyer report sums
                        # these deltas across rows so the totals
                        # reflect real request count, not a monotonic
                        # lifetime.
                        "delta_tokens_saved": int(delta_tokens_saved),
                        "delta_savings_usd": round(float(delta_savings_usd), 6),
                        "delta_cache_savings_usd": round(float(delta_cache_savings_usd), 6),
                        "delta_semantic_cache_usd": round(float(delta_semantic_cache_usd), 6),
                        "delta_self_hosted_prefix_cache_usd": round(
                            float(delta_self_hosted_usd), 6
                        ),
                        "delta_model_routing_usd": round(float(delta_model_routing_usd), 6),
                        "delta_ghost_tokens": int(delta_ghost_tokens),
                        "delta_scaffolding_tokens": int(delta_scaffolding_tokens),
                        "delta_tool_schema_compaction_usd": round(
                            float(delta_tool_schema_compaction_usd), 6
                        ),
                        "delta_api_surface_slimming_usd": round(
                            float(delta_api_surface_slimming_usd), 6
                        ),
                        "savings_by_source_tokens": dict(savings_by_source_tokens),
                        "savings_by_source_usd": dict(savings_by_source_usd),
                    }
                )
                self._trim_history_locked(reference_time=timestamp_dt)

            self._save_locked(history_entry=True)
            return True

    def record_measured_savings(
        self,
        *,
        model: str,
        estimated_savings_usd: float,
        measured_savings_usd: float,
        provider: str | None = None,
        request_id: str | None = None,
        timestamp: datetime | str | None = None,
    ) -> bool:
        """Persist one shadow-mode measured-vs-estimated savings comparison.

        Task 1 (commercial-readiness runbook): shadow mode duplicates a
        sampled fraction of requests upstream with compression disabled and
        compares the actual provider-billed cost of the compressed vs.
        uncompressed call. ``measured_savings_usd`` is that real cost
        delta (uncompressed cost minus compressed cost); ``estimated_savings_usd``
        is the normal token-count-delta estimate for the same request, so
        the two can be compared directly.

        The entry is appended to a dedicated ``shadow_checks`` list (bounded
        the same way as ``history``) rather than folded into the lifetime/
        session aggregates: a shadow check deliberately duplicates a
        request's upstream cost, and must never be double-counted as if it
        were a second real, billable request.

        ``measured_savings_usd`` may legitimately be negative — that means
        compression cost MORE than the uncompressed baseline for this
        sampled request (e.g. compression busted a provider prompt-cache
        hit). That case is logged at WARNING so it surfaces instead of
        being silently averaged away, per the runbook's negative-savings
        guard.
        """
        timestamp_dt = (
            _parse_timestamp(timestamp)
            if isinstance(timestamp, str)
            else timestamp.astimezone(timezone.utc)
            if isinstance(timestamp, datetime)
            else _utc_now()
        )
        if timestamp_dt is None:
            timestamp_dt = _utc_now()

        estimated = _coerce_float(estimated_savings_usd)
        measured = _safe_float(measured_savings_usd)
        delta = measured - estimated

        if measured < 0:
            logger.warning(
                "event=shadow_negative_savings request_id=%s model=%s provider=%s "
                "measured_savings_usd=%.6f estimated_savings_usd=%.6f — compression "
                "cost MORE than the uncompressed baseline for this sampled request",
                request_id,
                model,
                provider,
                measured,
                estimated,
            )

        entry = {
            "timestamp": _to_utc_iso(timestamp_dt),
            "request_id": request_id,
            "provider": _normalize_provider(provider),
            "model": _normalize_model(model),
            "savings_basis": SAVINGS_BASIS_MEASURED,
            "estimated_savings_usd": round(estimated, 6),
            "measured_savings_usd": round(measured, 6),
            "measured_delta_usd": round(delta, 6),
        }

        with self._lock:
            self._reload_if_stale_locked()
            shadow_checks: list[dict[str, Any]] = self._state.setdefault("shadow_checks", [])
            shadow_checks.append(entry)
            if len(shadow_checks) > DEFAULT_MAX_SHADOW_CHECKS:
                self._state["shadow_checks"] = shadow_checks[-DEFAULT_MAX_SHADOW_CHECKS:]
            self._save_locked(shadow_entry=True)
            return True

    def _record_named_bucket_locked(
        self,
        name_raw: str | None,
        *,
        state_key: str,
        max_entries: int,
        timestamp_dt: datetime,
        requests_delta: int = 0,
        tokens_saved_delta: int = 0,
        savings_usd_delta: float = 0.0,
        savings_by_source_usd: dict[str, float] | None = None,
        created_savings_usd_delta: float = 0.0,
        observed_provider_savings_usd_delta: float = 0.0,
        input_tokens_delta: int = 0,
        input_cost_usd_delta: float = 0.0,
    ) -> None:
        """Accumulate savings into a named bucket (project/model/client).

        Caller must hold ``self._lock``. Unattributed traffic (``name_raw``
        missing or unusable) is skipped so existing aggregate behavior is
        unchanged. The map is capped at ``max_entries``, evicting the
        smallest/oldest bucket.
        """
        name = sanitize_project_name(name_raw)
        if name is None:
            return
        buckets: dict[str, dict[str, Any]] = self._state.setdefault(state_key, {})
        entry = buckets.setdefault(name, _empty_project_entry())
        entry["requests"] += max(requests_delta, 0)
        entry["tokens_saved"] += max(tokens_saved_delta, 0)
        entry["compression_savings_usd"] = round(
            entry["compression_savings_usd"] + max(savings_usd_delta, 0.0), 6
        )
        source_usd = savings_by_source_usd if isinstance(savings_by_source_usd, dict) else {}
        for source_key, field_name in _NAMED_BUCKET_SOURCE_USD_FIELDS[1:]:
            entry[field_name] = round(
                _coerce_float(entry.get(field_name))
                + max(_coerce_float(source_usd.get(source_key)), 0.0),
                6,
            )
        entry["created_savings_usd"] = round(
            _coerce_float(entry.get("created_savings_usd")) + max(created_savings_usd_delta, 0.0),
            6,
        )
        entry["observed_provider_savings_usd"] = round(
            _coerce_float(entry.get("observed_provider_savings_usd"))
            + max(observed_provider_savings_usd_delta, 0.0),
            6,
        )
        entry["total_savings_usd"] = round(
            _coerce_float(entry.get("total_savings_usd"))
            + max(created_savings_usd_delta + observed_provider_savings_usd_delta, 0.0),
            6,
        )
        entry["total_input_tokens"] += max(input_tokens_delta, 0)
        entry["total_input_cost_usd"] = round(
            entry["total_input_cost_usd"] + max(input_cost_usd_delta, 0.0), 6
        )
        entry["last_activity_at"] = _to_utc_iso(timestamp_dt)
        if len(buckets) > max_entries:
            evict = min(
                (key for key in buckets if key != name),
                key=lambda key: (
                    buckets[key]["tokens_saved"],
                    buckets[key]["last_activity_at"] or "",
                ),
            )
            del buckets[evict]

    def _record_project_locked(
        self,
        project: str | None,
        *,
        timestamp_dt: datetime,
        requests_delta: int = 0,
        tokens_saved_delta: int = 0,
        savings_usd_delta: float = 0.0,
        savings_by_source_usd: dict[str, float] | None = None,
        created_savings_usd_delta: float = 0.0,
        observed_provider_savings_usd_delta: float = 0.0,
        input_tokens_delta: int = 0,
        input_cost_usd_delta: float = 0.0,
    ) -> None:
        self._record_named_bucket_locked(
            project,
            state_key="projects",
            max_entries=DEFAULT_MAX_PROJECTS,
            timestamp_dt=timestamp_dt,
            requests_delta=requests_delta,
            tokens_saved_delta=tokens_saved_delta,
            savings_usd_delta=savings_usd_delta,
            savings_by_source_usd=savings_by_source_usd,
            created_savings_usd_delta=created_savings_usd_delta,
            observed_provider_savings_usd_delta=observed_provider_savings_usd_delta,
            input_tokens_delta=input_tokens_delta,
            input_cost_usd_delta=input_cost_usd_delta,
        )

    def _record_model_locked(
        self,
        model: str | None,
        *,
        timestamp_dt: datetime,
        requests_delta: int = 0,
        tokens_saved_delta: int = 0,
        savings_usd_delta: float = 0.0,
        savings_by_source_usd: dict[str, float] | None = None,
        created_savings_usd_delta: float = 0.0,
        observed_provider_savings_usd_delta: float = 0.0,
        input_tokens_delta: int = 0,
        input_cost_usd_delta: float = 0.0,
    ) -> None:
        self._record_named_bucket_locked(
            model,
            state_key="models",
            max_entries=DEFAULT_MAX_MODELS,
            timestamp_dt=timestamp_dt,
            requests_delta=requests_delta,
            tokens_saved_delta=tokens_saved_delta,
            savings_usd_delta=savings_usd_delta,
            savings_by_source_usd=savings_by_source_usd,
            created_savings_usd_delta=created_savings_usd_delta,
            observed_provider_savings_usd_delta=observed_provider_savings_usd_delta,
            input_tokens_delta=input_tokens_delta,
            input_cost_usd_delta=input_cost_usd_delta,
        )

    def _record_client_locked(
        self,
        client: str | None,
        *,
        timestamp_dt: datetime,
        requests_delta: int = 0,
        tokens_saved_delta: int = 0,
        savings_usd_delta: float = 0.0,
        savings_by_source_usd: dict[str, float] | None = None,
        created_savings_usd_delta: float = 0.0,
        observed_provider_savings_usd_delta: float = 0.0,
        input_tokens_delta: int = 0,
        input_cost_usd_delta: float = 0.0,
    ) -> None:
        self._record_named_bucket_locked(
            client,
            state_key="clients",
            max_entries=DEFAULT_MAX_CLIENTS,
            timestamp_dt=timestamp_dt,
            requests_delta=requests_delta,
            tokens_saved_delta=tokens_saved_delta,
            savings_usd_delta=savings_usd_delta,
            savings_by_source_usd=savings_by_source_usd,
            created_savings_usd_delta=created_savings_usd_delta,
            observed_provider_savings_usd_delta=observed_provider_savings_usd_delta,
            input_tokens_delta=input_tokens_delta,
            input_cost_usd_delta=input_cost_usd_delta,
        )

    def _named_bucket_snapshot_locked(self, state_key: str) -> dict[str, dict[str, Any]]:
        """Stats for a named bucket map with a derived ``savings_percent``, sorted by savings."""
        buckets = self._state.get(state_key, {})
        ranked = sorted(
            buckets.items(),
            key=lambda item: item[1]["tokens_saved"],
            reverse=True,
        )
        result: dict[str, dict[str, Any]] = {}
        for name, entry in ranked:
            view = dict(entry)
            total_before = max(view["total_input_tokens"], view["tokens_saved"])
            view["savings_percent"] = round(
                (view["tokens_saved"] / total_before * 100) if total_before > 0 else 0.0,
                2,
            )
            result[name] = view
        return result

    def _projects_snapshot_locked(self) -> dict[str, dict[str, Any]]:
        return self._named_bucket_snapshot_locked("projects")

    def _models_snapshot_locked(self) -> dict[str, dict[str, Any]]:
        return self._named_bucket_snapshot_locked("models")

    def _clients_snapshot_locked(self) -> dict[str, dict[str, Any]]:
        return self._named_bucket_snapshot_locked("clients")

    def stats_preview(self, recent_points: int = 20) -> dict[str, Any]:
        """Return a compact preview for `/stats`."""
        snapshot = self.snapshot()
        return {
            "schema_version": snapshot["schema_version"],
            "storage_path": snapshot["storage_path"],
            "lifetime": snapshot["lifetime"],
            "display_session": snapshot["display_session"],
            "display_session_policy": snapshot["display_session_policy"],
            "history_points": len(snapshot["history"]),
            "recent_history": snapshot["history"][-recent_points:],
            "retention": snapshot["retention"],
            "projects": snapshot["projects"],
            "projects_limit": DEFAULT_MAX_PROJECTS,
            "models": snapshot["models"],
            "clients": snapshot["clients"],
            # Task 1 (commercial-readiness runbook): shadow-mode
            # measured-vs-estimated comparisons, most recent first slice.
            "shadow_checks": snapshot["shadow_checks"][-recent_points:],
        }

    def history_response(self, history_mode: str = "compact") -> dict[str, Any]:
        """Return frontend-friendly historical data for `/stats-history`."""
        # A history/export request is an explicit durability boundary. This
        # preserves the established contract that the ledger a caller has just
        # inspected is also present on disk, while keeping fsync out of normal
        # request completion.
        self.flush()
        if self._persistence_mode == "async":
            self._compact_journal()
        snapshot = self.snapshot()
        raw_history = snapshot["history"]
        series = {
            "hourly": self._build_rollup(raw_history, bucket="hour"),
            "daily": self._build_rollup(raw_history, bucket="day"),
            "weekly": self._build_rollup(raw_history, bucket="week"),
            "monthly": self._build_rollup(raw_history, bucket="month"),
        }
        history = self._history_for_response(raw_history, mode=history_mode)
        return {
            "schema_version": snapshot["schema_version"],
            "generated_at": _to_utc_iso(_utc_now()),
            "storage_path": snapshot["storage_path"],
            "lifetime": snapshot["lifetime"],
            "display_session": snapshot["display_session"],
            "display_session_policy": snapshot["display_session_policy"],
            "history": history,
            "series": series,
            "exports": {
                "default_format": "json",
                "available_formats": ["json", "csv"],
                "available_series": ["history", *series.keys()],
            },
            "retention": snapshot["retention"],
            "projects": snapshot["projects"],
            "models": snapshot["models"],
            "clients": snapshot["clients"],
            "history_summary": {
                "mode": history_mode,
                "stored_points": len(raw_history),
                "returned_points": len(history),
                "compacted": len(history) < len(raw_history),
            },
        }

    def export_rows(self, series: str = "history") -> list[dict[str, Any]]:
        """Return export rows for history or a rollup series."""
        response = self.history_response()
        if series == "history":
            return [dict(item) for item in response["history"]]
        return [dict(item) for item in response["series"].get(series, [])]

    def export_csv(self, series: str = "history") -> str:
        """Export history or rollup series as CSV."""
        rows = self.export_rows(series=series)
        if series == "history":
            fieldnames = [
                "timestamp",
                "total_tokens_saved",
                "compression_savings_usd",
                "total_input_tokens",
                "total_input_cost_usd",
            ]
        else:
            fieldnames = [
                "timestamp",
                "tokens_saved",
                "compression_savings_usd_delta",
                "total_tokens_saved",
                "compression_savings_usd",
                "total_input_tokens_delta",
                "total_input_tokens",
                "total_input_cost_usd_delta",
                "total_input_cost_usd",
            ]

        buffer = StringIO()
        writer = DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
        return buffer.getvalue()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._reload_if_stale_locked()
            history = [dict(item) for item in self._state["history"]]
            ret = {
                "schema_version": SCHEMA_VERSION,
                "storage_path": str(self._path),
                "lifetime": dict(self._state["lifetime"]),
                "display_session": self._display_session_snapshot_locked(),
                "display_session_policy": {
                    "rollover_inactivity_minutes": (self._display_session_inactivity_minutes),
                },
                "history": history,
                "retention": {
                    "max_history_points": self._max_history_points,
                    "max_history_age_days": self._max_history_age_days,
                    "max_response_history_points": self._max_response_history_points,
                },
                "projects": self._projects_snapshot_locked(),
                "models": self._models_snapshot_locked(),
                "clients": self._clients_snapshot_locked(),
                # Task 1 (commercial-readiness runbook): shadow-mode
                # measured-vs-estimated savings comparisons. Kept separate
                # from ``history`` (see ``record_measured_savings``) since
                # each entry duplicates a sampled request's upstream cost
                # and must never be folded into the lifetime/session
                # aggregates as if it were a second real request.
                "shadow_checks": [dict(item) for item in self._state.get("shadow_checks", [])],
            }
            if "attribution_note" in self._state:
                ret["attribution_note"] = self._state["attribution_note"]
            return ret

    def get_summary_stats(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Summary stats in the same shape as ``Storage.get_summary_stats``.

        Lets CLI reporting (``cutctx savings``) read the live proxy store
        instead of the SDK-client SQLite/JSONL backends, which the proxy
        never writes to. History rows carry running lifetime totals rather
        than per-request deltas for tokens saved/input tokens, so a windowed
        query subtracts the running totals at the window boundaries; only
        requests that produced a savings row are counted towards the
        windowed request count (unfiltered queries use the true lifetime
        counter).
        """
        with self._lock:
            self._reload_if_stale_locked()
            lifetime = self._state["lifetime"]

            if start_time is None and end_time is None:
                total_requests = int(lifetime.get("requests", 0))
                total_tokens_before = int(lifetime.get("total_input_tokens", 0))
                total_tokens_saved = int(lifetime.get("tokens_saved", 0))
            else:
                entries = []
                for row in self._state["history"]:
                    ts = _parse_timestamp(row.get("timestamp"))
                    if ts is not None:
                        entries.append((ts, row))
                entries.sort(key=lambda pair: pair[0])

                baseline_tokens_saved = 0
                baseline_input_tokens = 0
                end_tokens_saved = 0
                end_input_tokens = 0
                total_requests = 0
                for ts, row in entries:
                    if start_time is not None and ts < start_time:
                        baseline_tokens_saved = _coerce_int(row.get("total_tokens_saved"))
                        baseline_input_tokens = _coerce_int(row.get("total_input_tokens"))
                        continue
                    if end_time is not None and ts > end_time:
                        continue
                    end_tokens_saved = _coerce_int(row.get("total_tokens_saved"))
                    end_input_tokens = _coerce_int(row.get("total_input_tokens"))
                    total_requests += 1

                total_tokens_saved = max(0, end_tokens_saved - baseline_tokens_saved)
                total_tokens_before = max(0, end_input_tokens - baseline_input_tokens)

            total_tokens_after = max(0, total_tokens_before - total_tokens_saved)
            return {
                "total_requests": total_requests,
                "total_tokens_before": total_tokens_before,
                "total_tokens_after": total_tokens_after,
                "total_tokens_saved": total_tokens_saved,
            }

    def _default_state(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "lifetime": {
                "requests": 0,
                "tokens_saved": 0,
                "compression_savings_usd": 0.0,
                "compression_savings_observed_usd": 0.0,
                "created_savings_usd": 0.0,
                "observed_provider_savings_usd": 0.0,
                "created_savings_tokens": 0,
                "observed_provider_savings_tokens": 0,
                "attributed_requests": 0,
                "legacy_unattributed_requests": 0,
                "attribution_coverage": _coverage_payload(0, 0),
                "opportunity_funnel": _empty_opportunity_funnel(),
                "total_input_tokens": 0,
                "total_input_cost_usd": 0.0,
            },
            "display_session": _empty_display_session(),
            "history": [],
            "projects": {},
            "models": {},
            "clients": {},
            "shadow_checks": [],
            "journal_generation": 0,
        }

    def _load_state(self) -> dict[str, Any]:
        if not self._path.exists():
            return self._default_state()

        try:
            with open(self._path, encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # Medium-26 (production-audit-progress-2026-06-20.md):
            # the previous behavior was to silently fall back to
            # an empty state on a corrupt file. That left no
            # forensic record for the operator to recover the
            # historical data. The fix quarantines the corrupt
            # file by renaming it to <file>.corrupt-<timestamp>
            # and falls back to a fresh state. The next
            # record_request call writes a clean file at the
            # original path. The operator can manually inspect
            # the quarantine file and re-import it if needed.
            logger.warning(
                "Failed to load savings history from %s: %s; "
                "quarantining and starting with a fresh state",
                self._path,
                e,
            )
            try:
                import time as _t

                quarantine = self._path.with_suffix(f".corrupt-{int(_t.time())}.json")
                self._path.rename(quarantine)
                logger.warning(
                    "Quarantined corrupt savings file to %s",
                    quarantine,
                )
            except OSError as rename_exc:
                logger.error(
                    "Failed to quarantine corrupt savings file %s: %s",
                    self._path,
                    rename_exc,
                )
            return self._default_state()

        return self._sanitize_state(raw)

    def verify_integrity(self) -> dict[str, Any]:
        """Lightweight integrity check for the savings state file.

        Medium-26 (production-audit-progress-2026-06-20.md): exposes
        a check that the file is parseable as JSON, has the
        expected top-level keys, and that the history rows are
        monotonically ordered by timestamp. Returns a dict with
        ok/checks/error.
        """
        result: dict[str, Any] = {"ok": True, "checks": {}}
        if not self._path.exists():
            result["checks"]["file_exists"] = False
            return result
        result["checks"]["file_exists"] = True
        try:
            with open(self._path, encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            result["ok"] = False
            result["error"] = f"parse_failed: {exc}"
            return result
        if not isinstance(raw, dict):
            result["ok"] = False
            result["error"] = "top-level is not a dict"
            return result
        for required_key in ("lifetime", "display_session", "history"):
            if required_key not in raw:
                result["ok"] = False
                result["error"] = f"missing top-level key: {required_key}"
                return result
        result["checks"]["top_level_keys"] = "ok"
        history = raw.get("history")
        if isinstance(history, list) and history:
            prev: str | None = None
            monotonic = True
            for row in history:
                ts = row.get("timestamp") if isinstance(row, dict) else None
                if ts is None:
                    continue
                if prev is not None and ts < prev:
                    monotonic = False
                    break
                prev = ts
            result["checks"]["monotonic"] = "ok" if monotonic else "violated"
            if not monotonic:
                result["ok"] = False
                result["error"] = "history rows are not in monotonic timestamp order"
        else:
            result["checks"]["monotonic"] = "empty"
        return result

    def _sanitize_state(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            return self._default_state()

        source_schema_version = _coerce_int(raw.get("schema_version", 0))
        if source_schema_version < 6:
            raw["attribution_note"] = (
                "explicit created/observed token attribution introduced in schema v6; "
                "legacy requests remain visible but are excluded from attribution percentages"
            )
            raw["schema_version"] = SCHEMA_VERSION

        history_raw = raw.get("history", [])
        normalized_history = []
        if isinstance(history_raw, list):
            for item in history_raw:
                normalized = _normalize_history_entry(item)
                if normalized is not None:
                    normalized_history.append(normalized)

        normalized_history.sort(key=lambda item: item["timestamp"])

        lifetime_raw = raw.get("lifetime", {})
        lifetime_requests = 0
        lifetime_tokens_saved = 0
        lifetime_savings_usd = 0.0
        lifetime_savings_observed_usd = 0.0
        lifetime_created_savings_usd = 0.0
        lifetime_observed_provider_savings_usd = 0.0
        lifetime_input_tokens = 0
        lifetime_input_cost_usd = 0.0
        lifetime_created_savings_tokens = 0
        lifetime_observed_provider_savings_tokens = 0
        lifetime_attributed_requests = 0
        lifetime_legacy_unattributed_requests = 0
        lifetime_opportunity_funnel = _empty_opportunity_funnel()
        lifetime_extra_usd = dict.fromkeys(SESSION_SAVINGS_USD_FIELDS, 0.0)
        lifetime_source_tokens = dict.fromkeys(PERSISTED_SAVINGS_SOURCES, 0)
        lifetime_source_usd = dict.fromkeys(PERSISTED_SAVINGS_SOURCES, 0.0)
        if isinstance(lifetime_raw, dict):
            lifetime_requests = _coerce_int(lifetime_raw.get("requests"))
            lifetime_tokens_saved = _coerce_int(lifetime_raw.get("tokens_saved"))
            lifetime_savings_usd = _coerce_float(lifetime_raw.get("compression_savings_usd"))
            lifetime_savings_observed_usd = _coerce_float(
                lifetime_raw.get("compression_savings_observed_usd")
            )
            lifetime_created_savings_usd = _coerce_float(lifetime_raw.get("created_savings_usd"))
            lifetime_observed_provider_savings_usd = _coerce_float(
                lifetime_raw.get("observed_provider_savings_usd")
            )
            lifetime_input_tokens = _coerce_int(lifetime_raw.get("total_input_tokens"))
            lifetime_input_cost_usd = _coerce_float(lifetime_raw.get("total_input_cost_usd"))
            lifetime_created_savings_tokens = _coerce_int(
                lifetime_raw.get("created_savings_tokens")
            )
            lifetime_observed_provider_savings_tokens = _coerce_int(
                lifetime_raw.get("observed_provider_savings_tokens")
            )
            lifetime_attributed_requests = _coerce_int(lifetime_raw.get("attributed_requests"))
            lifetime_legacy_unattributed_requests = _coerce_int(
                lifetime_raw.get("legacy_unattributed_requests")
            )
            raw_funnel = lifetime_raw.get("opportunity_funnel")
            if isinstance(raw_funnel, dict):
                for key in (
                    "eligible_input_tokens",
                    "cache_protected_tokens",
                    "compressed_tokens",
                    "declined_tokens",
                ):
                    lifetime_opportunity_funnel[key] = _coerce_int(raw_funnel.get(key))
                if isinstance(raw_funnel.get("decline_reasons"), dict):
                    lifetime_opportunity_funnel["decline_reasons"] = {
                        str(reason): _coerce_int(count)
                        for reason, count in raw_funnel["decline_reasons"].items()
                        if _coerce_int(count) > 0
                    }
            for field in SESSION_SAVINGS_USD_FIELDS:
                lifetime_extra_usd[field] = _coerce_float(lifetime_raw.get(field))
            for source in PERSISTED_SAVINGS_SOURCES:
                lifetime_source_tokens[source] = _coerce_int(
                    lifetime_raw.get(f"savings_by_source_tokens.{source}")
                )
                lifetime_source_usd[source] = _coerce_float(
                    lifetime_raw.get(f"savings_by_source_usd.{source}")
                )

        if normalized_history:
            last = normalized_history[-1]
            lifetime_tokens_saved = max(
                lifetime_tokens_saved,
                last["total_tokens_saved"],
            )
            lifetime_savings_usd = max(
                lifetime_savings_usd,
                _coerce_float(last.get("compression_savings_usd")),
            )
            lifetime_savings_observed_usd = max(
                lifetime_savings_observed_usd,
                _coerce_float(last.get("compression_savings_observed_usd")),
            )
            lifetime_input_tokens = max(
                lifetime_input_tokens,
                _coerce_int(last.get("total_input_tokens")),
            )
            lifetime_input_cost_usd = max(
                lifetime_input_cost_usd,
                _coerce_float(last.get("total_input_cost_usd")),
            )
            for field in SESSION_SAVINGS_USD_FIELDS:
                lifetime_extra_usd[field] = max(
                    lifetime_extra_usd[field],
                    _coerce_float(last.get(field)),
                )
            for source in PERSISTED_SAVINGS_SOURCES:
                lifetime_source_tokens[source] = max(
                    lifetime_source_tokens[source],
                    sum(
                        _coerce_int(row.get("savings_by_source_tokens", {}).get(source))
                        for row in normalized_history
                        if isinstance(row.get("savings_by_source_tokens"), dict)
                    ),
                )
                lifetime_source_usd[source] = max(
                    lifetime_source_usd[source],
                    sum(
                        _coerce_float(row.get("savings_by_source_usd", {}).get(source))
                        for row in normalized_history
                        if isinstance(row.get("savings_by_source_usd"), dict)
                    ),
                )

        lifetime_created_savings_usd, lifetime_observed_provider_savings_usd = (
            _derive_created_and_observed_savings_usd(
                savings_by_source_usd={
                    source: value for source, value in lifetime_source_usd.items() if value > 0
                }
                or None,
                created_savings_usd=(
                    lifetime_raw.get("created_savings_usd")
                    if isinstance(lifetime_raw, dict) and "created_savings_usd" in lifetime_raw
                    else None
                ),
                observed_provider_savings_usd=(
                    lifetime_raw.get("observed_provider_savings_usd")
                    if isinstance(lifetime_raw, dict)
                    and "observed_provider_savings_usd" in lifetime_raw
                    else None
                ),
                compression_savings_usd=lifetime_savings_usd,
                cache_savings_usd=lifetime_extra_usd.get("cache_savings_usd", 0.0),
                semantic_cache_savings_usd=lifetime_extra_usd.get(
                    "semantic_cache_savings_usd", 0.0
                ),
                self_hosted_prefix_cache_savings_usd=lifetime_extra_usd.get(
                    "self_hosted_prefix_cache_savings_usd",
                    0.0,
                ),
                model_routing_savings_usd=lifetime_extra_usd.get("model_routing_savings_usd", 0.0),
                tool_schema_compaction_savings_usd=lifetime_extra_usd.get(
                    "tool_schema_compaction_savings_usd",
                    0.0,
                ),
                api_surface_slimming_savings_usd=lifetime_extra_usd.get(
                    "api_surface_slimming_savings_usd",
                    0.0,
                ),
                normalization_savings_usd=lifetime_extra_usd.get("normalization_savings_usd", 0.0),
                memoization_savings_usd=lifetime_extra_usd.get("memoization_savings_usd", 0.0),
                output_optimization_savings_usd=lifetime_extra_usd.get(
                    "output_optimization_savings_usd",
                    0.0,
                ),
                batch_routing_savings_usd=lifetime_extra_usd.get("batch_routing_savings_usd", 0.0),
            )
        )

        # v5 and earlier did not persist request-level coverage. Count only
        # history rows with explicit source dictionaries as reconstructable.
        if source_schema_version < 6:
            reconstructable = sum(
                1 for row in normalized_history if row.get("savings_by_source_tokens")
            )
            lifetime_attributed_requests = reconstructable
            lifetime_legacy_unattributed_requests = max(
                lifetime_requests - reconstructable,
                0,
            )
            lifetime_created_savings_tokens = sum(
                _coerce_int(value)
                for source, value in lifetime_source_tokens.items()
                if source not in OBSERVED_PROVIDER_SAVINGS_SOURCES
            )
            lifetime_observed_provider_savings_tokens = sum(
                _coerce_int(value)
                for source, value in lifetime_source_tokens.items()
                if source in OBSERVED_PROVIDER_SAVINGS_SOURCES
            )

        state = {
            "schema_version": SCHEMA_VERSION,
            "lifetime": {
                "requests": lifetime_requests,
                "tokens_saved": lifetime_tokens_saved,
                "compression_savings_usd": round(lifetime_savings_usd, 6),
                "compression_savings_observed_usd": round(lifetime_savings_observed_usd, 6),
                "created_savings_usd": round(lifetime_created_savings_usd, 6),
                "observed_provider_savings_usd": round(lifetime_observed_provider_savings_usd, 6),
                "created_savings_tokens": lifetime_created_savings_tokens,
                "observed_provider_savings_tokens": lifetime_observed_provider_savings_tokens,
                "attributed_requests": lifetime_attributed_requests,
                "legacy_unattributed_requests": lifetime_legacy_unattributed_requests,
                "attribution_coverage": _coverage_payload(
                    lifetime_attributed_requests,
                    lifetime_legacy_unattributed_requests,
                ),
                "opportunity_funnel": lifetime_opportunity_funnel,
                "total_input_tokens": lifetime_input_tokens,
                "total_input_cost_usd": round(lifetime_input_cost_usd, 6),
            },
            "display_session": _normalize_display_session(raw.get("display_session")),
            "history": normalized_history,
            "projects": _normalize_projects(raw.get("projects")),
            "models": _normalize_models(raw.get("models")),
            "clients": _normalize_clients(raw.get("clients")),
            "shadow_checks": _normalize_shadow_checks(raw.get("shadow_checks")),
        }
        if "attribution_note" in raw:
            state["attribution_note"] = raw["attribution_note"]
        for field, value in lifetime_extra_usd.items():
            if value > 0 or (isinstance(lifetime_raw, dict) and field in lifetime_raw):
                state["lifetime"][field] = round(value, 6)
        for source, value in lifetime_source_tokens.items():
            key = f"savings_by_source_tokens.{source}"
            if value > 0 or (isinstance(lifetime_raw, dict) and key in lifetime_raw):
                state["lifetime"][key] = int(value)
        for source, value in lifetime_source_usd.items():
            key = f"savings_by_source_usd.{source}"
            if value > 0 or (isinstance(lifetime_raw, dict) and key in lifetime_raw):
                state["lifetime"][key] = round(value, 6)

        if normalized_history:
            reference_time = _parse_timestamp(normalized_history[-1]["timestamp"]) or _utc_now()
            original_state = self._state if hasattr(self, "_state") else None
            self._state = state
            try:
                self._trim_history_locked(reference_time=reference_time)
                state = self._state
            finally:
                if original_state is not None:
                    self._state = original_state

        return state

    def _trim_history_locked(self, reference_time: datetime | None = None) -> None:
        history = self._state["history"]
        if not history:
            return

        if self._max_history_age_days > 0:
            cutoff = (reference_time or _utc_now()) - timedelta(days=self._max_history_age_days)
            filtered = [
                item
                for item in history
                if (_parse_timestamp(item["timestamp"]) or _utc_now()) >= cutoff
            ]
            if not filtered:
                filtered = [history[-1]]
            history = filtered

        if self._max_history_points > 0 and len(history) > self._max_history_points:
            history = history[-self._max_history_points :]

        self._state["history"] = history

    def _history_for_response(
        self,
        history: list[dict[str, Any]],
        *,
        mode: str,
    ) -> list[dict[str, Any]]:
        if mode == "none":
            return []
        if mode == "full":
            return [dict(item) for item in history]
        return self._compact_history(history)

    def _compact_history(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(history) <= self._max_response_history_points:
            return [dict(item) for item in history]

        # Keep the recent tail dense for charts while evenly sampling older
        # checkpoints so long-running installs don't return unbounded payloads.
        recent_points = min(
            max(self._max_response_history_points // 3, 50),
            self._max_response_history_points - 1,
        )
        recent = history[-recent_points:]
        older = history[:-recent_points]
        older_slots = self._max_response_history_points - len(recent)
        if older_slots <= 0 or not older:
            return [dict(item) for item in recent[-self._max_response_history_points :]]

        if older_slots == 1:
            sampled_older = [older[0]]
        else:
            sampled_older = [
                older[((len(older) - 1) * index) // (older_slots - 1)]
                for index in range(older_slots)
            ]

        compacted: list[dict[str, Any]] = []
        seen_timestamps: set[str] = set()
        for point in [*sampled_older, *recent]:
            timestamp = point.get("timestamp")
            if not isinstance(timestamp, str) or timestamp in seen_timestamps:
                continue
            seen_timestamps.add(timestamp)
            compacted.append(dict(point))

        return compacted

    def _snapshot_locked(self) -> dict[str, Any]:
        """Copy the persisted state while the caller holds ``self._lock``."""

        def copy_small(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: copy_small(item) for key, item in value.items()}
            if isinstance(value, list):
                return [copy_small(item) for item in value]
            return value

        # History and shadow-check entries are append-only: subsequent request
        # updates only add a new entry or replace the containing bounded list.
        # A shallow copy of those containers is therefore an isolated snapshot
        # without deep-copying thousands of immutable historical dictionaries.
        return {
            "schema_version": SCHEMA_VERSION,
            "lifetime": copy_small(self._state["lifetime"]),
            "display_session": copy_small(self._state["display_session"]),
            "history": copy.copy(self._state["history"]),
            "projects": copy_small(self._state.get("projects", {})),
            "models": copy_small(self._state.get("models", {})),
            "clients": copy_small(self._state.get("clients", {})),
            "shadow_checks": copy.copy(self._state.get("shadow_checks", [])),
            "journal_generation": self._journal_generation,
        }

    def _ensure_writer_locked(self) -> None:
        if self._writer is None:
            self._writer = threading.Thread(
                target=self._writer_loop,
                name="cutctx-savings-writer",
                daemon=True,
            )
            self._writer.start()

    def _journal_patch_locked(
        self, *, history_entry: bool = False, shadow_entry: bool = False
    ) -> dict[str, Any]:
        """Build a compact replayable patch without serializing full history."""
        snapshot = self._snapshot_locked()
        patch = {
            "generation": self._journal_generation + len(self._pending_journal_records) + 1,
            "lifetime": snapshot["lifetime"],
            "display_session": snapshot["display_session"],
            "projects": snapshot["projects"],
            "models": snapshot["models"],
            "clients": snapshot["clients"],
        }
        if history_entry and self._state["history"]:
            patch["history_entry"] = dict(self._state["history"][-1])
        if shadow_entry and self._state.get("shadow_checks"):
            patch["shadow_entry"] = dict(self._state["shadow_checks"][-1])
        return patch

    def _save_locked(self, *, history_entry: bool = False, shadow_entry: bool = False) -> None:
        """Schedule or synchronously persist a mutation made under ``_lock``."""
        self._dirty_generation += 1
        if self._persistence_mode == "sync":
            self._persist_snapshot(self._snapshot_locked())
            self._persisted_generation = self._dirty_generation
            self._loaded_mtime = self._current_mtime()
            return

        self._pending_journal_records.append(
            self._journal_patch_locked(history_entry=history_entry, shadow_entry=shadow_entry)
        )
        # A newer mutation supersedes a previous failure: its eventual
        # journal patch contains both the earlier and newer totals.
        self._writer_error = None
        self._failed_generation = None
        self._ensure_writer_locked()
        self._write_condition.notify_all()

    def _writer_loop(self) -> None:
        """Persist the newest dirty snapshot outside proxy request handling."""
        while True:
            with self._write_condition:
                while (
                    self._dirty_generation <= self._persisted_generation
                    and not self._writer_stopping
                ):
                    self._write_condition.wait()
                if self._writer_stopping:
                    return

                # Normal writes debounce for a bounded interval. ``flush``
                # requests skip the delay and establish a durability boundary.
                target_generation = self._dirty_generation
                if self._flush_generation < target_generation:
                    self._write_condition.wait(timeout=self._flush_interval_seconds)
                    target_generation = self._dirty_generation
                records = self._pending_journal_records[:]
                del self._pending_journal_records[: len(records)]

            try:
                self._append_journal(records)
            except BaseException as exc:
                with self._write_condition:
                    self._writer_error = exc
                    self._failed_generation = target_generation
                    self._pending_journal_records[0:0] = records
                    self._write_condition.notify_all()
                    if self._writer_stopping:
                        return
                    # Do not spin on an unavailable disk. A later mutation or
                    # shutdown will wake the writer and permit recovery.
                    while self._dirty_generation <= target_generation and not self._writer_stopping:
                        self._write_condition.wait()
                continue

            with self._write_condition:
                self._persisted_generation = max(self._persisted_generation, target_generation)
                if records:
                    self._journal_generation = max(
                        self._journal_generation,
                        _coerce_int(records[-1].get("generation")),
                    )
                self._loaded_mtime = self._current_mtime()
                self._write_condition.notify_all()

    def flush(self, timeout: float | None = None) -> bool:
        """Wait until all updates accepted at entry have reached durable storage."""
        if self._persistence_mode == "sync":
            return True

        deadline = None if timeout is None else time.monotonic() + timeout
        with self._write_condition:
            target_generation = self._dirty_generation
            if target_generation <= self._persisted_generation:
                return True
            self._ensure_writer_locked()
            self._flush_generation = max(self._flush_generation, target_generation)
            self._write_condition.notify_all()
            while self._persisted_generation < target_generation:
                if (
                    self._writer_error is not None
                    and self._failed_generation is not None
                    and self._failed_generation >= target_generation
                ):
                    raise self._writer_error
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return False
                self._write_condition.wait(timeout=remaining)
            return True

    def close(self) -> None:
        """Flush pending savings and stop the asynchronous writer, if any."""
        flush_error: BaseException | None = None
        try:
            self.flush()
        except BaseException as exc:
            flush_error = exc
        finally:
            with self._write_condition:
                self._writer_stopping = True
                self._write_condition.notify_all()
                writer = self._writer
            if writer is not None:
                writer.join(timeout=5)
            if flush_error is None:
                self._compact_journal()
        if flush_error is not None:
            raise flush_error

    def _append_journal(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._journal_path, "a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, separators=(",", ":")))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _compact_journal(self) -> None:
        """Write one complete snapshot, then discard journal records it covers."""
        with self._write_condition:
            snapshot = self._snapshot_locked()
            snapshot["journal_generation"] = self._journal_generation
        self._persist_snapshot(snapshot)
        try:
            with open(self._journal_path, "w", encoding="utf-8") as handle:
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            logger.warning("Failed to compact savings journal %s: %s", self._journal_path, exc)

    def _replay_journal(self, state: dict[str, Any]) -> dict[str, Any]:
        """Apply durable append patches written after the last JSON snapshot."""
        if not self._journal_path.exists():
            return state
        compacted_generation = _coerce_int(state.get("journal_generation"))
        raw = dict(state)
        raw["history"] = list(state.get("history", []))
        raw["shadow_checks"] = list(state.get("shadow_checks", []))
        latest_generation = compacted_generation
        try:
            with open(self._journal_path, encoding="utf-8") as handle:
                for line in handle:
                    try:
                        patch = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(
                            "Ignoring incomplete savings journal record in %s", self._journal_path
                        )
                        break
                    generation = _coerce_int(patch.get("generation"))
                    if generation <= compacted_generation:
                        continue
                    for key in ("lifetime", "display_session", "projects", "models", "clients"):
                        if isinstance(patch.get(key), dict):
                            raw[key] = patch[key]
                    if isinstance(patch.get("history_entry"), dict):
                        raw["history"].append(patch["history_entry"])
                    if isinstance(patch.get("shadow_entry"), dict):
                        raw["shadow_checks"].append(patch["shadow_entry"])
                    latest_generation = max(latest_generation, generation)
        except OSError as exc:
            logger.warning("Failed to replay savings journal %s: %s", self._journal_path, exc)
            return state
        raw["journal_generation"] = latest_generation
        replayed = self._sanitize_state(raw)
        replayed["journal_generation"] = latest_generation
        return replayed

    def _persist_snapshot(self, payload: dict[str, Any]) -> None:
        """Atomically write one already-copied savings snapshot to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            json_data = json.dumps(payload, indent=2)

            fd, tmp_path = tempfile.mkstemp(
                dir=self._path.parent,
                prefix=".proxy_savings_",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(json_data)
                    f.flush()
                    os.fsync(f.fileno())
                Path(tmp_path).replace(self._path)
            except Exception:
                try:
                    Path(tmp_path).unlink()
                except OSError:
                    pass
                raise
        except OSError as e:
            logger.warning("Failed to save savings history to %s: %s", self._path, e)

    def _current_mtime(self) -> float | None:
        try:
            return self._path.stat().st_mtime
        except OSError:
            return None

    def _reload_if_stale_locked(self) -> None:
        """Reload state from disk if another process has written since we last saw it.

        Must be called while holding ``self._lock``, before reading or
        mutating ``self._state``. Cross-process shared storage means a
        different cutctx proxy (e.g. one on an auto-reassigned port) may
        have appended savings since this process last loaded/saved — this
        keeps Attribution/lifetime totals live-consistent across processes
        instead of reflecting only this process's own requests, and avoids
        a stale-base overwrite clobbering the other process's writes.
        Cheap in the common case: one stat() syscall, no reload needed.
        """
        current = self._current_mtime()
        if current is not None and current != self._loaded_mtime:
            self._state = self._load_state()
            self._loaded_mtime = current

    def _display_session_snapshot_locked(
        self,
        reference_time: datetime | None = None,
    ) -> dict[str, Any]:
        session = dict(self._state["display_session"])
        last_activity = _parse_timestamp(session.get("last_activity_at"))
        if last_activity is None or self._is_display_session_expired(
            last_activity,
            reference_time=reference_time,
        ):
            return _empty_display_session()

        return _normalize_display_session(session)

    def _is_display_session_expired(
        self,
        last_activity: datetime,
        *,
        reference_time: datetime | None = None,
    ) -> bool:
        return (reference_time or _utc_now()) - last_activity > timedelta(
            minutes=self._display_session_inactivity_minutes
        )

    def _build_rollup(
        self,
        history: list[dict[str, Any]],
        bucket: str,
    ) -> list[dict[str, Any]]:
        if not history:
            return []

        aggregated: dict[str, dict[str, Any]] = {}
        prev_total_tokens = 0
        prev_total_usd = 0.0
        prev_total_input_tokens = 0
        prev_total_input_cost_usd = 0.0
        # Phase 1.4 sources: each history point also carries a running
        # lifetime total for these, exactly like ``compression_savings_usd``
        # above. Without diffing them here too, every non-lifetime duration
        # tab (Daily/Weekly/Monthly) silently reports compression-only
        # savings and undercounts cache/routing/schema savings for the period.
        extra_sources = (
            "cache_savings_usd",
            "semantic_cache_savings_usd",
            "self_hosted_prefix_cache_savings_usd",
            "model_routing_savings_usd",
            "tool_schema_compaction_savings_usd",
            "api_surface_slimming_savings_usd",
        )
        prev_extra = dict.fromkeys(extra_sources, 0.0)

        for point in history:
            timestamp = _parse_timestamp(point["timestamp"])
            if timestamp is None:
                continue

            bucket_start = _bucket_start(timestamp, bucket)

            bucket_key = _to_utc_iso(bucket_start)
            total_tokens_saved = _coerce_int(point.get("total_tokens_saved"))
            total_usd = _coerce_float(point.get("compression_savings_usd"))
            total_input_tokens = _coerce_int(point.get("total_input_tokens"))
            total_input_cost_usd = _coerce_float(point.get("total_input_cost_usd"))
            delta_tokens = max(total_tokens_saved - prev_total_tokens, 0)
            delta_usd = max(total_usd - prev_total_usd, 0.0)
            delta_input_tokens = max(total_input_tokens - prev_total_input_tokens, 0)
            delta_input_cost_usd = max(
                total_input_cost_usd - prev_total_input_cost_usd,
                0.0,
            )

            extra_totals = {key: _coerce_float(point.get(key)) for key in extra_sources}
            extra_deltas = {
                key: max(extra_totals[key] - prev_extra[key], 0.0) for key in extra_sources
            }

            prev_total_tokens = total_tokens_saved
            prev_total_usd = total_usd
            prev_total_input_tokens = total_input_tokens
            prev_total_input_cost_usd = total_input_cost_usd
            prev_extra = extra_totals

            entry = aggregated.setdefault(
                bucket_key,
                {
                    "timestamp": bucket_key,
                    "requests": 0,
                    "tokens_saved": 0,
                    "created_savings_tokens": 0,
                    "observed_provider_savings_tokens": 0,
                    "attributed_requests": 0,
                    "legacy_unattributed_requests": 0,
                    "opportunity_funnel": _empty_opportunity_funnel(),
                    "compression_savings_usd_delta": 0.0,
                    "total_tokens_saved": total_tokens_saved,
                    "compression_savings_usd": total_usd,
                    **{f"{key}_delta": 0.0 for key in extra_sources},
                    "total_input_tokens_delta": 0,
                    "total_input_tokens": total_input_tokens,
                    "total_input_cost_usd_delta": 0.0,
                    "total_input_cost_usd": total_input_cost_usd,
                    "by_provider": {},
                    "by_model": {},
                },
            )
            entry["requests"] += 1
            entry["tokens_saved"] += delta_tokens
            entry["created_savings_tokens"] += _coerce_int(
                point.get("delta_created_savings_tokens")
            )
            entry["observed_provider_savings_tokens"] += _coerce_int(
                point.get("delta_observed_provider_savings_tokens")
            )
            if point.get("attribution_covered"):
                entry["attributed_requests"] += 1
            else:
                entry["legacy_unattributed_requests"] += 1
            point_funnel = point.get("opportunity_funnel")
            if isinstance(point_funnel, dict):
                for funnel_key in (
                    "eligible_input_tokens",
                    "cache_protected_tokens",
                    "compressed_tokens",
                    "declined_tokens",
                ):
                    entry["opportunity_funnel"][funnel_key] += _coerce_int(
                        point_funnel.get(funnel_key)
                    )
            point_decline = point.get("decline_reason")
            if point_decline:
                reasons = entry["opportunity_funnel"]["decline_reasons"]
                reasons[point_decline] = int(reasons.get(point_decline, 0)) + 1
            entry["compression_savings_usd_delta"] = round(
                entry["compression_savings_usd_delta"] + delta_usd,
                6,
            )
            for key in extra_sources:
                delta_key = f"{key}_delta"
                entry[delta_key] = round(entry[delta_key] + extra_deltas[key], 6)
            entry["total_input_tokens_delta"] += delta_input_tokens
            entry["total_input_cost_usd_delta"] = round(
                entry["total_input_cost_usd_delta"] + delta_input_cost_usd,
                6,
            )
            entry["total_tokens_saved"] = total_tokens_saved
            entry["compression_savings_usd"] = round(total_usd, 6)
            entry["total_input_tokens"] = total_input_tokens
            entry["total_input_cost_usd"] = round(total_input_cost_usd, 6)

            # Attribute this checkpoint's delta to the provider that produced
            # it. Each checkpoint comes from a single request, so its delta is
            # wholly owned by one provider. Skip no-op checkpoints so providers
            # only appear in a bucket where they actually moved a counter.
            if delta_tokens or delta_usd or delta_input_tokens or delta_input_cost_usd:
                provider = _normalize_provider(point.get("provider"))
                prov = entry["by_provider"].setdefault(
                    provider,
                    {
                        "requests": 0,
                        "tokens_saved": 0,
                        "compression_savings_usd_delta": 0.0,
                        "total_input_tokens_delta": 0,
                        "total_input_cost_usd_delta": 0.0,
                    },
                )
                prov["requests"] += 1
                prov["tokens_saved"] += delta_tokens
                prov["compression_savings_usd_delta"] = round(
                    prov["compression_savings_usd_delta"] + delta_usd,
                    6,
                )
                prov["total_input_tokens_delta"] += delta_input_tokens
                prov["total_input_cost_usd_delta"] = round(
                    prov["total_input_cost_usd_delta"] + delta_input_cost_usd,
                    6,
                )

                model = _normalize_model(point.get("model"))
                mod = entry["by_model"].setdefault(
                    model,
                    {
                        "requests": 0,
                        "tokens_saved": 0,
                        "compression_savings_usd_delta": 0.0,
                        "total_input_tokens_delta": 0,
                        "total_input_cost_usd_delta": 0.0,
                    },
                )
                mod["requests"] += 1
                mod["tokens_saved"] += delta_tokens
                mod["compression_savings_usd_delta"] = round(
                    mod["compression_savings_usd_delta"] + delta_usd,
                    6,
                )
                mod["total_input_tokens_delta"] += delta_input_tokens
                mod["total_input_cost_usd_delta"] = round(
                    mod["total_input_cost_usd_delta"] + delta_input_cost_usd,
                    6,
                )

        for entry in aggregated.values():
            entry["attribution_coverage"] = _coverage_payload(
                entry["attributed_requests"],
                entry["legacy_unattributed_requests"],
            )
        return list(aggregated.values())

"""Durable proxy savings and display-session tracking.

Persists cumulative proxy compression savings plus a canonical display session
window to a local JSON file so historical charts and dashboard session stats
survive proxy restarts and can be shared by multiple Cutctx frontends.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import tempfile
import threading
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
SCHEMA_VERSION = 3
DEFAULT_MAX_HISTORY_POINTS = 5000
DEFAULT_MAX_PROJECTS = 50
DEFAULT_MAX_MODELS = 50
DEFAULT_MAX_CLIENTS = 50
PROJECT_NAME_MAX_LENGTH = 128
DEFAULT_MAX_HISTORY_AGE_DAYS = 365
DEFAULT_MAX_RESPONSE_HISTORY_POINTS = 500
DEFAULT_DISPLAY_SESSION_INACTIVITY_MINUTES = 60

PERSISTED_SAVINGS_SOURCES = (
    "provider_prompt_cache",
    "cutctx_compression",
    "tool_schema_compaction",
    "api_surface_slimming",
    "semantic_cache",
    "prefix_cache_self_hosted",
    "model_routing",
    "output_optimization",
    "memoization",
    "batch_routing",
    "normalization",
)

SESSION_SAVINGS_USD_FIELDS = (
    "cache_savings_usd",
    "semantic_cache_savings_usd",
    "self_hosted_prefix_cache_savings_usd",
    "model_routing_savings_usd",
    "tool_schema_compaction_savings_usd",
    "api_surface_slimming_savings_usd",
    "output_optimization_savings_usd",
    "memoization_savings_usd",
    "batch_routing_savings_usd",
    "normalization_savings_usd",
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
        resolved = _resolve_litellm_model(model)
        info = litellm.model_cost.get(resolved, {})
        input_cost_per_token = info.get("input_cost_per_token")
        if not input_cost_per_token:
            return 0.0
        return float(tokens_saved) * float(input_cost_per_token)
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
    cache_savings_usd = 0.0
    semantic_cache_savings_usd = 0.0
    self_hosted_prefix_cache_savings_usd = 0.0
    model_routing_savings_usd = 0.0
    tool_schema_compaction_savings_usd = 0.0
    api_surface_slimming_savings_usd = 0.0
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

    if isinstance(entry, dict):
        timestamp = _parse_timestamp(entry.get("timestamp"))
        total_tokens_saved = _coerce_int(entry.get("total_tokens_saved"))
        compression_savings_usd = _coerce_float(entry.get("compression_savings_usd"))
        cache_savings_usd = _coerce_float(entry.get("cache_savings_usd"))
        semantic_cache_savings_usd = _coerce_float(entry.get("semantic_cache_savings_usd"))
        self_hosted_prefix_cache_savings_usd = _coerce_float(
            entry.get("self_hosted_prefix_cache_savings_usd")
        )
        model_routing_savings_usd = _coerce_float(entry.get("model_routing_savings_usd"))
        tool_schema_compaction_savings_usd = _coerce_float(
            entry.get("tool_schema_compaction_savings_usd")
        )
        api_surface_slimming_savings_usd = _coerce_float(
            entry.get("api_surface_slimming_savings_usd")
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

    if timestamp is None:
        return None

    return {
        "timestamp": _to_utc_iso(timestamp),
        "provider": provider,
        "model": model,
        "total_tokens_saved": total_tokens_saved,
        "compression_savings_usd": round(compression_savings_usd, 6),
        "cache_savings_usd": round(cache_savings_usd, 6),
        "semantic_cache_savings_usd": round(semantic_cache_savings_usd, 6),
        "self_hosted_prefix_cache_savings_usd": round(self_hosted_prefix_cache_savings_usd, 6),
        "model_routing_savings_usd": round(model_routing_savings_usd, 6),
        "tool_schema_compaction_savings_usd": round(tool_schema_compaction_savings_usd, 6),
        "api_surface_slimming_savings_usd": round(api_surface_slimming_savings_usd, 6),
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
        "total_input_tokens": 0,
        "total_input_cost_usd": 0.0,
        "savings_percent": 0.0,
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
        "total_input_tokens": 0,
        "total_input_cost_usd": 0.0,
        "last_activity_at": None,
    }


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
        "total_input_tokens": total_input_tokens,
        "total_input_cost_usd": round(
            _coerce_float(entry.get("total_input_cost_usd")),
            6,
        ),
        "savings_percent": savings_percent,
        "started_at": _to_utc_iso(started_at),
        "last_activity_at": _to_utc_iso(last_activity_at),
    }
    for field in SESSION_SAVINGS_USD_FIELDS:
        value = round(_coerce_float(entry.get(field)), 6)
        if value > 0 or field in entry:
            session[field] = value
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
    ) -> None:
        self._path = Path(path or get_default_savings_storage_path())
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
        self._lock = threading.Lock()
        self._state = self._load_state()
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
                    "total_tokens_saved": lifetime["tokens_saved"],
                    "compression_savings_usd": lifetime["compression_savings_usd"],
                    "total_input_tokens": lifetime["total_input_tokens"],
                    "total_input_cost_usd": lifetime["total_input_cost_usd"],
                }
            )
            self._trim_history_locked(reference_time=timestamp_dt)
            self._save_locked()
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
            if delta_cache_savings_usd:
                savings_by_source_usd["provider_prompt_cache"] = delta_cache_savings_usd
            if delta_savings_usd:
                savings_by_source_usd["cutctx_compression"] = delta_savings_usd
            if delta_semantic_cache_usd:
                savings_by_source_usd["semantic_cache"] = delta_semantic_cache_usd
            if delta_self_hosted_usd:
                savings_by_source_usd["prefix_cache_self_hosted"] = delta_self_hosted_usd
            if delta_model_routing_usd:
                savings_by_source_usd["model_routing"] = delta_model_routing_usd
            if delta_tool_schema_compaction_usd:
                savings_by_source_usd["tool_schema_compaction"] = delta_tool_schema_compaction_usd
            if delta_api_surface_slimming_usd:
                savings_by_source_usd["api_surface_slimming"] = delta_api_surface_slimming_usd
        savings_by_source_usd = {str(k): float(v) for k, v in savings_by_source_usd.items()}
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
            lifetime["scaffolding_tokens"] = (
                int(lifetime.get("scaffolding_tokens", 0)) + delta_scaffolding_tokens
            )
            lifetime["ghost_tokens"] = int(lifetime.get("ghost_tokens", 0)) + delta_ghost_tokens
            lifetime["compression_savings_usd"] = round(
                lifetime["compression_savings_usd"] + delta_savings_usd,
                6,
            )
            lifetime["cache_savings_usd"] = round(
                lifetime.get("cache_savings_usd", 0.0) + delta_cache_savings_usd,
                6,
            )
            lifetime["semantic_cache_savings_usd"] = round(
                lifetime.get("semantic_cache_savings_usd", 0.0) + delta_semantic_cache_usd,
                6,
            )
            lifetime["self_hosted_prefix_cache_savings_usd"] = round(
                lifetime.get("self_hosted_prefix_cache_savings_usd", 0.0) + delta_self_hosted_usd,
                6,
            )
            lifetime["model_routing_savings_usd"] = round(
                lifetime.get("model_routing_savings_usd", 0.0) + delta_model_routing_usd,
                6,
            )
            lifetime["tool_schema_compaction_savings_usd"] = round(
                lifetime.get("tool_schema_compaction_savings_usd", 0.0)
                + delta_tool_schema_compaction_usd,
                6,
            )
            lifetime["api_surface_slimming_savings_usd"] = round(
                lifetime.get("api_surface_slimming_savings_usd", 0.0)
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
            session["scaffolding_tokens"] = (
                int(session.get("scaffolding_tokens", 0)) + delta_scaffolding_tokens
            )
            session["ghost_tokens"] = int(session.get("ghost_tokens", 0)) + delta_ghost_tokens
            session["compression_savings_usd"] = round(
                session["compression_savings_usd"] + delta_savings_usd,
                6,
            )
            session["cache_savings_usd"] = round(
                session.get("cache_savings_usd", 0.0) + delta_cache_savings_usd,
                6,
            )
            session["semantic_cache_savings_usd"] = round(
                session.get("semantic_cache_savings_usd", 0.0) + delta_semantic_cache_usd,
                6,
            )
            session["self_hosted_prefix_cache_savings_usd"] = round(
                session.get("self_hosted_prefix_cache_savings_usd", 0.0) + delta_self_hosted_usd,
                6,
            )
            session["model_routing_savings_usd"] = round(
                session.get("model_routing_savings_usd", 0.0) + delta_model_routing_usd,
                6,
            )
            session["tool_schema_compaction_savings_usd"] = round(
                session.get("tool_schema_compaction_savings_usd", 0.0)
                + delta_tool_schema_compaction_usd,
                6,
            )
            session["api_surface_slimming_savings_usd"] = round(
                session.get("api_surface_slimming_savings_usd", 0.0)
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
            session["last_activity_at"] = _to_utc_iso(timestamp_dt)
            if session.get("started_at") is None:
                session["started_at"] = session["last_activity_at"]

            self._record_project_locked(
                project,
                timestamp_dt=timestamp_dt,
                requests_delta=1,
                tokens_saved_delta=delta_tokens_saved,
                savings_usd_delta=delta_savings_usd,
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
                    input_tokens_delta=delta_input_tokens,
                    input_cost_usd_delta=delta_input_cost_usd,
                )
            self._record_client_locked(
                client,
                timestamp_dt=timestamp_dt,
                requests_delta=1,
                tokens_saved_delta=delta_tokens_saved,
                savings_usd_delta=delta_savings_usd,
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
                        # Lifetime counters (running totals at this point).
                        "total_tokens_saved": lifetime["tokens_saved"],
                        "compression_savings_usd": lifetime["compression_savings_usd"],
                        "cache_savings_usd": round(lifetime.get("cache_savings_usd", 0.0), 6),
                        "semantic_cache_savings_usd": round(
                            lifetime.get("semantic_cache_savings_usd", 0.0), 6
                        ),
                        "self_hosted_prefix_cache_savings_usd": round(
                            lifetime.get("self_hosted_prefix_cache_savings_usd", 0.0),
                            6,
                        ),
                        "model_routing_savings_usd": round(
                            lifetime.get("model_routing_savings_usd", 0.0), 6
                        ),
                        "tool_schema_compaction_savings_usd": round(
                            lifetime.get("tool_schema_compaction_savings_usd", 0.0), 6
                        ),
                        "api_surface_slimming_savings_usd": round(
                            lifetime.get("api_surface_slimming_savings_usd", 0.0), 6
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

            self._save_locked()
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
        }

    def history_response(self, history_mode: str = "compact") -> dict[str, Any]:
        """Return frontend-friendly historical data for `/stats-history`."""
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
            return {
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
            }

    def _default_state(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "lifetime": {
                "requests": 0,
                "tokens_saved": 0,
                "compression_savings_usd": 0.0,
                "total_input_tokens": 0,
                "total_input_cost_usd": 0.0,
            },
            "display_session": _empty_display_session(),
            "history": [],
            "projects": {},
            "models": {},
            "clients": {},
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
        lifetime_input_tokens = 0
        lifetime_input_cost_usd = 0.0
        lifetime_extra_usd = dict.fromkeys(SESSION_SAVINGS_USD_FIELDS, 0.0)
        lifetime_source_tokens = dict.fromkeys(PERSISTED_SAVINGS_SOURCES, 0)
        lifetime_source_usd = dict.fromkeys(PERSISTED_SAVINGS_SOURCES, 0.0)
        if isinstance(lifetime_raw, dict):
            lifetime_requests = _coerce_int(lifetime_raw.get("requests"))
            lifetime_tokens_saved = _coerce_int(lifetime_raw.get("tokens_saved"))
            lifetime_savings_usd = _coerce_float(lifetime_raw.get("compression_savings_usd"))
            lifetime_input_tokens = _coerce_int(lifetime_raw.get("total_input_tokens"))
            lifetime_input_cost_usd = _coerce_float(lifetime_raw.get("total_input_cost_usd"))
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
                _coerce_float(last["compression_savings_usd"]),
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

        state = {
            "schema_version": SCHEMA_VERSION,
            "lifetime": {
                "requests": lifetime_requests,
                "tokens_saved": lifetime_tokens_saved,
                "compression_savings_usd": round(lifetime_savings_usd, 6),
                "total_input_tokens": lifetime_input_tokens,
                "total_input_cost_usd": round(lifetime_input_cost_usd, 6),
            },
            "display_session": _normalize_display_session(raw.get("display_session")),
            "history": normalized_history,
            "projects": _normalize_projects(raw.get("projects")),
            "models": _normalize_models(raw.get("models")),
            "clients": _normalize_clients(raw.get("clients")),
        }
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

    def _save_locked(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": SCHEMA_VERSION,
                "lifetime": self._state["lifetime"],
                "display_session": self._state["display_session"],
                "history": self._state["history"],
                "projects": self._state.get("projects", {}),
                "models": self._state.get("models", {}),
                "clients": self._state.get("clients", {}),
            }
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
        self._loaded_mtime = self._current_mtime()

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

        total_before = max(
            _coerce_int(session.get("tokens_saved")),
            _coerce_int(session.get("total_input_tokens")),
        )
        session["savings_percent"] = round(
            (_coerce_int(session.get("tokens_saved")) / total_before * 100)
            if total_before > 0
            else 0.0,
            2,
        )
        session["compression_savings_usd"] = round(
            _coerce_float(session.get("compression_savings_usd")),
            6,
        )
        session["total_input_cost_usd"] = round(
            _coerce_float(session.get("total_input_cost_usd")),
            6,
        )
        return session

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

            prev_total_tokens = total_tokens_saved
            prev_total_usd = total_usd
            prev_total_input_tokens = total_input_tokens
            prev_total_input_cost_usd = total_input_cost_usd

            entry = aggregated.setdefault(
                bucket_key,
                {
                    "timestamp": bucket_key,
                    "requests": 0,
                    "tokens_saved": 0,
                    "compression_savings_usd_delta": 0.0,
                    "total_tokens_saved": total_tokens_saved,
                    "compression_savings_usd": total_usd,
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
            entry["compression_savings_usd_delta"] = round(
                entry["compression_savings_usd_delta"] + delta_usd,
                6,
            )
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

        return list(aggregated.values())

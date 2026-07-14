"""Offline evidence store and calibration for model-routing shadow comparisons.

The primary request is never changed by this module. Callers may execute a
candidate response out of band, score it against the requested-model baseline,
and persist only sanitized decision/cost/quality evidence for later policy
calibration.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import threading
from collections.abc import Callable, Coroutine
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODEL_ROUTING_EVAL_PATH_ENV = "CUTCTX_MODEL_ROUTING_EVAL_PATH"
MODEL_ROUTING_SHADOW_MODE_ENV = "CUTCTX_MODEL_ROUTING_SHADOW_MODE"
MODEL_ROUTING_SHADOW_SAMPLE_RATE_ENV = "CUTCTX_MODEL_ROUTING_SHADOW_SAMPLE_RATE"
DEFAULT_MODEL_ROUTING_EVAL_PATH = ".cutctx/model_routing_evals.jsonl"
_MODEL_ROUTING_SHADOW_TASKS: set[asyncio.Task[Any]] = set()


def schedule_model_routing_shadow(
    coroutine: Coroutine[Any, Any, Any],
) -> asyncio.Task[Any]:
    """Schedule best-effort shadow work without delaying the primary response."""

    task = asyncio.get_running_loop().create_task(coroutine)
    _MODEL_ROUTING_SHADOW_TASKS.add(task)

    def consume_result(completed: asyncio.Task[Any]) -> None:
        _MODEL_ROUTING_SHADOW_TASKS.discard(completed)
        if not completed.cancelled():
            completed.exception()

    task.add_done_callback(consume_result)
    return task


def should_sample_model_routing_shadow(request_id: str, sample_rate: float) -> bool:
    """Return a stable sampling decision for a request identity."""

    rate = min(max(float(sample_rate), 0.0), 1.0)
    if rate <= 0.0 or not request_id:
        return False
    if rate >= 1.0:
        return True
    digest = hashlib.sha256(request_id.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") / float(2**64)
    return bucket < rate


def model_routing_shadow_enabled_from_env() -> bool:
    raw = os.environ.get(MODEL_ROUTING_SHADOW_MODE_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def model_routing_shadow_sample_rate_from_env() -> float:
    return _bounded_float(os.environ.get(MODEL_ROUTING_SHADOW_SAMPLE_RATE_ENV), 0.0, 1.0)


def prompt_fingerprint(messages: list[dict[str, Any]]) -> str:
    """Create a stable fingerprint without persisting prompt content."""

    canonical = json.dumps(messages, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


ROUTING_FEATURE_NAMES = (
    "word_count",
    "char_count",
    "message_count",
    "has_prior_turns",
    "has_code",
    "has_tool_context",
    "has_reference",
    "has_high_risk_intent",
    "is_multiline",
    "is_question",
)


def extract_routing_features(messages: list[dict[str, Any]]) -> dict[str, float]:
    """Extract bounded structural features without retaining request text."""

    last_user = next(
        (message for message in reversed(messages) if message.get("role") == "user"), {}
    )
    content = last_user.get("content", "")
    text = content if isinstance(content, str) else ""
    normalized = text.strip().lower()
    words = normalized.split()
    code_markers = ("```", "diff --git", "traceback", "stack trace", "begin patch")
    reference_markers = (
        " this",
        " that",
        " these",
        " those",
        " first ",
        " second ",
        " above",
        " earlier",
        " previous",
    )
    risk_markers = (
        "implement",
        "debug",
        "refactor",
        "architecture",
        "migration",
        "security",
        "production",
        "deploy",
        "release",
        "billing",
        "authentication",
        "authorization",
    )
    has_tool_context = any(
        message.get("role") == "tool"
        or not isinstance(message.get("content", ""), str)
        or "tool" in str(message.get("role", "")).lower()
        for message in messages
    )
    padded = f" {normalized} "
    return {
        "word_count": min(len(words) / 64.0, 1.0),
        "char_count": min(len(text) / 512.0, 1.0),
        "message_count": min(len(messages) / 12.0, 1.0),
        "has_prior_turns": float(len(messages) > 1),
        "has_code": float(any(marker in normalized for marker in code_markers)),
        "has_tool_context": float(has_tool_context),
        "has_reference": float(any(marker in padded for marker in reference_markers)),
        "has_high_risk_intent": float(any(marker in normalized for marker in risk_markers)),
        "is_multiline": float("\n" in text),
        "is_question": float(normalized.endswith("?")),
    }


@dataclass(frozen=True)
class ModelRoutingEvalRecord:
    request_id: str
    prompt_hash: str
    source_model: str
    candidate_model: str
    scorer: str
    confidence: float
    quality_score: float
    source_cost_usd: float
    candidate_cost_usd: float
    timestamp: str = ""
    category: str = ""
    features: dict[str, float] = field(default_factory=dict)
    segments: dict[str, str] = field(default_factory=dict)

    @property
    def savings_usd(self) -> float:
        return self.source_cost_usd - self.candidate_cost_usd

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp or datetime.now(timezone.utc).isoformat()
        payload["savings_usd"] = round(self.savings_usd, 8)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ModelRoutingEvalRecord:
        return cls(
            request_id=str(payload.get("request_id", "")),
            prompt_hash=str(payload.get("prompt_hash", "")),
            source_model=str(payload.get("source_model", "")),
            candidate_model=str(payload.get("candidate_model", "")),
            scorer=str(payload.get("scorer", "")),
            confidence=_bounded_float(payload.get("confidence"), 0.0, 1.0),
            quality_score=_bounded_float(payload.get("quality_score"), 0.0, 1.0),
            source_cost_usd=_finite_float(payload.get("source_cost_usd")),
            candidate_cost_usd=_finite_float(payload.get("candidate_cost_usd")),
            timestamp=str(payload.get("timestamp", "")),
            category=str(payload.get("category", "")),
            features={
                name: _bounded_float((payload.get("features") or {}).get(name), 0.0, 1.0)
                for name in ROUTING_FEATURE_NAMES
            }
            if isinstance(payload.get("features"), dict)
            else {},
            segments={
                str(key): str(value)
                for key, value in (payload.get("segments") or {}).items()
                if key in {"client", "task_type", "workspace_hash", "repository_hash"}
            }
            if isinstance(payload.get("segments"), dict)
            else {},
        )


class ModelRoutingEvalStore:
    """Thread-safe append-only JSONL store for sanitized shadow evidence."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.environ.get(MODEL_ROUTING_EVAL_PATH_ENV)
        self.path = Path(configured or DEFAULT_MODEL_ROUTING_EVAL_PATH).expanduser()
        self._lock = threading.Lock()

    def append(self, record: ModelRoutingEvalRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(rendered + "\n")

    def load(self) -> list[ModelRoutingEvalRecord]:
        if not self.path.exists():
            return []
        records: list[ModelRoutingEvalRecord] = []
        with self._lock, self.path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = json.loads(line)
                    if isinstance(payload, dict):
                        records.append(ModelRoutingEvalRecord.from_dict(payload))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
        return records


def record_model_routing_comparison(
    store: ModelRoutingEvalStore,
    *,
    request_id: str,
    messages: list[dict[str, Any]],
    source_model: str,
    candidate_model: str,
    scorer: str,
    confidence: float,
    baseline_response: str,
    candidate_response: str,
    source_cost_usd: float,
    candidate_cost_usd: float,
    category: str = "",
    segments: dict[str, str] | None = None,
    judge: Callable[[str, str, str], tuple[float, str]] | None = None,
) -> ModelRoutingEvalRecord:
    """Score and persist one shadow comparison without storing response text.

    Judge scores may use the repository's common 1-5 evaluator contract. They
    are normalized to 0-1 before persistence. The default is the local F1
    evaluator and therefore performs no additional model call.
    """

    if judge is None:
        from cutctx.evals.memory.judge import simple_judge

        judge = simple_judge
    question = _last_user_text(messages)
    score, _reasoning = judge(question, baseline_response, candidate_response)
    record = ModelRoutingEvalRecord(
        request_id=request_id,
        prompt_hash=prompt_fingerprint(messages),
        source_model=source_model,
        candidate_model=candidate_model,
        scorer=scorer,
        confidence=confidence,
        quality_score=_bounded_float(float(score) / 5.0, 0.0, 1.0),
        source_cost_usd=source_cost_usd,
        candidate_cost_usd=candidate_cost_usd,
        category=category,
        features=extract_routing_features(messages),
        segments=sanitize_routing_segments(segments or {}),
    )
    store.append(record)
    return record


async def maybe_run_model_routing_shadow(
    *,
    request_id: str,
    messages: list[dict[str, Any]],
    source_model: str,
    candidate_model: str,
    scorer: str,
    confidence: float,
    candidate_response: str,
    candidate_cost_usd: float,
    baseline_call: Callable[[], Any],
    store: ModelRoutingEvalStore | None = None,
    sample_rate: float | None = None,
    enabled: bool | None = None,
    judge: Callable[[str, str, str], tuple[float, str]] | None = None,
    category: str = "",
    segments: dict[str, str] | None = None,
) -> ModelRoutingEvalRecord | None:
    """Run a sampled baseline call and record evidence, never raising.

    ``baseline_call`` may return ``(response_text, cost_usd)`` directly or an
    awaitable resolving to that tuple. This keeps transport-specific replay in
    the compatibility handler while centralizing sampling, privacy, judging,
    and failure isolation.
    """

    active = model_routing_shadow_enabled_from_env() if enabled is None else enabled
    rate = model_routing_shadow_sample_rate_from_env() if sample_rate is None else sample_rate
    if not active or not should_sample_model_routing_shadow(request_id, rate):
        return None
    try:
        result = baseline_call()
        if hasattr(result, "__await__"):
            result = await result
        baseline_response, source_cost_usd = result
        return record_model_routing_comparison(
            store or ModelRoutingEvalStore(),
            request_id=request_id,
            messages=messages,
            source_model=source_model,
            candidate_model=candidate_model,
            scorer=scorer,
            confidence=confidence,
            baseline_response=str(baseline_response),
            candidate_response=candidate_response,
            source_cost_usd=float(source_cost_usd),
            candidate_cost_usd=candidate_cost_usd,
            category=category,
            segments=segments,
            judge=judge,
        )
    except Exception:
        return None


def build_quality_cost_frontier(
    records: list[ModelRoutingEvalRecord],
    *,
    quality_floor: float = 0.8,
) -> list[dict[str, Any]]:
    """Evaluate every observed confidence threshold as a routing policy."""

    if not records:
        return []
    thresholds = sorted({record.confidence for record in records}, reverse=True)
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        routed = [record for record in records if record.confidence >= threshold]
        quality = sum(record.quality_score for record in routed) / len(routed)
        unsafe = sum(record.quality_score < quality_floor for record in routed)
        rows.append(
            {
                "minimum_confidence": threshold,
                "routed_samples": len(routed),
                "routing_rate": len(routed) / len(records),
                "mean_quality": quality,
                "unsafe_rate": unsafe / len(routed),
                "total_savings_usd": sum(record.savings_usd for record in routed),
                "mean_savings_usd": sum(record.savings_usd for record in routed) / len(routed),
            }
        )
    return rows


def recommend_confidence_threshold(
    records: list[ModelRoutingEvalRecord],
    *,
    minimum_mean_quality: float = 0.9,
    maximum_unsafe_rate: float = 0.01,
    quality_floor: float = 0.8,
) -> dict[str, Any] | None:
    """Choose the highest-savings observed policy satisfying quality limits."""

    eligible = [
        row
        for row in build_quality_cost_frontier(records, quality_floor=quality_floor)
        if row["mean_quality"] >= minimum_mean_quality and row["unsafe_rate"] <= maximum_unsafe_rate
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda row: (
            row["total_savings_usd"],
            row["routed_samples"],
            row["minimum_confidence"],
        ),
    )


def build_segmented_recommendations(
    records: list[ModelRoutingEvalRecord],
    *,
    minimum_samples: int = 20,
    minimum_mean_quality: float = 0.9,
    maximum_unsafe_rate: float = 0.01,
    quality_floor: float = 0.8,
) -> dict[str, Any]:
    """Recommend thresholds per safe segment with global fallback."""

    global_recommendation = recommend_confidence_threshold(
        records,
        minimum_mean_quality=minimum_mean_quality,
        maximum_unsafe_rate=maximum_unsafe_rate,
        quality_floor=quality_floor,
    )
    dimensions: dict[str, dict[str, Any]] = {}
    segment_values: dict[str, set[str]] = {
        "client": set(),
        "task_type": set(),
        "model_pair": set(),
        "workspace_hash": set(),
        "repository_hash": set(),
    }
    for record in records:
        segment_values["model_pair"].add(f"{record.source_model}->{record.candidate_model}")
        segment_values["task_type"].add(record.segments.get("task_type") or record.category)
        for dimension in ("client", "workspace_hash", "repository_hash"):
            value = record.segments.get(dimension)
            if value:
                segment_values[dimension].add(value)

    for dimension, values in segment_values.items():
        dimension_rows: dict[str, Any] = {}
        for value in sorted(filter(None, values)):
            selected = [record for record in records if _segment_value(record, dimension) == value]
            recommendation = (
                recommend_confidence_threshold(
                    selected,
                    minimum_mean_quality=minimum_mean_quality,
                    maximum_unsafe_rate=maximum_unsafe_rate,
                    quality_floor=quality_floor,
                )
                if len(selected) >= minimum_samples
                else None
            )
            dimension_rows[value] = {
                "samples": len(selected),
                "status": "promoted"
                if recommendation is not None
                else "global_fallback"
                if len(selected) < minimum_samples
                else "quality_blocked",
                "recommendation": recommendation,
                "effective_minimum_confidence": (recommendation or global_recommendation or {}).get(
                    "minimum_confidence"
                ),
            }
        dimensions[dimension] = dimension_rows
    return {
        "minimum_segment_samples": minimum_samples,
        "global_recommendation": global_recommendation,
        "dimensions": dimensions,
    }


def build_model_routing_evidence_report(
    records: list[ModelRoutingEvalRecord],
    *,
    minimum_samples: int = 20,
    minimum_mean_quality: float = 0.9,
    maximum_unsafe_rate: float = 0.01,
    quality_floor: float = 0.8,
) -> dict[str, Any]:
    """Build a privacy-safe readiness report for operator routing decisions."""

    required_samples = max(1, int(minimum_samples))
    sample_count = len(records)
    frontier = build_quality_cost_frontier(records, quality_floor=quality_floor)
    recommendation = (
        recommend_confidence_threshold(
            records,
            minimum_mean_quality=minimum_mean_quality,
            maximum_unsafe_rate=maximum_unsafe_rate,
            quality_floor=quality_floor,
        )
        if sample_count >= required_samples
        else None
    )
    if sample_count == 0:
        status = "no_evidence"
    elif sample_count < required_samples:
        status = "collecting"
    elif recommendation is None:
        status = "quality_blocked"
    else:
        status = "ready"

    segmented = build_segmented_recommendations(
        records,
        minimum_samples=required_samples,
        minimum_mean_quality=minimum_mean_quality,
        maximum_unsafe_rate=maximum_unsafe_rate,
        quality_floor=quality_floor,
    )
    if sample_count < required_samples:
        segmented["global_recommendation"] = None
        for dimension_rows in segmented["dimensions"].values():
            for row in dimension_rows.values():
                row["status"] = "collecting"
                row["recommendation"] = None
                row["effective_minimum_confidence"] = None

    return {
        "schema_version": 1,
        "status": status,
        "samples": sample_count,
        "sample_progress": {
            "observed": sample_count,
            "required": required_samples,
            "fraction": min(sample_count / required_samples, 1.0),
        },
        "constraints": {
            "minimum_samples": required_samples,
            "minimum_mean_quality": minimum_mean_quality,
            "maximum_unsafe_rate": maximum_unsafe_rate,
            "quality_floor": quality_floor,
        },
        "recommendation": recommendation,
        "frontier": frontier,
        "segmented": segmented,
    }


def sanitize_routing_segments(segments: dict[str, str]) -> dict[str, str]:
    """Keep low-cardinality labels and hash repository/workspace identities."""

    result: dict[str, str] = {}
    for key in ("client", "task_type"):
        value = str(segments.get(key, "")).strip().lower()
        if value:
            result[key] = value[:64]
    for key in ("workspace", "repository"):
        value = str(segments.get(key, "")).strip()
        if value:
            result[f"{key}_hash"] = hashlib.sha256(value.encode()).hexdigest()
    return result


def _segment_value(record: ModelRoutingEvalRecord, dimension: str) -> str:
    if dimension == "model_pair":
        return f"{record.source_model}->{record.candidate_model}"
    if dimension == "task_type":
        return record.segments.get("task_type") or record.category
    return record.segments.get(dimension, "")


def _finite_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _bounded_float(value: Any, lower: float, upper: float) -> float:
    return min(max(_finite_float(value), lower), upper)


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return str(message["content"])
    return ""


__all__ = [
    "DEFAULT_MODEL_ROUTING_EVAL_PATH",
    "MODEL_ROUTING_EVAL_PATH_ENV",
    "MODEL_ROUTING_SHADOW_MODE_ENV",
    "MODEL_ROUTING_SHADOW_SAMPLE_RATE_ENV",
    "ModelRoutingEvalRecord",
    "ModelRoutingEvalStore",
    "ROUTING_FEATURE_NAMES",
    "build_model_routing_evidence_report",
    "build_quality_cost_frontier",
    "build_segmented_recommendations",
    "extract_routing_features",
    "maybe_run_model_routing_shadow",
    "model_routing_shadow_enabled_from_env",
    "model_routing_shadow_sample_rate_from_env",
    "prompt_fingerprint",
    "record_model_routing_comparison",
    "recommend_confidence_threshold",
    "sanitize_routing_segments",
    "schedule_model_routing_shadow",
    "should_sample_model_routing_shadow",
]

"""Deterministic savings canaries and hard regression guardrails.

The coordinator is deliberately dependency-free so every provider adapter can
use the same assignment and reporting contract.  Assignment is stable for a
caller-supplied identity and treatment arms are mutually exclusive.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Literal

CanaryArm = Literal[
    "control",
    "mutable_tail",
    "tool_api_slimming",
    "model_routing",
]

TREATMENT_ARMS: tuple[CanaryArm, ...] = (
    "mutable_tail",
    "tool_api_slimming",
    "model_routing",
)

_STATE_SCHEMA_VERSION = 1
_MAX_PERSISTED_IDENTITIES = 50_000


class CanaryStateError(RuntimeError):
    """Raised when persisted experiment state cannot safely be reused."""


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class CanaryAssignment:
    arm: CanaryArm = "control"
    eligible: bool = False
    enabled: bool = False
    reason: str = "canary_disabled"
    bucket: int = 99
    assignment_identity_source: str = "unknown"
    assignment_sticky: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _ArmMetrics:
    requests: int = 0
    input_tokens: int = 0
    created_savings_usd: float = 0.0
    observed_provider_savings_usd: float = 0.0
    combined_savings_usd: float = 0.0
    provider_cache_value_usd: float = 0.0
    quality_samples: int = 0
    quality_successes: int = 0
    retries: int = 0
    user_corrections: int = 0
    latency_ms: float = 0.0
    created_rate_samples: int = 0
    created_rate_sum: float = 0.0
    created_rate_sum_squares: float = 0.0

    def snapshot(self) -> dict[str, Any]:
        created_per_million = (
            self.created_savings_usd * 1_000_000 / self.input_tokens
            if self.input_tokens > 0
            else 0.0
        )
        quality_rate = (
            self.quality_successes / self.quality_samples
            if self.quality_samples > 0
            else None
        )
        rate_ci = None
        if self.created_rate_samples > 1:
            sample_mean = self.created_rate_sum / self.created_rate_samples
            variance = max(
                (self.created_rate_sum_squares - self.created_rate_samples * sample_mean**2)
                / (self.created_rate_samples - 1),
                0.0,
            )
            margin = 1.96 * math.sqrt(variance / self.created_rate_samples)
            rate_ci = [round(max(0.0, sample_mean - margin), 6), round(sample_mean + margin, 6)]
        quality_ci = None
        if quality_rate is not None and self.quality_samples > 0:
            margin = 1.96 * math.sqrt(
                quality_rate * (1.0 - quality_rate) / self.quality_samples
            )
            quality_ci = [
                round(max(0.0, quality_rate - margin), 6),
                round(min(1.0, quality_rate + margin), 6),
            ]
        return {
            **asdict(self),
            "created_savings_usd_per_million_input_tokens": round(created_per_million, 6),
            "quality_success_rate": round(quality_rate, 6) if quality_rate is not None else None,
            "created_savings_rate_95_percent_ci": rate_ci,
            "quality_success_95_percent_ci": quality_ci,
            "average_latency_ms": round(self.latency_ms / self.requests, 3)
            if self.requests
            else 0.0,
        }


@dataclass
class SavingsCanaryCoordinator:
    enabled: bool = False
    allocation_percent: int = 10
    regression_limit: float = 0.01
    min_samples: int = 100
    salt: str = "cutctx-savings-canary-v1"
    state_path: str | os.PathLike[str] | None = None
    allow_non_sticky: bool = False
    _metrics: dict[CanaryArm, _ArmMetrics] = field(default_factory=dict, init=False)
    _paused: dict[CanaryArm, str] = field(default_factory=dict, init=False)
    _allocations: dict[CanaryArm, int] = field(default_factory=dict, init=False)
    _sticky_assignments: dict[str, CanaryArm] = field(default_factory=dict, init=False)
    _feedback_event_ids: dict[str, None] = field(default_factory=dict, init=False)
    _baseline_payload: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.allocation_percent = max(0, min(int(self.allocation_percent), 10))
        self.regression_limit = max(0.0, float(self.regression_limit))
        self.min_samples = max(1, int(self.min_samples))
        self._metrics = {arm: _ArmMetrics() for arm in ("control", *TREATMENT_ARMS)}
        self._allocations = dict.fromkeys(TREATMENT_ARMS, self.allocation_percent)
        if self.state_path is not None:
            self.state_path = str(Path(self.state_path).expanduser())
        if self.state_path is not None and self.enabled:
            self._load_state()
        self._baseline_payload = self._state_payload_locked()

    @classmethod
    def from_env(cls) -> SavingsCanaryCoordinator:
        return cls(
            enabled=_env_bool("CUTCTX_SAVINGS_CANARY_ENABLED", False),
            allocation_percent=int(os.environ.get("CUTCTX_SAVINGS_CANARY_PERCENT", "10")),
            regression_limit=float(os.environ.get("CUTCTX_SAVINGS_CANARY_REGRESSION_LIMIT", "0.01")),
            min_samples=int(os.environ.get("CUTCTX_SAVINGS_CANARY_MIN_SAMPLES", "100")),
            salt=os.environ.get("CUTCTX_SAVINGS_CANARY_SALT", "cutctx-savings-canary-v1"),
            state_path=os.environ.get(
                "CUTCTX_SAVINGS_CANARY_PATH",
                "~/.cutctx/savings_canary.json",
            ),
            allow_non_sticky=_env_bool("CUTCTX_SAVINGS_CANARY_ALLOW_NON_STICKY", False),
        )

    @property
    def salt_fingerprint(self) -> str:
        return hashlib.sha256(self.salt.encode("utf-8")).hexdigest()[:16]

    def _quarantine_state(self, path: Path, reason: str) -> None:
        quarantined = path.with_name(f"{path.name}.{reason}.{int(time.time())}.quarantine")
        try:
            os.replace(path, quarantined)
        except OSError:
            pass

    def _load_state(self) -> None:
        path = Path(str(self.state_path))
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            self._quarantine_state(path, "corrupt")
            return
        if payload.get("schema_version") != _STATE_SCHEMA_VERSION:
            self._quarantine_state(path, "unsupported-schema")
            return
        persisted_fingerprint = str(payload.get("salt_fingerprint") or "")
        if persisted_fingerprint != self.salt_fingerprint:
            raise CanaryStateError(
                "savings canary salt differs from persisted experiment state; "
                "archive the state file or restore the original salt before starting"
            )
        try:
            allocations = {
                arm: max(0, int((payload.get("allocations") or {}).get(arm, 0)))
                for arm in TREATMENT_ARMS
            }
            if sum(allocations.values()) > 100:
                raise ValueError("persisted treatment allocations exceed 100 percent")
            paused = {
                arm: str(reason)
                for arm, reason in (payload.get("paused") or {}).items()
                if arm in TREATMENT_ARMS
            }
            metrics_payload = payload.get("metrics") or {}
            metrics = {
                arm: _ArmMetrics(
                    **{
                        key: value
                        for key, value in (metrics_payload.get(arm) or {}).items()
                        if key in _ArmMetrics.__dataclass_fields__
                    }
                )
                for arm in ("control", *TREATMENT_ARMS)
            }
            sticky = {
                str(identity_hash): arm
                for identity_hash, arm in (payload.get("sticky_assignments") or {}).items()
                if arm in ("control", *TREATMENT_ARMS)
            }
            feedback_ids = {
                str(event_id): None
                for event_id in (payload.get("feedback_event_ids") or [])
                if str(event_id).strip()
            }
        except (TypeError, ValueError):
            self._quarantine_state(path, "invalid")
            return
        self._allocations = allocations
        self._paused = paused
        self._metrics = metrics
        self._sticky_assignments = dict(list(sticky.items())[-_MAX_PERSISTED_IDENTITIES:])
        self._feedback_event_ids = dict(
            list(feedback_ids.items())[-_MAX_PERSISTED_IDENTITIES:]
        )

    def _state_payload_locked(self) -> dict[str, Any]:
        return {
            "schema_version": _STATE_SCHEMA_VERSION,
            "salt_fingerprint": self.salt_fingerprint,
            "allocations": dict(self._allocations),
            "paused": dict(self._paused),
            "metrics": {arm: asdict(metrics) for arm, metrics in self._metrics.items()},
            "sticky_assignments": dict(self._sticky_assignments),
            "feedback_event_ids": list(self._feedback_event_ids),
        }

    def _persist_locked(self, *, existing_lock_fd: int | None = None) -> None:
        if self.state_path is None:
            return
        path = Path(str(self.state_path))
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_path = path.with_suffix(f"{path.suffix}.lock")
        owns_file_lock = existing_lock_fd is None
        lock_fd = (
            os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            if existing_lock_fd is None
            else existing_lock_fd
        )
        try:
            if owns_file_lock:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            local_payload = self._state_payload_locked()
            disk_payload: dict[str, Any] = {
                "schema_version": _STATE_SCHEMA_VERSION,
                "salt_fingerprint": self.salt_fingerprint,
                "allocations": dict.fromkeys(TREATMENT_ARMS, 0),
                "paused": {},
                "metrics": {
                    arm: asdict(_ArmMetrics()) for arm in ("control", *TREATMENT_ARMS)
                },
                "sticky_assignments": {},
                "feedback_event_ids": [],
            }
            if path.exists():
                try:
                    candidate = json.loads(path.read_text(encoding="utf-8"))
                    if candidate.get("schema_version") != _STATE_SCHEMA_VERSION:
                        raise CanaryStateError("unsupported savings canary state schema")
                    if candidate.get("salt_fingerprint") != self.salt_fingerprint:
                        raise CanaryStateError(
                            "savings canary salt differs from persisted experiment state"
                        )
                    disk_payload = candidate
                except CanaryStateError:
                    raise
                except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
                    raise CanaryStateError(
                        "savings canary state became unreadable while the experiment was active"
                    ) from exc

            baseline_metrics = self._baseline_payload.get("metrics") or {}
            disk_metrics = disk_payload.get("metrics") or {}
            local_metrics = local_payload.get("metrics") or {}
            merged_metrics: dict[str, dict[str, int | float]] = {}
            for arm in ("control", *TREATMENT_ARMS):
                merged_metrics[arm] = {}
                for field_name in _ArmMetrics.__dataclass_fields__:
                    disk_value = (disk_metrics.get(arm) or {}).get(field_name, 0)
                    local_value = (local_metrics.get(arm) or {}).get(field_name, 0)
                    baseline_value = (baseline_metrics.get(arm) or {}).get(field_name, 0)
                    merged_metrics[arm][field_name] = disk_value + max(
                        local_value - baseline_value, 0
                    )

            merged_allocations = {
                arm: max(
                    int((disk_payload.get("allocations") or {}).get(arm, 0)),
                    int((local_payload.get("allocations") or {}).get(arm, 0)),
                )
                for arm in TREATMENT_ARMS
            }
            if sum(merged_allocations.values()) > 100:
                raise CanaryStateError("merged treatment allocations exceed 100 percent")
            merged_paused = dict(disk_payload.get("paused") or {})
            merged_paused.update(local_payload.get("paused") or {})
            merged_sticky = dict(disk_payload.get("sticky_assignments") or {})
            merged_sticky.update(local_payload.get("sticky_assignments") or {})
            merged_sticky = dict(
                list(merged_sticky.items())[-_MAX_PERSISTED_IDENTITIES:]
            )
            merged_feedback = dict.fromkeys(disk_payload.get("feedback_event_ids") or [])
            merged_feedback.update(
                dict.fromkeys(local_payload.get("feedback_event_ids") or [])
            )
            merged_payload = {
                "schema_version": _STATE_SCHEMA_VERSION,
                "salt_fingerprint": self.salt_fingerprint,
                "allocations": merged_allocations,
                "paused": merged_paused,
                "metrics": merged_metrics,
                "sticky_assignments": merged_sticky,
                "feedback_event_ids": list(merged_feedback)[-_MAX_PERSISTED_IDENTITIES:],
            }

            # Keep this worker synchronized with observations committed by
            # sibling processes before serializing the merged transaction.
            self._allocations = merged_allocations
            self._paused = merged_paused
            self._metrics = {
                arm: _ArmMetrics(**merged_metrics[arm])
                for arm in ("control", *TREATMENT_ARMS)
            }
            self._sticky_assignments = merged_sticky
            self._feedback_event_ids = dict.fromkeys(merged_payload["feedback_event_ids"])
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(merged_payload, handle, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, path)
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                self._baseline_payload = merged_payload
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        finally:
            if owns_file_lock:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)

    @staticmethod
    def is_eligible(*, client: str | None, model: str | None) -> bool:
        client_name = (client or "").strip().lower()
        model_name = (model or "").strip().lower()
        return client_name == "codex" or model_name.startswith("gpt-5")

    def assign(
        self,
        identity: str,
        *,
        client: str | None = None,
        model: str | None = None,
        identity_source: str = "caller",
        sticky: bool = True,
    ) -> CanaryAssignment:
        if not self.enabled:
            return CanaryAssignment(reason="canary_disabled")
        if not self.is_eligible(client=client, model=model):
            return CanaryAssignment(
                enabled=True,
                reason="ineligible_client_or_model",
                assignment_identity_source=identity_source,
                assignment_sticky=sticky,
            )
        if not sticky and not self.allow_non_sticky:
            return CanaryAssignment(
                arm="control",
                eligible=True,
                enabled=True,
                reason="non_sticky_identity_excluded",
                assignment_identity_source=identity_source,
                assignment_sticky=False,
            )
        stable_identity = identity.strip() or f"{client or 'unknown'}:{model or 'unknown'}"
        identity_hash = hashlib.sha256(f"{self.salt}:{stable_identity}".encode()).hexdigest()
        digest = bytes.fromhex(identity_hash)
        bucket = int.from_bytes(digest[:8], "big") % 100
        with self._lock:
            allocations = dict(self._allocations)
            arm = self._sticky_assignments.get(identity_hash)
        if arm is None:
            cursor = 0
            arm = "control"
            for candidate in TREATMENT_ARMS:
                width = allocations[candidate]
                if cursor <= bucket < cursor + width:
                    arm = candidate
                    break
                cursor += width
            with self._lock:
                self._sticky_assignments[identity_hash] = arm
                while len(self._sticky_assignments) > _MAX_PERSISTED_IDENTITIES:
                    self._sticky_assignments.pop(next(iter(self._sticky_assignments)))
                self._persist_locked()
        with self._lock:
            paused_reason = self._paused.get(arm)
        if paused_reason:
            return CanaryAssignment(
                arm="control",
                eligible=True,
                enabled=True,
                reason=f"arm_paused:{paused_reason}",
                bucket=bucket,
                assignment_identity_source=identity_source,
                assignment_sticky=sticky,
            )
        return CanaryAssignment(
            arm=arm,
            eligible=True,
            enabled=True,
            reason="assigned",
            bucket=bucket,
            assignment_identity_source=identity_source,
            assignment_sticky=sticky,
        )

    def record(
        self,
        arm: CanaryArm,
        *,
        input_tokens: int,
        created_savings_usd: float,
        observed_provider_savings_usd: float,
        provider_cache_value_usd: float | None = None,
        quality_success: bool | None = None,
        retries: int = 0,
        user_corrections: int = 0,
        latency_ms: float = 0.0,
    ) -> None:
        if not self.enabled:
            return
        if arm not in self._metrics:
            arm = "control"
        with self._lock:
            metrics = self._metrics[arm]
            metrics.requests += 1
            metrics.input_tokens += max(0, int(input_tokens))
            metrics.created_savings_usd += max(0.0, float(created_savings_usd))
            metrics.observed_provider_savings_usd += max(
                0.0, float(observed_provider_savings_usd)
            )
            metrics.combined_savings_usd += max(
                0.0, float(created_savings_usd) + float(observed_provider_savings_usd)
            )
            metrics.provider_cache_value_usd += max(
                0.0,
                float(
                    observed_provider_savings_usd
                    if provider_cache_value_usd is None
                    else provider_cache_value_usd
                ),
            )
            if quality_success is not None:
                metrics.quality_samples += 1
                metrics.quality_successes += int(bool(quality_success))
            metrics.retries += max(0, int(retries))
            metrics.user_corrections += max(0, int(user_corrections))
            metrics.latency_ms += max(0.0, float(latency_ms))
            if input_tokens > 0:
                created_rate = max(0.0, float(created_savings_usd)) * 1_000_000 / input_tokens
                metrics.created_rate_samples += 1
                metrics.created_rate_sum += created_rate
                metrics.created_rate_sum_squares += created_rate**2
            if arm != "control":
                reason = self._regression_reason_locked(arm)
                if reason:
                    self._paused[arm] = reason
            self._persist_locked()

    def _regression_reason_locked(self, arm: CanaryArm) -> str | None:
        control = self._metrics["control"]
        treatment = self._metrics[arm]
        if control.requests < self.min_samples or treatment.requests < self.min_samples:
            return None
        control_snap = control.snapshot()
        treatment_snap = treatment.snapshot()
        cq = control_snap["quality_success_rate"]
        tq = treatment_snap["quality_success_rate"]
        if cq is not None and tq is not None and tq < cq * (1.0 - self.regression_limit):
            return "quality_regression"
        control_cache = (
            control.provider_cache_value_usd / control.input_tokens
            if control.input_tokens > 0
            else 0.0
        )
        treatment_cache = (
            treatment.provider_cache_value_usd / treatment.input_tokens
            if treatment.input_tokens > 0
            else 0.0
        )
        if control_cache > 0 and treatment_cache < control_cache * (1.0 - self.regression_limit):
            return "provider_cache_regression"
        control_combined = (
            control.combined_savings_usd / control.input_tokens
            if control.input_tokens > 0
            else 0.0
        )
        treatment_combined = (
            treatment.combined_savings_usd / treatment.input_tokens
            if treatment.input_tokens > 0
            else 0.0
        )
        if treatment_combined < control_combined:
            return "combined_savings_regression"
        return None

    def record_feedback(
        self,
        arm: CanaryArm,
        *,
        event_id: str,
        quality_success: bool,
        retries: int = 0,
        user_corrections: int = 0,
    ) -> bool:
        """Attach delayed task-quality feedback without double-counting a request."""
        if not self.enabled:
            return False
        normalized_event_id = event_id.strip()
        if not normalized_event_id:
            raise ValueError("event_id is required")
        if arm not in self._metrics:
            arm = "control"
        with self._lock:
            file_lock_fd: int | None = None
            if self.state_path is not None:
                path = Path(str(self.state_path))
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                lock_path = path.with_suffix(f"{path.suffix}.lock")
                file_lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
                fcntl.flock(file_lock_fd, fcntl.LOCK_EX)
                # Refresh under the same cross-process transaction lock before
                # checking the idempotency ledger.
                self._load_state()
                self._baseline_payload = self._state_payload_locked()
            try:
                if normalized_event_id in self._feedback_event_ids:
                    return True
                self._feedback_event_ids[normalized_event_id] = None
                while len(self._feedback_event_ids) > _MAX_PERSISTED_IDENTITIES:
                    self._feedback_event_ids.pop(next(iter(self._feedback_event_ids)))
                metrics = self._metrics[arm]
                metrics.quality_samples += 1
                metrics.quality_successes += int(bool(quality_success))
                metrics.retries += max(0, int(retries))
                metrics.user_corrections += max(0, int(user_corrections))
                if arm != "control":
                    reason = self._regression_reason_locked(arm)
                    if reason:
                        self._paused[arm] = reason
                self._persist_locked(existing_lock_fd=file_lock_fd)
            finally:
                if file_lock_fd is not None:
                    fcntl.flock(file_lock_fd, fcntl.LOCK_UN)
                    os.close(file_lock_fd)
        return False

    def report(self) -> dict[str, Any]:
        with self._lock:
            metrics = {arm: value.snapshot() for arm, value in self._metrics.items()}
            paused = dict(self._paused)
            allocations = dict(self._allocations)
        control_rate = metrics["control"]["created_savings_usd_per_million_input_tokens"]
        decisions: dict[str, dict[str, Any]] = {}
        for arm in TREATMENT_ARMS:
            treatment_rate = metrics[arm]["created_savings_usd_per_million_input_tokens"]
            lift = ((treatment_rate / control_rate) - 1.0) if control_rate > 0 else None
            decisions[arm] = {
                "paused": arm in paused,
                "pause_reason": paused.get(arm),
                "created_savings_lift_percent": round(lift * 100, 2)
                if lift is not None
                else None,
                "meets_20_percent_lift_target": bool(lift is not None and lift >= 0.20),
                "rollout_decision": "stop"
                if arm in paused
                else "promote_to_25_percent"
                if lift is not None
                and lift >= 0.20
                and metrics[arm]["requests"] >= self.min_samples
                and metrics[arm]["quality_samples"] >= self.min_samples
                and metrics["control"]["quality_samples"] >= self.min_samples
                else "collect_more_data",
            }
        return {
            "enabled": self.enabled,
            "allocation_percent_per_treatment": self.allocation_percent,
            "allocations": allocations,
            "control_percent": 100 - sum(allocations.values()),
            "regression_limit_percent": self.regression_limit * 100,
            "minimum_samples": self.min_samples,
            "metrics": metrics,
            "decisions": decisions,
        }

    def promote(self, arm: CanaryArm, percent: int) -> dict[str, Any]:
        if arm not in TREATMENT_ARMS:
            raise ValueError("only treatment arms can be promoted")
        if percent not in (10, 25, 50):
            raise ValueError("canary allocation must be 10, 25, or 50 percent")
        with self._lock:
            if arm in self._paused:
                raise ValueError(f"cannot promote paused arm: {self._paused[arm]}")
            current_percent = self._allocations[arm]
            if percent > current_percent:
                if percent != {10: 25, 25: 50}.get(current_percent):
                    raise ValueError("canary promotion must proceed from 10 to 25 to 50 percent")
                control = self._metrics["control"].snapshot()
                treatment = self._metrics[arm].snapshot()
                if (
                    control["requests"] < self.min_samples
                    or treatment["requests"] < self.min_samples
                    or control["quality_samples"] < self.min_samples
                    or treatment["quality_samples"] < self.min_samples
                ):
                    raise ValueError("cannot promote before the full evaluation window")
                control_rate = control[
                    "created_savings_usd_per_million_input_tokens"
                ]
                treatment_rate = treatment[
                    "created_savings_usd_per_million_input_tokens"
                ]
                if control_rate <= 0 or treatment_rate < control_rate * 1.20:
                    raise ValueError(
                        "cannot promote without at least 20 percent created-savings lift"
                    )
            next_allocations = dict(self._allocations)
            next_allocations[arm] = percent
            if sum(next_allocations.values()) > 100:
                raise ValueError("treatment allocations cannot exceed 100 percent")
            self._allocations = next_allocations
            self._persist_locked()
        return self.report()


_COORDINATOR: SavingsCanaryCoordinator | None = None
_COORDINATOR_LOCK = Lock()


def get_savings_canary_coordinator() -> SavingsCanaryCoordinator:
    global _COORDINATOR
    with _COORDINATOR_LOCK:
        if _COORDINATOR is None:
            _COORDINATOR = SavingsCanaryCoordinator.from_env()
        return _COORDINATOR


def reset_savings_canary_coordinator_for_tests() -> None:
    global _COORDINATOR
    with _COORDINATOR_LOCK:
        _COORDINATOR = None


__all__ = [
    "CanaryArm",
    "CanaryAssignment",
    "CanaryStateError",
    "SavingsCanaryCoordinator",
    "TREATMENT_ARMS",
    "get_savings_canary_coordinator",
    "reset_savings_canary_coordinator_for_tests",
]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Per-provider circuit breaker for upstream HTTP calls.

Commercial-readiness runbook Task 4: failover (``cutctx/proxy/routes/
failover.py``) can mark a provider unhealthy but has no time-window
backoff, so a dead upstream can be hammered by retry storms. This module
adds a small CLOSED -> OPEN -> HALF_OPEN state machine, one instance per
upstream provider (anthropic/openai/gemini/...), so the shared retry path
in ``server.py:_retry_request`` can fail fast instead of dialing a
provider that is known to be down.

Configuration is via environment variables (no config-schema change):
  * ``CUTCTX_CIRCUIT_FAILURE_THRESHOLD`` - consecutive failures before the
    breaker opens (default 5).
  * ``CUTCTX_CIRCUIT_COOLDOWN_S`` - seconds the breaker stays OPEN before
    allowing a HALF_OPEN probe request (default 30).

Failures are upstream-availability signals (connection errors, timeouts,
5xx responses) as classified by the caller - a 4xx response is a caller
error, not a provider outage, and should be reported via
``record_success`` (the provider *did* respond).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from enum import Enum

logger = logging.getLogger("cutctx.proxy.circuit_breaker")

DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_COOLDOWN_S = 30.0


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("event=circuit_breaker_bad_env var=%s value=%r; using default", name, raw)
        return default
    return value if value > 0 else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("event=circuit_breaker_bad_env var=%s value=%r; using default", name, raw)
        return default
    return value if value >= 0 else default


def failure_threshold_from_env() -> int:
    """Read ``CUTCTX_CIRCUIT_FAILURE_THRESHOLD`` (default 5)."""
    return _env_int("CUTCTX_CIRCUIT_FAILURE_THRESHOLD", DEFAULT_FAILURE_THRESHOLD)


def cooldown_s_from_env() -> float:
    """Read ``CUTCTX_CIRCUIT_COOLDOWN_S`` (default 30.0)."""
    return _env_float("CUTCTX_CIRCUIT_COOLDOWN_S", DEFAULT_COOLDOWN_S)


class CircuitState(str, Enum):
    """The three states of the breaker's state machine."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """CLOSED -> OPEN -> HALF_OPEN circuit breaker for one upstream provider.

    * CLOSED: requests flow normally; consecutive failures are counted.
    * OPEN: requests are rejected fast until ``cooldown_s`` has elapsed
      since the breaker opened.
    * HALF_OPEN: entered automatically once the cooldown elapses; the next
      request is treated as a probe. A single success closes the breaker;
      a single failure reopens it (and restarts the cooldown).

    ``failure_threshold``/``cooldown_s`` default to the
    ``CUTCTX_CIRCUIT_FAILURE_THRESHOLD``/``CUTCTX_CIRCUIT_COOLDOWN_S`` env
    vars (read at construction time) but may be overridden per-instance,
    which is primarily useful for tests.
    """

    def __init__(
        self,
        provider: str,
        failure_threshold: int | None = None,
        cooldown_s: float | None = None,
    ) -> None:
        self.provider = provider
        self.failure_threshold = (
            failure_threshold if failure_threshold is not None else failure_threshold_from_env()
        )
        self.cooldown_s = cooldown_s if cooldown_s is not None else cooldown_s_from_env()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Current state (resolves OPEN -> HALF_OPEN once cooldown elapses)."""
        with self._lock:
            self._maybe_transition_to_half_open_locked()
            return self._state

    def _maybe_transition_to_half_open_locked(self) -> None:
        """Caller must hold ``self._lock``."""
        if self._state is CircuitState.OPEN and self._opened_at is not None:
            if time.monotonic() - self._opened_at >= self.cooldown_s:
                self._state = CircuitState.HALF_OPEN
                logger.info("event=circuit_half_open provider=%s", self.provider)

    def allow_request(self) -> bool:
        """Return ``True`` if a request to this provider may proceed."""
        with self._lock:
            self._maybe_transition_to_half_open_locked()
            return self._state is not CircuitState.OPEN

    def record_success(self) -> None:
        """Report that a request to this provider succeeded."""
        with self._lock:
            if self._state is not CircuitState.CLOSED:
                logger.info("event=circuit_closed provider=%s", self.provider)
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        """Report that a request to this provider failed."""
        with self._lock:
            self._maybe_transition_to_half_open_locked()
            self._consecutive_failures += 1
            if self._state is CircuitState.HALF_OPEN:
                self._open_locked()
                return
            if (
                self._state is CircuitState.CLOSED
                and self._consecutive_failures >= self.failure_threshold
            ):
                self._open_locked()

    def _open_locked(self) -> None:
        """Caller must hold ``self._lock``."""
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        logger.warning(
            "event=circuit_open provider=%s consecutive_failures=%d cooldown_s=%.1f",
            self.provider,
            self._consecutive_failures,
            self.cooldown_s,
        )

    def retry_after_s(self) -> float:
        """Seconds remaining until a HALF_OPEN probe is allowed (>= 0)."""
        with self._lock:
            if self._state is not CircuitState.OPEN or self._opened_at is None:
                return 0.0
            remaining = self.cooldown_s - (time.monotonic() - self._opened_at)
            return max(0.0, remaining)

    def snapshot(self) -> dict[str, str | int | float]:
        """Serializable snapshot, e.g. for exposing on a health/stats endpoint."""
        with self._lock:
            self._maybe_transition_to_half_open_locked()
            retry_after = 0.0
            if self._state is CircuitState.OPEN and self._opened_at is not None:
                retry_after = max(0.0, self.cooldown_s - (time.monotonic() - self._opened_at))
            return {
                "provider": self.provider,
                "state": self._state.value,
                "consecutive_failures": self._consecutive_failures,
                "failure_threshold": self.failure_threshold,
                "cooldown_s": self.cooldown_s,
                "retry_after_s": retry_after,
            }


_registry_lock = threading.Lock()
_registry: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(provider: str) -> CircuitBreaker:
    """Return the process-wide shared :class:`CircuitBreaker` for *provider*.

    Breakers are created lazily on first use and cached so every call site
    for a given provider observes the same state machine.
    """
    with _registry_lock:
        breaker = _registry.get(provider)
        if breaker is None:
            breaker = CircuitBreaker(provider)
            _registry[provider] = breaker
        return breaker


def reset_all_circuit_breakers() -> None:
    """Test helper: drop all cached breakers so env-var overrides re-apply."""
    with _registry_lock:
        _registry.clear()


def infer_provider_from_url(url: str) -> str:
    """Best-effort provider name from an outbound upstream URL.

    Used at the shared ``_retry_request`` call site (which is generic
    across providers) so no per-handler wiring is required. Falls back to
    ``"unknown"`` for unrecognized hosts (e.g. an operator-supplied custom
    ``upstream_base_url``), which simply means those calls share one
    breaker bucket rather than being misclassified as a known provider.
    """
    lowered = url.lower()
    if "anthropic" in lowered:
        return "anthropic"
    if "openai" in lowered or "chatgpt.com" in lowered:
        return "openai"
    if "generativelanguage" in lowered or "googleapis" in lowered or "cloudcode" in lowered:
        return "gemini"
    return "unknown"


__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "cooldown_s_from_env",
    "failure_threshold_from_env",
    "get_circuit_breaker",
    "infer_provider_from_url",
    "reset_all_circuit_breakers",
]

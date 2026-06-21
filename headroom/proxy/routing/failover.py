# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Provider failover manager with circuit-breaker semantics.

Thread-safe provider selection with:
  - Priority ordering (lower number = preferred)
  - Circuit-breaker: trip after N consecutive failures
  - Cooldown recovery: re-enable after configurable sleep period
  - ``failover_router_from_env``: factory that never raises
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("headroom.proxy.routing.failover")

# Default single-provider fallback used when the env var is absent or unparseable.
_DEFAULT_PROVIDERS: list[dict[str, Any]] = [
    {
        "name": "anthropic",
        "base_url": "https://api.anthropic.com",
        "api_key_env": "ANTHROPIC_API_KEY",
        "priority": 1,
    }
]

_PROVIDERS_ENV = "HEADROOM_PROVIDERS"


@dataclass
class ProviderEndpoint:
    """A configured upstream LLM provider endpoint."""

    name: str
    """Logical name, e.g. ``'anthropic'``, ``'openai'``, ``'bedrock'``."""

    base_url: str
    """Root URL of the upstream API, e.g. ``'https://api.anthropic.com'``."""

    api_key_env: str
    """Name of the environment variable that holds the API key."""

    priority: int = 1
    """Lower value = higher preference. Ties resolved by insertion order."""

    healthy: bool = True
    """Current circuit-breaker state; ``False`` means tripped."""

    last_failure_ts: float | None = None
    """``time.monotonic()`` timestamp of the most recent recorded failure."""

    # Internal: consecutive failure counter (not part of the public dict repr)
    _failure_count: int = field(default=0, repr=False, compare=False)

    @property
    def api_key(self) -> str | None:
        """Resolve the API key from the environment at call time."""
        return os.environ.get(self.api_key_env)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "priority": self.priority,
            "healthy": self.healthy,
            "last_failure_ts": self.last_failure_ts,
        }


class FailoverRouter:
    """Routes requests to the highest-priority healthy provider.

    Implements a *per-provider* circuit-breaker:

    * After ``failure_threshold`` consecutive failures the provider is marked
      unhealthy and skipped.
    * After ``cooldown_seconds`` of being unhealthy the provider is eligible
      again (healthy=True, failure count reset).

    All internal state mutations are protected by a :class:`threading.Lock` so
    the router is safe to share across threads/ASGI worker tasks.
    """

    def __init__(
        self,
        endpoints: list[ProviderEndpoint],
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self._endpoints = list(endpoints)
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_active(self) -> ProviderEndpoint | None:
        """Return the best available provider, or ``None`` if all are unhealthy."""
        with self._lock:
            now = time.monotonic()
            # Sort by priority (ascending) then by original list order.
            for ep in sorted(self._endpoints, key=lambda e: e.priority):
                if not ep.healthy:
                    # Check whether the cooldown has elapsed.
                    if ep.last_failure_ts is not None and (now - ep.last_failure_ts) >= self._cooldown:
                        logger.info(
                            "event=provider_cooldown_elapsed provider=%s; re-enabling",
                            ep.name,
                        )
                        ep.healthy = True
                        ep._failure_count = 0
                    else:
                        continue
                return ep
            return None

    def record_failure(self, provider_name: str) -> None:
        """Record a failure for *provider_name*. Trips the circuit on threshold."""
        with self._lock:
            ep = self._find(provider_name)
            if ep is None:
                logger.warning("event=unknown_provider_failure provider=%s", provider_name)
                return
            ep._failure_count += 1
            ep.last_failure_ts = time.monotonic()
            if ep._failure_count >= self._threshold:
                if ep.healthy:
                    logger.warning(
                        "event=circuit_tripped provider=%s failures=%d threshold=%d",
                        ep.name,
                        ep._failure_count,
                        self._threshold,
                    )
                ep.healthy = False

    def record_success(self, provider_name: str) -> None:
        """Record a success for *provider_name*. Resets the failure counter."""
        with self._lock:
            ep = self._find(provider_name)
            if ep is None:
                logger.warning("event=unknown_provider_success provider=%s", provider_name)
                return
            if ep._failure_count > 0 or not ep.healthy:
                logger.info(
                    "event=circuit_reset provider=%s previous_failures=%d",
                    ep.name,
                    ep._failure_count,
                )
            ep._failure_count = 0
            ep.healthy = True
            ep.last_failure_ts = None

    def get_status(self) -> list[dict[str, Any]]:
        """Return health status for all configured providers."""
        with self._lock:
            return [ep.to_dict() for ep in self._endpoints]

    # ------------------------------------------------------------------
    # Admin helpers (used by FastAPI routes)
    # ------------------------------------------------------------------

    def disable(self, provider_name: str) -> bool:
        """Manually mark a provider unhealthy. Returns False if not found."""
        with self._lock:
            ep = self._find(provider_name)
            if ep is None:
                return False
            ep.healthy = False
            ep.last_failure_ts = time.monotonic()
            logger.info("event=provider_manually_disabled provider=%s", provider_name)
            return True

    def enable(self, provider_name: str) -> bool:
        """Manually re-enable a provider. Returns False if not found."""
        with self._lock:
            ep = self._find(provider_name)
            if ep is None:
                return False
            ep.healthy = True
            ep._failure_count = 0
            ep.last_failure_ts = None
            logger.info("event=provider_manually_enabled provider=%s", provider_name)
            return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find(self, name: str) -> ProviderEndpoint | None:
        """Locate an endpoint by name (caller must hold the lock)."""
        for ep in self._endpoints:
            if ep.name == name:
                return ep
        return None


def failover_router_from_env(
    failure_threshold: int = 3,
    cooldown_seconds: float = 60.0,
) -> FailoverRouter:
    """Build a :class:`FailoverRouter` from environment variables.

    Reads ``HEADROOM_PROVIDERS`` as a JSON array of provider config objects::

        '[{"name": "anthropic", "base_url": "https://api.anthropic.com",
           "api_key_env": "ANTHROPIC_API_KEY", "priority": 1}]'

    If the env var is absent, empty, or contains invalid JSON/structure, the
    function falls back silently to a single-provider default config and logs a
    warning so operators can diagnose misconfiguration without crashing the proxy.
    """
    raw = os.environ.get(_PROVIDERS_ENV, "").strip()
    provider_dicts: list[dict[str, Any]] = []

    if raw:
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise TypeError(f"Expected JSON array, got {type(parsed).__name__}")
            provider_dicts = parsed
        except Exception as exc:
            logger.warning(
                "event=env_parse_error env=%s error=%r; using default providers",
                _PROVIDERS_ENV,
                str(exc),
            )

    if not provider_dicts:
        logger.info(
            "event=using_default_providers reason=%s",
            "env_var_not_set" if not raw else "parse_error_or_empty_array",
        )
        provider_dicts = _DEFAULT_PROVIDERS

    endpoints: list[ProviderEndpoint] = []
    for item in provider_dicts:
        try:
            if not isinstance(item, dict):
                raise TypeError(f"Provider config must be a dict, got {type(item).__name__}")
            ep = ProviderEndpoint(
                name=str(item["name"]),
                base_url=str(item["base_url"]),
                api_key_env=str(item["api_key_env"]),
                priority=int(item.get("priority", 1)),
                healthy=bool(item.get("healthy", True)),
            )
            endpoints.append(ep)
        except Exception as exc:
            logger.warning(
                "event=provider_config_skip item=%r error=%r",
                item,
                str(exc),
            )

    if not endpoints:
        logger.warning(
            "event=no_valid_providers; router will return None from get_active()"
        )

    return FailoverRouter(
        endpoints=endpoints,
        failure_threshold=failure_threshold,
        cooldown_seconds=cooldown_seconds,
    )

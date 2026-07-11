# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""Batch-routing eligibility gate.

Per artifacts/savings-moat-expansion-specs.md WS13:
- Flag: CUTCTX_BATCH_ROUTING=1 (default off).
- Eligibility is EXPLICIT, NEVER INFERRED. A request is
  batch-eligible only if it carries the header `x-cutctx-batch: allow`
  (SDK helper + cutctx wrap env passthrough) OR originates from
  Cutctx's own background jobs (cutctx learn, cutctx evals, WS15
  pre-compaction).
- No heuristic sniffing of "looks async" — mis-batching an
  interactive request is a catastrophic UX regression.
- Safety: this module does not itself own a durable provider batch executor
  or a result-polling endpoint.  An eligible request therefore remains a
  synchronous passthrough until one is registered.  Returning a 202 from an
  in-memory queue without an executor would silently strand user work.
- Attribution: price delta recorded as `batch_routing` source.
- Default-off (the spec's flag-off golden contract).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Per spec: 'a request is batch-eligible only if it carries the header
# x-cutctx-batch: allow'. Header names are case-insensitive per RFC 7230
# (we normalize to lower-case for matching).
BATCH_HEADER_NAME = "x-cutctx-batch"
BATCH_HEADER_VALUE_ALLOW = "allow"

# Per spec: '~50% discount on eligible traffic.'
DEFAULT_BATCH_DISCOUNT = 0.50

# Per spec: 'Anthropic Message Batches first; OpenAI second.'
DEFAULT_PROVIDER_PRIORITY = ("anthropic", "openai")

# Per spec: the allowlisted internal-job origins.
INTERNAL_BATCH_JOB_ORIGINS: frozenset[str] = frozenset(
    {"cutctx learn", "cutctx evals", "ws15 pre-compact"}
)


# ---------------------------------------------------------------------------
# Public configuration
# ---------------------------------------------------------------------------


@dataclass
class BatchRouterConfig:
    """Configuration for the batch-API router.

    The master flag `enabled` defaults to False. When False, every
    `route()` call is a strict no-op that returns a passthrough
    decision and the request body BYTE-IDENTICAL.
    """

    enabled: bool = False
    provider_priority: tuple[str, ...] = DEFAULT_PROVIDER_PRIORITY
    default_discount: float = DEFAULT_BATCH_DISCOUNT
    # Optional override: an explicit list of internal-job origins.
    # If None, INTERNAL_BATCH_JOB_ORIGINS is used.
    internal_origins: frozenset[str] | None = None


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class BatchAction(str, Enum):
    """Possible outcomes of a `route()` call."""

    PASSTHROUGH = "passthrough"  # not eligible
    ENQUEUED = "enqueued"  # batch-eligible, added to the queue


@dataclass
class BatchRouterDecision:
    """The result of a route() call.

    - `action`: passthrough or enqueued.
    - `request_body`: the input body (a copy if enqueued, the SAME
      object reference if passthrough).
    - `queue_id`: a stable handle for polling (set when enqueued).
    - `poll_url`: where the client can poll for the result.
    - `estimated_discount`: the expected price discount.
    - `metadata`: origin info, reason for the decision, etc.
    """

    action: str  # BatchAction value
    request_body: Any = None
    queue_id: str = ""
    poll_url: str = ""
    estimated_discount: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Queue state
# ---------------------------------------------------------------------------


@dataclass
class BatchQueueState:
    """Per-router queue state. Tracked for the operator surface and
    for the WS13 attribution path."""

    pending: int = 0
    completed: int = 0
    failed: int = 0
    total_enqueued: int = 0


# ---------------------------------------------------------------------------
# Eligibility gate
# ---------------------------------------------------------------------------


def is_internal_batch_job(origin: str | None) -> bool:
    """True if the request originates from a known internal batch
    job. The allowlist is per spec: 'cutctx learn, cutctx evals,
    WS15 pre-compaction'."""
    if not origin:
        return False
    return origin in INTERNAL_BATCH_JOB_ORIGINS


def is_request_batch_eligible(
    request_body: Any,
    headers: Mapping[str, str] | None,
    origin: str | None,
    config: BatchRouterConfig,
) -> tuple[bool, str]:
    """Decide whether a request is batch-eligible.

    The spec is explicit: eligibility is by header or by internal
    origin ONLY. No heuristic sniffing.

    Returns:
        (eligible, reason). reason is one of:
        - "header": the request had x-cutctx-batch: allow
        - "internal_job": the origin was in the internal allowlist
        - "not_eligible": otherwise
    """
    # Header check (case-insensitive on header NAME per RFC 7230,
    # case-sensitive on the VALUE per HTTP spec — the value "allow"
    # is the ONLY valid value).
    if headers:
        # Normalize header keys to lower-case
        norm_headers = {k.lower(): v for k, v in headers.items()}
        if norm_headers.get(BATCH_HEADER_NAME) == BATCH_HEADER_VALUE_ALLOW:
            return True, "header"
    # Internal job check
    if is_internal_batch_job(origin):
        return True, "internal_job"
    return False, "not_eligible"


# ---------------------------------------------------------------------------
# The router
# ---------------------------------------------------------------------------


class BatchRouter:
    """Routes eligible requests to a provider's batch API.

    Flag-off: every route() call returns a passthrough decision with
    the same body reference. No state is held.

    Flag-on currently records eligibility but remains fail-safe passthrough.
    Provider batch submission is deliberately not simulated: a durable
    executor and poll/result lifecycle must be installed before the router is
    allowed to return an asynchronous acceptance response.
    """

    def __init__(self, config: BatchRouterConfig | None = None) -> None:
        self.config = config or BatchRouterConfig()
        # Per-queue-id -> InternalBatchJob
        self._jobs: dict[str, InternalBatchJob] = {}
        # Counters for the operator surface
        self._state = BatchQueueState()

    def route(
        self,
        request_body: Any,
        headers: Mapping[str, str] | None = None,
        origin: str | None = None,
    ) -> BatchRouterDecision:
        """Decide whether to enqueue or pass through.

        Flag-off short-circuit happens before any eligibility check.
        """
        if not self.config.enabled:
            return BatchRouterDecision(
                action=BatchAction.PASSTHROUGH.value,
                request_body=request_body,
            )

        eligible, reason = is_request_batch_eligible(
            request_body=request_body,
            headers=headers,
            origin=origin,
            config=self.config,
        )
        if not eligible:
            return BatchRouterDecision(
                action=BatchAction.PASSTHROUGH.value,
                request_body=request_body,
            )

        # Never acknowledge an asynchronous request that no component will
        # execute.  This was previously an in-memory-only queue with no
        # worker, provider submission, polling endpoint, or restart recovery.
        # Treat explicit opt-in as advisory until that complete lifecycle is
        # available, preserving the user's request and normal response shape.
        logger.info(
            "batch routing eligible but unavailable; forwarding synchronously "
            "origin=%s reason=%s",
            origin,
            reason,
        )
        return BatchRouterDecision(
            action=BatchAction.PASSTHROUGH.value,
            request_body=request_body,
            metadata={
                "reason": "batch_executor_unavailable",
                "eligible_reason": reason,
                "origin": origin,
            },
        )

    def mark_completed(self, queue_id: str, success: bool) -> None:
        """Mark a queued job as completed (called by the async poll
        handler when the upstream batch API returns)."""
        if queue_id not in self._jobs:
            return
        if success:
            self._state.completed += 1
        else:
            self._state.failed += 1
        # Decrement pending; the job stays in the dict for audit.
        self._state.pending = max(0, self._state.pending - 1)
        del self._jobs[queue_id]

    def queue_state(self) -> BatchQueueState:
        """Return the current queue state (a copy)."""
        return BatchQueueState(
            pending=self._state.pending,
            completed=self._state.completed,
            failed=self._state.failed,
            total_enqueued=self._state.total_enqueued,
        )

    def internal_queue_jobs(self) -> list[InternalBatchJob]:
        """Return a list of all currently-pending jobs (for the
        operator surface and for tests)."""
        return list(self._jobs.values())


@dataclass
class InternalBatchJob:
    """An enqueued internal batch job. Held in the router's queue
    until mark_completed() is called.

    - `queue_id`: stable handle for polling
    - `request_body`: the original request body (a copy, since
      enqueuing is a mutation)
    - `origin`: where the job came from (for audit)
    - `eligible_reason`: why this job was eligible ('header' or
      'internal_job')
    """

    queue_id: str
    request_body: Any
    origin: str | None
    eligible_reason: str = ""


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


__all__ = [
    "BATCH_HEADER_NAME",
    "BATCH_HEADER_VALUE_ALLOW",
    "DEFAULT_BATCH_DISCOUNT",
    "DEFAULT_PROVIDER_PRIORITY",
    "INTERNAL_BATCH_JOB_ORIGINS",
    "BatchRouter",
    "BatchRouterConfig",
    "BatchRouterDecision",
    "BatchAction",
    "BatchQueueState",
    "InternalBatchJob",
    "is_request_batch_eligible",
    "is_internal_batch_job",
]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""TDD tests for the WS13 batch-API arbitrage.

Per artifacts/savings-moat-expansion-specs.md WS13:
- Flag: CUTCTX_BATCH_ROUTING=1 (default off).
- Eligibility is EXPLICIT, NEVER INFERRED. A request is batch-eligible
  only if it carries the header `x-cutctx-batch: allow` (SDK helper
  + cutctx wrap env passthrough) OR originates from Cutctx's own
  background jobs (cutctx learn, cutctx evals, WS15 pre-compaction).
  No heuristic sniffing of "looks async" — mis-batching an
  interactive request is a catastrophic UX regression.
- Mechanics: eligible requests are enqueued to the provider's batch
  API (Anthropic Message Batches first; OpenAI second); the proxy
  returns a 202-style poll handle or holds the connection per client
  preference header. Queue state in the existing stats DB.
- Attribution: price delta recorded as `batch_routing` source.
- Default-off (the spec's flag-off golden contract).

TDD: written first, then cutctx/proxy/batch_router.py is made
to satisfy them.
"""

from __future__ import annotations

import pytest

from cutctx.proxy.batch_router import (
    BATCH_HEADER_NAME,
    BATCH_HEADER_VALUE_ALLOW,
    DEFAULT_BATCH_DISCOUNT,
    BatchRouter,
    BatchRouterConfig,
    is_internal_batch_job,
    is_request_batch_eligible,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_batch_header_name_is_x_cutctx_batch_allow() -> None:
    """The header name is 'x-cutctx-batch' and the value is 'allow'."""
    assert BATCH_HEADER_NAME == "x-cutctx-batch"
    assert BATCH_HEADER_VALUE_ALLOW == "allow"


def test_default_batch_discount_is_50_percent() -> None:
    """Per spec: 'Anthropic Message Batches first; OpenAI second;
    ~50% discount on eligible traffic.'"""
    assert DEFAULT_BATCH_DISCOUNT == 0.50


# ---------------------------------------------------------------------------
# Flag-off golden contract
# ---------------------------------------------------------------------------


def test_default_config_is_all_off() -> None:
    """The default BatchRouterConfig must be all-off."""
    cfg = BatchRouterConfig()
    assert cfg.enabled is False


def test_flag_off_always_returns_passthrough() -> None:
    """With flag off, every request is a passthrough (no eligibility
    check, no routing, no state growth)."""
    router = BatchRouter(BatchRouterConfig())
    decision = router.route(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={"x-cutctx-batch": "allow"},  # even with the header!
    )
    assert decision.action == "passthrough"


def test_flag_off_does_not_grow_state() -> None:
    """With flag off, hammer the router with many calls; nothing
    should accumulate in the internal batch queue state."""
    cfg = BatchRouterConfig()
    router = BatchRouter(cfg)
    for i in range(50):
        decision = router.route(
            request_body={"model": "claude-3-opus", "messages": []},
            headers={"x-cutctx-batch": "allow"},
            origin="cutctx learn",  # internal job
        )
        assert decision.action == "passthrough"
    # No state accumulated
    assert len(router.internal_queue_jobs()) == 0


# ---------------------------------------------------------------------------
# Eligibility gate — the spec's most important rule
# ---------------------------------------------------------------------------


def test_no_header_no_internal_origin_not_eligible() -> None:
    """No header, no internal job -> NOT batch-eligible."""
    eligible, reason = is_request_batch_eligible(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={},
        origin=None,
        config=BatchRouterConfig(enabled=True),
    )
    assert eligible is False
    assert reason == "not_eligible"


def test_header_allow_makes_request_eligible() -> None:
    """Header x-cutctx-batch: allow -> eligible. This is the ONLY
    client-driven eligibility path. Per spec: 'mis-batching an
    interactive request is a catastrophic UX regression.'"""
    eligible, reason = is_request_batch_eligible(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={BATCH_HEADER_NAME: BATCH_HEADER_VALUE_ALLOW},
        origin=None,
        config=BatchRouterConfig(enabled=True),
    )
    assert eligible is True
    assert reason == "header"


def test_header_value_other_than_allow_not_eligible() -> None:
    """A non-'allow' value (e.g. 'yes', 'true', '1') does NOT make
    the request eligible. The spec is explicit: only 'allow' works."""
    for value in ("yes", "true", "1", "ALLOW", "on"):
        eligible, _ = is_request_batch_eligible(
            request_body={"model": "claude-3-opus", "messages": []},
            headers={BATCH_HEADER_NAME: value},
            origin=None,
            config=BatchRouterConfig(enabled=True),
        )
        assert eligible is False, f"header value {value!r} should not enable batch routing"


def test_header_case_insensitive() -> None:
    """HTTP headers are case-insensitive on the NAME per RFC 7230.
    'X-Cutctx-Batch: allow' also enables (different case on name,
    canonical value on value)."""
    eligible, _ = is_request_batch_eligible(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={"X-Cutctx-Batch": "allow"},
        origin=None,
        config=BatchRouterConfig(enabled=True),
    )
    assert eligible is True


def test_header_value_case_sensitive() -> None:
    """The header VALUE is case-sensitive per HTTP spec. 'ALLOW'
    (uppercase value) does NOT match 'allow' (lowercase value)."""
    eligible, _ = is_request_batch_eligible(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={"x-cutctx-batch": "ALLOW"},
        origin=None,
        config=BatchRouterConfig(enabled=True),
    )
    assert eligible is False


def test_internal_origin_cutctx_learn_makes_request_eligible() -> None:
    """Per spec: 'originates from Cutctx's own background jobs
    (cutctx learn, cutctx evals, WS15 pre-compaction).'"""
    for origin in ("cutctx learn", "cutctx evals", "ws15 pre-compact"):
        eligible, reason = is_request_batch_eligible(
            request_body={"model": "claude-3-opus", "messages": []},
            headers={},
            origin=origin,
            config=BatchRouterConfig(enabled=True),
        )
        assert eligible is True, f"internal job {origin!r} should be eligible"
        assert reason == "internal_job"


def test_arbitrary_internal_origin_not_eligible() -> None:
    """Only the allowlisted internal jobs are eligible, not any
    string that happens to look like an internal job."""
    eligible, _ = is_request_batch_eligible(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={},
        origin="some_arbitrary_cli_subcommand",
        config=BatchRouterConfig(enabled=True),
    )
    assert eligible is False


# ---------------------------------------------------------------------------
# Routing decision
# ---------------------------------------------------------------------------


def test_routing_decision_includes_queue_id_and_poll_url() -> None:
    """When eligible, the decision includes a queue_id (a stable
    handle for polling) and a poll_url (where the client can poll
    for the result)."""
    cfg = BatchRouterConfig(enabled=True)
    router = BatchRouter(cfg)
    decision = router.route(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={BATCH_HEADER_NAME: BATCH_HEADER_VALUE_ALLOW},
    )
    assert decision.action == "enqueued"
    assert decision.queue_id  # not empty
    assert decision.poll_url  # not empty
    assert decision.estimated_discount == DEFAULT_BATCH_DISCOUNT


def test_routing_decision_records_internal_job_metadata() -> None:
    """When routed because of an internal job, the decision records
    the origin in metadata so the operator can audit it."""
    cfg = BatchRouterConfig(enabled=True)
    router = BatchRouter(cfg)
    decision = router.route(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={},
        origin="cutctx learn",
    )
    assert decision.action == "enqueued"
    assert decision.metadata.get("origin") == "cutctx learn"
    assert decision.metadata.get("reason") == "internal_job"


# ---------------------------------------------------------------------------
# Flag-on: eligibility gate is the only thing that matters
# ---------------------------------------------------------------------------


def test_flag_on_without_header_and_no_internal_origin_is_passthrough() -> None:
    """With flag on, a request without the header and no internal
    origin is a passthrough (the spec: 'mis-batching an interactive
    request is a catastrophic UX regression' — we don't infer)."""
    cfg = BatchRouterConfig(enabled=True)
    router = BatchRouter(cfg)
    decision = router.route(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={},
        origin=None,
    )
    assert decision.action == "passthrough"


def test_flag_on_with_header_enqueues() -> None:
    """With flag on + the allow header, the request is enqueued."""
    cfg = BatchRouterConfig(enabled=True)
    router = BatchRouter(cfg)
    decision = router.route(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={BATCH_HEADER_NAME: BATCH_HEADER_VALUE_ALLOW},
    )
    assert decision.action == "enqueued"


# ---------------------------------------------------------------------------
# Internal queue state
# ---------------------------------------------------------------------------


def test_internal_queue_state_tracks_enqueued_jobs() -> None:
    """The router maintains an internal queue of enqueued jobs (so
    the operator can see the queue size, throughput, etc.)."""
    cfg = BatchRouterConfig(enabled=True)
    router = BatchRouter(cfg)
    for _ in range(3):
        router.route(
            request_body={"model": "claude-3-opus", "messages": []},
            headers={BATCH_HEADER_NAME: BATCH_HEADER_VALUE_ALLOW},
        )
    state = router.queue_state()
    assert state.pending == 3
    assert state.total_enqueued == 3


def test_internal_queue_state_completed_count_increments() -> None:
    """When a job is marked completed (the async poll returns), the
    pending count decreases and the completed count increases."""
    cfg = BatchRouterConfig(enabled=True)
    router = BatchRouter(cfg)
    decisions = [
        router.route(
            request_body={"model": "claude-3-opus", "messages": []},
            headers={BATCH_HEADER_NAME: BATCH_HEADER_VALUE_ALLOW},
        )
        for _ in range(3)
    ]
    # Mark the first one completed
    router.mark_completed(decisions[0].queue_id, success=True)
    state = router.queue_state()
    assert state.pending == 2
    assert state.completed == 1


# ---------------------------------------------------------------------------
# Background jobs that are inherently batch-eligible
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "origin",
    [
        "cutctx learn",
        "cutctx evals",
        "ws15 pre-compact",
    ],
)
def test_internal_job_origins_are_batch_eligible(origin: str) -> None:
    assert is_internal_batch_job(origin) is True


@pytest.mark.parametrize(
    "origin",
    [
        "user",
        "cutctx serve",
        "cutctx evals --interactive",  # not exactly the bg job
        "random other thing",
    ],
)
def test_non_internal_origins_are_not_batch_eligible(origin: str) -> None:
    assert is_internal_batch_job(origin) is False


# ---------------------------------------------------------------------------
# BDD: end-to-end
# ---------------------------------------------------------------------------


def test_bdd_scenario_user_opt_in_to_batch() -> None:
    """BDD: the spec's user-opt-in flow. A user explicitly opts in
    to batch processing by setting the x-cutctx-batch header (e.g.
    via `cutctx wrap --batch-ok`). The request is enqueued, the
    response is a 202-style poll handle, the user polls the queue.
    """
    cfg = BatchRouterConfig(enabled=True)
    router = BatchRouter(cfg)
    decision = router.route(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={BATCH_HEADER_NAME: BATCH_HEADER_VALUE_ALLOW},
    )
    assert decision.action == "enqueued"
    assert decision.estimated_discount == pytest.approx(0.5)
    # The operator can see the queue
    state = router.queue_state()
    assert state.pending == 1


def test_bdd_scenario_internal_background_job() -> None:
    """BDD: the spec's internal-job flow. cutctx learn emits a
    request; it is automatically batch-eligible (no header needed)."""
    cfg = BatchRouterConfig(enabled=True)
    router = BatchRouter(cfg)
    decision = router.route(
        request_body={"model": "claude-3-opus", "messages": []},
        headers={},  # no header
        origin="cutctx learn",
    )
    assert decision.action == "enqueued"
    assert decision.metadata.get("reason") == "internal_job"


def test_bdd_scenario_interactive_request_not_batched() -> None:
    """BDD: the spec's safety case. A normal interactive request
    (no header, no internal origin) is NEVER batched, even with
    flag on. Mis-batching an interactive request would be a
    catastrophic UX regression.
    """
    cfg = BatchRouterConfig(enabled=True)
    router = BatchRouter(cfg)
    # Hammer with 100 different interactive requests
    for i in range(100):
        decision = router.route(
            request_body={
                "model": "claude-3-opus",
                "messages": [{"role": "user", "content": f"interactive-{i}"}],
            },
            headers={},
            origin=None,
        )
        assert decision.action == "passthrough", (
            f"interactive request {i} was batched — this is the catastrophic UX regression"
        )


# ---------------------------------------------------------------------------
# Regression guard: flag-off path is byte-identical
# ---------------------------------------------------------------------------


def test_flag_off_request_body_unchanged() -> None:
    """With flag off, the request body is returned BYTE-IDENTICAL
    (same object reference). The spec's golden contract."""
    cfg = BatchRouterConfig()  # default: all off
    router = BatchRouter(cfg)
    body = {"model": "claude-3-opus", "messages": [{"role": "user", "content": "test"}]}
    decision = router.route(request_body=body, headers={})
    assert decision.request_body is body

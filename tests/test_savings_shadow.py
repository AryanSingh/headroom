# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Task 1 (commercial-readiness runbook): Savings Validation Protocol / shadow mode.

Cutctx's savings numbers are estimates (token-count delta x list price).
Shadow mode empirically validates a sampled fraction of requests by
replaying them upstream with compression disabled and comparing the
actual provider-billed cost of the compressed vs. uncompressed call.

Covers:
- ``should_run_shadow_check``: deterministic sampling decision, injectable
  rng, no real randomness needed in tests.
- ``shadow_mode_enabled_from_env`` / ``shadow_sample_rate_from_env``: env
  var parsing, same pattern as ``circuit_breaker.py``.
- ``SavingsTracker.record_measured_savings``: persists a
  ``savings_basis="measured"`` entry alongside (not replacing) the normal
  ``"estimated"`` history rows; negative measured savings logs a WARNING;
  shadow checks never pollute the lifetime/session aggregates.
- ``AnthropicHandlerMixin._maybe_shadow_check``: the hook point in
  ``handlers/anthropic.py``. Disabled by default (provably zero extra
  upstream calls); when enabled + sampled, reuses the existing
  ``_retry_request`` byte-faithful-forwarding path to replay the original
  (pre-compression) bytes and records the comparison; any failure is
  swallowed and never affects the primary response.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from functools import partial
from typing import Any

import anyio
import pytest

from cutctx.proxy.handlers.anthropic import AnthropicHandlerMixin
from cutctx.proxy.savings_pricing import value_tokens_usd
from cutctx.proxy.savings_tracker import (
    SavingsTracker,
    estimate_request_cost_usd,
    shadow_mode_enabled_from_env,
    shadow_sample_rate_from_env,
    should_run_shadow_check,
)

MODEL = "claude-opus-4-1-20250805"


class _ListHandler(logging.Handler):
    """Direct handler that survives the proxy disabling propagation.

    ``caplog`` attaches to root; ``cutctx.proxy.helpers._setup_file_logging``
    flips ``logging.getLogger("cutctx").propagate = False`` once a proxy
    instance is constructed anywhere in the test run, after which
    root-attached handlers stop receiving cutctx-namespaced records
    (order-dependent across the full suite). Attaching directly to the
    target logger sidesteps that. Mirrors the pattern in
    ``test_backend_streaming_cache_metrics.py``.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextmanager
def _capture_logger(name: str):
    handler = _ListHandler()
    target = logging.getLogger(name)
    target.addHandler(handler)
    prior_level = target.level
    target.setLevel(logging.WARNING)
    try:
        yield handler
    finally:
        target.removeHandler(handler)
        target.setLevel(prior_level)


# --------------------------------------------------------------------------- #
# should_run_shadow_check                                                     #
# --------------------------------------------------------------------------- #


def test_should_run_shadow_check_zero_rate_never_fires() -> None:
    """A sample rate of 0 always returns False, regardless of the draw."""
    assert should_run_shadow_check(0.0, rng=lambda: 0.0) is False
    assert should_run_shadow_check(0.0) is False


def test_should_run_shadow_check_full_rate_always_fires() -> None:
    """A sample rate of 1.0 (or above) always returns True."""
    assert should_run_shadow_check(1.0, rng=lambda: 0.999999) is True
    assert should_run_shadow_check(2.0) is True


def test_should_run_shadow_check_partial_rate_is_deterministic_with_injected_rng() -> None:
    """Mid-range rates compare the injected draw against the rate.

    No monkeypatching of the ``random`` module is needed: passing a
    deterministic zero-arg callable makes the decision fully predictable.
    """
    assert should_run_shadow_check(0.5, rng=lambda: 0.3) is True
    assert should_run_shadow_check(0.5, rng=lambda: 0.7) is False
    # Boundary: draw == rate is NOT a hit (strict less-than).
    assert should_run_shadow_check(0.5, rng=lambda: 0.5) is False


def test_should_run_shadow_check_negative_rate_never_fires() -> None:
    assert should_run_shadow_check(-1.0, rng=lambda: 0.0) is False


# --------------------------------------------------------------------------- #
# env var helpers                                                             #
# --------------------------------------------------------------------------- #


def test_shadow_mode_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CUTCTX_SHADOW_MODE", raising=False)
    assert shadow_mode_enabled_from_env() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_shadow_mode_enabled_via_env(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", value)
    assert shadow_mode_enabled_from_env() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
def test_shadow_mode_disabled_via_env(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", value)
    assert shadow_mode_enabled_from_env() is False


def test_shadow_sample_rate_defaults_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CUTCTX_SHADOW_SAMPLE_RATE", raising=False)
    assert shadow_sample_rate_from_env() == 0.0


def test_shadow_sample_rate_parses_and_clamps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "0.25")
    assert shadow_sample_rate_from_env() == 0.25

    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "5.0")
    assert shadow_sample_rate_from_env() == 1.0

    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "-3.0")
    assert shadow_sample_rate_from_env() == 0.0


def test_shadow_sample_rate_bad_value_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "not-a-number")
    assert shadow_sample_rate_from_env() == 0.0


# --------------------------------------------------------------------------- #
# SavingsTracker.record_measured_savings                                      #
# --------------------------------------------------------------------------- #


def test_record_measured_savings_persists_measured_entry(tmp_path) -> None:
    tracker = SavingsTracker(str(tmp_path / "savings.json"))
    ok = tracker.record_measured_savings(
        model=MODEL,
        provider="anthropic",
        estimated_savings_usd=0.02,
        measured_savings_usd=0.015,
        request_id="req-shadow-1",
    )
    assert ok is True

    snapshot = tracker.snapshot()
    assert len(snapshot["shadow_checks"]) == 1
    entry = snapshot["shadow_checks"][0]
    assert entry["savings_basis"] == "measured"
    assert entry["estimated_savings_usd"] == 0.02
    assert entry["measured_savings_usd"] == 0.015
    assert entry["measured_delta_usd"] == pytest.approx(-0.005)
    assert entry["request_id"] == "req-shadow-1"
    assert entry["model"] == MODEL
    assert entry["provider"] == "anthropic"


def test_record_measured_savings_appears_in_stats_preview(tmp_path) -> None:
    tracker = SavingsTracker(str(tmp_path / "savings.json"))
    tracker.record_measured_savings(
        model=MODEL,
        estimated_savings_usd=0.01,
        measured_savings_usd=0.01,
    )
    preview = tracker.stats_preview()
    assert len(preview["shadow_checks"]) == 1
    assert preview["shadow_checks"][0]["savings_basis"] == "measured"


def test_record_measured_savings_negative_delta_logs_warning(tmp_path) -> None:
    """Runbook's negative-savings guard: compression costing MORE than the
    uncompressed baseline must surface as a WARNING, not be silently
    reported as a positive number.
    """
    tracker = SavingsTracker(str(tmp_path / "savings.json"))
    with _capture_logger("cutctx.proxy.savings_tracker") as log_handle:
        tracker.record_measured_savings(
            model=MODEL,
            estimated_savings_usd=0.02,
            measured_savings_usd=-0.01,
            request_id="req-negative",
        )
    assert any("shadow_negative_savings" in record.getMessage() for record in log_handle.records)
    snapshot = tracker.snapshot()
    assert snapshot["shadow_checks"][0]["measured_savings_usd"] == -0.01


def test_record_measured_savings_does_not_affect_lifetime_or_session(tmp_path) -> None:
    """A shadow check duplicates a sampled request's upstream cost — it
    must never be double-counted as if it were a second real request.
    """
    tracker = SavingsTracker(str(tmp_path / "savings.json"))
    tracker.record_request(model=MODEL, input_tokens=1000, tokens_saved=500)
    before = tracker.snapshot()["lifetime"]["requests"]

    tracker.record_measured_savings(
        model=MODEL,
        estimated_savings_usd=0.01,
        measured_savings_usd=0.01,
    )

    after = tracker.snapshot()["lifetime"]["requests"]
    assert after == before


def test_normal_request_history_rows_are_tagged_estimated(tmp_path) -> None:
    """Every ordinary per-request savings row is an estimate; only
    ``record_measured_savings`` rows carry ``savings_basis="measured"``.
    """
    tracker = SavingsTracker(str(tmp_path / "savings.json"))
    tracker.record_request(model=MODEL, input_tokens=1000, tokens_saved=500)
    history = tracker.snapshot()["history"]
    assert history
    assert all(row["savings_basis"] == "estimated" for row in history)


def test_shadow_checks_survive_reload(tmp_path) -> None:
    """Shadow checks round-trip through disk like the rest of the state."""
    path = str(tmp_path / "savings.json")
    tracker = SavingsTracker(path)
    tracker.record_measured_savings(
        model=MODEL,
        estimated_savings_usd=0.01,
        measured_savings_usd=0.008,
        request_id="req-reload",
    )

    reloaded = SavingsTracker(path)
    snapshot = reloaded.snapshot()
    assert len(snapshot["shadow_checks"]) == 1
    assert snapshot["shadow_checks"][0]["request_id"] == "req-reload"


# --------------------------------------------------------------------------- #
# AnthropicHandlerMixin._maybe_shadow_check                                   #
# --------------------------------------------------------------------------- #


class _RespStub:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _DummyMetrics:
    def __init__(self, savings_tracker: SavingsTracker) -> None:
        self.savings_tracker = savings_tracker


class _ShadowCheckHandler(AnthropicHandlerMixin):
    """Minimal handler exposing just what ``_maybe_shadow_check`` needs."""

    def __init__(self, savings_tracker: SavingsTracker, retry_impl) -> None:
        self.metrics = _DummyMetrics(savings_tracker)
        self._retry_impl = retry_impl
        self.calls: list[dict[str, Any]] = []

    async def _retry_request(self, method, url, headers, body, **kwargs):
        self.calls.append({"method": method, "url": url, "body": body, **kwargs})
        return await self._retry_impl(method, url, headers, body, **kwargs)


def _make_handler(tmp_path, retry_impl) -> tuple[_ShadowCheckHandler, SavingsTracker]:
    tracker = SavingsTracker(str(tmp_path / "savings.json"))
    handler = _ShadowCheckHandler(tracker, retry_impl)
    return handler, tracker


def _base_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs = dict(
        request_id="req-1",
        model=MODEL,
        provider_name="anthropic",
        url="https://api.anthropic.com/v1/messages",
        headers={"x-api-key": "sk-ant-test"},
        original_body_bytes=b'{"model":"claude-3-5-sonnet-latest","messages":[]}',
        body_mutated=True,
        tokens_saved=500,
        compressed_cache_read_tokens=0,
        compressed_cache_write_tokens=0,
        compressed_uncached_input_tokens=1000,
    )
    kwargs.update(overrides)
    return kwargs


async def _never_called(*args: Any, **kwargs: Any):
    raise AssertionError("shadow call should not have been made")


def test_shadow_check_default_off_makes_no_upstream_call(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CUTCTX_SHADOW_MODE unset (the default): zero extra upstream calls,
    zero behavioral change, regardless of how much was saved.
    """
    monkeypatch.delenv("CUTCTX_SHADOW_MODE", raising=False)
    monkeypatch.delenv("CUTCTX_SHADOW_SAMPLE_RATE", raising=False)
    handler, tracker = _make_handler(tmp_path, _never_called)

    anyio.run(partial(handler._maybe_shadow_check, **_base_kwargs()))

    assert handler.calls == []
    assert tracker.snapshot()["shadow_checks"] == []


def test_shadow_check_explicitly_disabled_makes_no_call(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", "false")
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "1.0")
    handler, tracker = _make_handler(tmp_path, _never_called)

    anyio.run(partial(handler._maybe_shadow_check, **_base_kwargs()))

    assert handler.calls == []


def test_shadow_check_skips_when_nothing_was_compressed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even fully enabled + sampled, a request with tokens_saved == 0 has
    nothing to validate, so no duplicate call is made.
    """
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "1.0")
    handler, tracker = _make_handler(tmp_path, _never_called)

    anyio.run(partial(handler._maybe_shadow_check, **_base_kwargs(tokens_saved=0)))

    assert handler.calls == []


def test_shadow_check_skips_when_body_not_mutated(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "1.0")
    handler, tracker = _make_handler(tmp_path, _never_called)

    anyio.run(partial(handler._maybe_shadow_check, **_base_kwargs(body_mutated=False)))

    assert handler.calls == []


def test_shadow_check_skips_when_no_original_bytes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "1.0")
    handler, tracker = _make_handler(tmp_path, _never_called)

    anyio.run(partial(handler._maybe_shadow_check, **_base_kwargs(original_body_bytes=None)))

    assert handler.calls == []


def test_shadow_check_zero_sample_rate_skips_even_when_enabled(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "0.0")
    handler, tracker = _make_handler(tmp_path, _never_called)

    anyio.run(partial(handler._maybe_shadow_check, **_base_kwargs()))

    assert handler.calls == []


def test_shadow_check_sampled_fires_replays_original_bytes_and_records_measurement(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The core positive path: enabled + sampled + something was
    compressed -> exactly one extra upstream call, sent byte-faithfully
    from ``original_body_bytes`` (``body_mutated=False``), and the
    measured-vs-estimated comparison is recorded.
    """
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "1.0")

    async def retry_impl(method, url, headers, body, **kwargs):
        return _RespStub(
            200,
            {
                "usage": {
                    "input_tokens": 1500,  # uncompressed: 500 more than compressed
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            },
        )

    handler, tracker = _make_handler(tmp_path, retry_impl)

    anyio.run(
        partial(
            handler._maybe_shadow_check,
            **_base_kwargs(compressed_uncached_input_tokens=1000, tokens_saved=500),
        )
    )

    assert len(handler.calls) == 1
    call = handler.calls[0]
    assert call["body_mutated"] is False
    assert call["original_body_bytes"] == b'{"model":"claude-3-5-sonnet-latest","messages":[]}'
    assert call["forwarder_name"] == "anthropic_messages_shadow"

    shadow_checks = tracker.snapshot()["shadow_checks"]
    assert len(shadow_checks) == 1
    entry = shadow_checks[0]
    assert entry["savings_basis"] == "measured"
    assert entry["request_id"] == "req-1"
    assert entry["model"] == MODEL
    assert entry["provider"] == "anthropic"

    expected_compressed_cost = estimate_request_cost_usd(
        MODEL, input_tokens=1000, uncached_input_tokens=1000
    )
    expected_shadow_cost = estimate_request_cost_usd(
        MODEL, input_tokens=1500, uncached_input_tokens=1500
    )
    assert entry["measured_savings_usd"] == pytest.approx(
        expected_shadow_cost - expected_compressed_cost
    )
    assert entry["estimated_savings_usd"] == pytest.approx(value_tokens_usd(MODEL, 500))


def test_shadow_check_negative_measurement_flows_through_and_warns(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the 'uncompressed' shadow call is somehow cheaper than the
    compressed call (e.g. compression busted a cache hit), the negative
    delta must be recorded, not clamped away, and must log a warning.
    """
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "1.0")

    async def retry_impl(method, url, headers, body, **kwargs):
        return _RespStub(
            200,
            {"usage": {"input_tokens": 100, "cache_read_input_tokens": 0}},
        )

    handler, tracker = _make_handler(tmp_path, retry_impl)

    with _capture_logger("cutctx.proxy.savings_tracker") as log_handle:
        anyio.run(
            partial(
                handler._maybe_shadow_check,
                **_base_kwargs(compressed_uncached_input_tokens=5000, tokens_saved=500),
            )
        )

    shadow_checks = tracker.snapshot()["shadow_checks"]
    assert len(shadow_checks) == 1
    assert shadow_checks[0]["measured_savings_usd"] < 0
    assert any("shadow_negative_savings" in r.getMessage() for r in log_handle.records)


def test_shadow_check_upstream_error_status_is_not_recorded_as_measurement(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "1.0")

    async def retry_impl(method, url, headers, body, **kwargs):
        return _RespStub(500, {"error": {"message": "boom"}})

    handler, tracker = _make_handler(tmp_path, retry_impl)

    with _capture_logger("cutctx.proxy") as log_handle:
        anyio.run(partial(handler._maybe_shadow_check, **_base_kwargs()))

    assert len(handler.calls) == 1  # the shadow call was attempted
    assert tracker.snapshot()["shadow_checks"] == []  # but nothing was recorded
    assert any("shadow_check_upstream_error" in r.getMessage() for r in log_handle.records)


def test_shadow_check_failure_is_swallowed_and_never_raises(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A network error (or any exception) during the shadow call must
    never propagate — it would otherwise poison the primary response.
    """
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "1.0")

    async def retry_impl(method, url, headers, body, **kwargs):
        raise ConnectionError("upstream unreachable")

    handler, tracker = _make_handler(tmp_path, retry_impl)

    with _capture_logger("cutctx.proxy") as log_handle:
        # Must not raise.
        anyio.run(partial(handler._maybe_shadow_check, **_base_kwargs()))

    assert tracker.snapshot()["shadow_checks"] == []
    assert any("shadow_check_failed" in r.getMessage() for r in log_handle.records)


def test_shadow_check_malformed_json_response_is_swallowed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "1.0")

    class _BadJsonResp:
        status_code = 200

        def json(self):
            raise ValueError("not json")

    async def retry_impl(method, url, headers, body, **kwargs):
        return _BadJsonResp()

    handler, tracker = _make_handler(tmp_path, retry_impl)

    # Must not raise.
    anyio.run(partial(handler._maybe_shadow_check, **_base_kwargs()))

    assert tracker.snapshot()["shadow_checks"] == []


def test_shadow_check_missing_savings_tracker_is_a_noop(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If ``self.metrics`` has no ``savings_tracker`` attribute, the
    comparison is simply not recorded rather than raising.
    """
    monkeypatch.setenv("CUTCTX_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_SHADOW_SAMPLE_RATE", "1.0")

    async def retry_impl(method, url, headers, body, **kwargs):
        return _RespStub(200, {"usage": {"input_tokens": 1500}})

    class _Handler(AnthropicHandlerMixin):
        def __init__(self) -> None:
            self.metrics = object()  # no savings_tracker attribute

        async def _retry_request(self, method, url, headers, body, **kwargs):
            return await retry_impl(method, url, headers, body, **kwargs)

    handler = _Handler()
    # Must not raise.
    anyio.run(partial(handler._maybe_shadow_check, **_base_kwargs()))

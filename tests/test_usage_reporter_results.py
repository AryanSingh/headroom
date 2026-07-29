"""Contract tests for hosted usage-reporting results.

Product decision (verified-production-remediation Task 2): there is no
deployed hosted usage-ingestion endpoint today. `UsageReporter` must stop
POSTing to the obsolete `/v1/license/usage` path (which only ever answered
HTTP 405) and report `"unavailable"` instead, without ever representing that
405 as a successful delivery.

The `_classify_usage_response` / `_classify_usage_exception` helpers document
the contract a *future* authenticated endpoint would need to satisfy. They
are exercised directly here (against constructed responses/exceptions, not
any invented URL) so the mapping is pinned down before such an endpoint ever
exists.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest

from cutctx.telemetry.reporter import (
    UsageReporter,
    UsageReportResult,
    _classify_usage_exception,
    _classify_usage_response,
)


class _FakeCostTracker:
    def __init__(self, requests_by_model: dict[str, int]):
        self._requests_by_model = dict(requests_by_model)
        self._tokens_saved_by_model: dict[str, int] = {}
        self._tokens_sent_by_model: dict[str, int] = {}


class _FakeProxy:
    def __init__(self, cost_tracker: _FakeCostTracker):
        self.cost_tracker = cost_tracker


def _reject_any_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(
        f"usage reporter must not call the obsolete usage endpoint, got {request.url}"
    )


# ---------------------------------------------------------------------------
# Response/exception classification contract
# ---------------------------------------------------------------------------


def test_classify_successful_acknowledgement_as_delivered() -> None:
    response = httpx.Response(200, json={"status": "accepted"})
    assert _classify_usage_response(response) == "delivered"


@pytest.mark.parametrize("status_code", [401, 403])
def test_classify_auth_failures_as_unavailable(status_code: int) -> None:
    response = httpx.Response(status_code, json={"error": "unauthorized"})
    assert _classify_usage_response(response) == "unavailable"


def test_classify_unsupported_method_as_unavailable_not_delivered() -> None:
    """405 must never be read as success -- this was the historical bug."""
    response = httpx.Response(405, text="Method Not Allowed")
    assert _classify_usage_response(response) == "unavailable"


def test_classify_malformed_success_body_as_unavailable() -> None:
    response = httpx.Response(200, content=b"not json")
    assert _classify_usage_response(response) == "unavailable"


def test_classify_unexpected_success_shape_as_unavailable() -> None:
    response = httpx.Response(200, json={"unexpected": "shape"})
    assert _classify_usage_response(response) == "unavailable"


def test_classify_server_error_as_retryable_failure() -> None:
    response = httpx.Response(500, json={"error": "internal"})
    assert _classify_usage_response(response) == "retryable_failure"


def test_classify_timeout_exception_as_retryable_failure() -> None:
    assert _classify_usage_exception(httpx.TimeoutException("timed out")) == "retryable_failure"


def test_classify_connection_error_as_retryable_failure() -> None:
    assert (
        _classify_usage_exception(httpx.ConnectError("connection refused")) == "retryable_failure"
    )


def test_classify_unexpected_exception_as_unavailable() -> None:
    assert _classify_usage_exception(ValueError("boom")) == "unavailable"


# ---------------------------------------------------------------------------
# Runtime behavior under the current "unavailable" product decision
# ---------------------------------------------------------------------------


def test_report_usage_never_posts_to_the_obsolete_endpoint(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> UsageReportResult:
        reporter = UsageReporter(license_key="lic_test", cloud_url="https://licenses.example")
        reporter._proxy = _FakeProxy(_FakeCostTracker({"gpt-4": 3}))  # type: ignore[assignment]
        reporter._http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(_reject_any_request)
        )
        try:
            with caplog.at_level(logging.WARNING, logger="cutctx.telemetry.reporter"):
                return await reporter._report_usage()
        finally:
            await reporter._http_client.aclose()

    result = asyncio.run(scenario())

    assert result == "unavailable"
    assert any("unavailable" in message.lower() for message in caplog.messages)


def test_report_usage_skips_empty_periods_without_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> UsageReportResult:
        reporter = UsageReporter(license_key="lic_test", cloud_url="https://licenses.example")
        reporter._proxy = _FakeProxy(_FakeCostTracker({}))  # type: ignore[assignment]
        with caplog.at_level(logging.WARNING, logger="cutctx.telemetry.reporter"):
            return await reporter._report_usage()

    result = asyncio.run(scenario())

    assert result == "unavailable"
    assert caplog.messages == []


def test_report_usage_return_value_can_be_safely_ignored() -> None:
    """`_report_loop` awaits `_report_usage()` without using the result."""

    async def scenario() -> None:
        reporter = UsageReporter(license_key="lic_test", cloud_url="https://licenses.example")
        reporter._proxy = _FakeProxy(_FakeCostTracker({"gpt-4": 1}))  # type: ignore[assignment]
        reporter._http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(_reject_any_request)
        )
        try:
            await reporter._report_usage()  # no assertion on the return value
        finally:
            await reporter._http_client.aclose()

    asyncio.run(scenario())


def test_report_usage_warning_is_rate_limited_across_periods(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        reporter = UsageReporter(license_key="lic_test", cloud_url="https://licenses.example")
        tracker = _FakeCostTracker({"gpt-4": 1})
        reporter._proxy = _FakeProxy(tracker)  # type: ignore[assignment]
        reporter._http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(_reject_any_request)
        )
        try:
            with caplog.at_level(logging.WARNING, logger="cutctx.telemetry.reporter"):
                await reporter._report_usage()
                tracker._requests_by_model["gpt-4"] += 1
                await reporter._report_usage()
        finally:
            await reporter._http_client.aclose()

    asyncio.run(scenario())

    warnings = [m for m in caplog.messages if "unavailable" in m.lower()]
    assert len(warnings) == 1


def test_usage_report_result_literal_matches_documented_contract() -> None:
    assert set(UsageReportResult.__args__) == {"delivered", "unavailable", "retryable_failure"}

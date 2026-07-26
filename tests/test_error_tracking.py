"""Tests for optional error tracking.

The important properties are the *negative* ones: with no DSN configured, or
with sentry-sdk absent, nothing must be initialised, nothing sent, and nothing
raised. A local-first product must not phone home by accident.
"""

from __future__ import annotations

import sys

import pytest

from cutctx.observability import error_tracking


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    error_tracking.reset_for_tests()
    monkeypatch.delenv("CUTCTX_SENTRY_DSN", raising=False)
    monkeypatch.delenv("CUTCTX_SENTRY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("CUTCTX_SENTRY_TRACES_SAMPLE_RATE", raising=False)
    yield
    error_tracking.reset_for_tests()


def test_disabled_without_dsn():
    """The default posture: completely inert."""
    assert error_tracking.dsn() is None
    assert error_tracking.init() is False
    assert error_tracking.is_enabled() is False


def test_blank_dsn_is_treated_as_unset(monkeypatch):
    monkeypatch.setenv("CUTCTX_SENTRY_DSN", "   ")
    assert error_tracking.dsn() is None
    assert error_tracking.init() is False


def test_capture_is_a_noop_when_disabled():
    """Must not raise even though nothing is initialised."""
    error_tracking.capture_exception(ValueError("boom"))
    assert error_tracking.is_enabled() is False


def test_missing_sentry_sdk_is_handled(monkeypatch):
    """A DSN set without the optional dependency installed must warn, not crash.

    Setting the sys.modules entry to None makes `import sentry_sdk` raise
    ImportError, which is how CPython signals a blocked import.
    """
    monkeypatch.setenv("CUTCTX_SENTRY_DSN", "https://key@example.test/1")
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)

    assert error_tracking.init() is False
    assert error_tracking.is_enabled() is False


def test_traces_sample_rate_defaults_to_zero():
    """Tracing every request on a latency-sensitive proxy must be opt-in."""
    assert error_tracking.traces_sample_rate() == 0.0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0", 0.0), ("0.25", 0.25), ("1", 1.0), ("2", 1.0), ("-1", 0.0)],
)
def test_traces_sample_rate_is_clamped(monkeypatch, raw, expected):
    monkeypatch.setenv("CUTCTX_SENTRY_TRACES_SAMPLE_RATE", raw)
    assert error_tracking.traces_sample_rate() == expected


def test_traces_sample_rate_rejects_garbage(monkeypatch):
    monkeypatch.setenv("CUTCTX_SENTRY_TRACES_SAMPLE_RATE", "banana")
    assert error_tracking.traces_sample_rate() == 0.0


def test_environment_falls_back(monkeypatch):
    assert error_tracking.environment() == "unknown"
    monkeypatch.setenv("CUTCTX_DEPLOYMENT_PROFILE", "staging")
    assert error_tracking.environment() == "staging"
    monkeypatch.setenv("CUTCTX_SENTRY_ENVIRONMENT", "prod")
    assert error_tracking.environment() == "prod"


class TestScrubbing:
    """Compressed payloads are customer code, logs, and prompts. None of that
    may leave the process in an error report."""

    def test_request_body_and_cookies_removed(self):
        event = {"request": {"data": "SECRET PAYLOAD", "cookies": "a=b", "url": "/v1/messages"}}
        out = error_tracking._scrub(event, {})
        assert "data" not in out["request"]
        assert "cookies" not in out["request"]
        assert out["request"]["url"] == "/v1/messages"

    @pytest.mark.parametrize(
        "header",
        ["Authorization", "x-api-key", "X-Cutctx-Admin-Key", "X-Cutctx-User-Token", "Cookie"],
    )
    def test_credential_headers_redacted(self, header):
        event = {"request": {"headers": {header: "super-secret", "User-Agent": "curl"}}}
        out = error_tracking._scrub(event, {})
        assert out["request"]["headers"][header] == "[redacted]"
        assert out["request"]["headers"]["User-Agent"] == "curl"

    def test_stack_frame_locals_removed(self):
        event = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {"function": "compress", "vars": {"payload": "CUSTOMER CODE"}},
                                {"function": "route"},
                            ]
                        }
                    }
                ]
            }
        }
        out = error_tracking._scrub(event, {})
        frames = out["exception"]["values"][0]["stacktrace"]["frames"]
        assert "vars" not in frames[0]
        assert frames[0]["function"] == "compress"

    def test_scrub_tolerates_unexpected_shapes(self):
        """Sentry event shapes vary; the scrubber must not raise."""
        for event in ({}, {"request": None}, {"exception": {}}, {"exception": {"values": None}}):
            assert error_tracking._scrub(dict(event), {}) is not None

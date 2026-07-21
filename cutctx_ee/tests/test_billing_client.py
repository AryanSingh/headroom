"""Tests for the billing portal client contract."""

from __future__ import annotations

import pytest

from cutctx_ee.billing import client


class _FakeResponse:
    def __init__(self, status_code: int, *, content_type: str = "application/json", payload=None):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def test_checkout_seat_rejects_html_portal(monkeypatch):
    monkeypatch.setattr(
        client.httpx,
        "post",
        lambda *args, **kwargs: _FakeResponse(200, content_type="text/html; charset=utf-8"),
    )
    assert client.checkout_seat("lic-1", "user-1") is False


def test_checkout_seat_accepts_json_success(monkeypatch):
    monkeypatch.setattr(
        client.httpx,
        "post",
        lambda *args, **kwargs: _FakeResponse(200, payload={"status": "ok"}),
    )
    assert client.checkout_seat("lic-1", "user-1") is True


def test_checkout_seat_fails_closed_on_portal_exception_by_default(monkeypatch):
    monkeypatch.delenv("CUTCTX_LICENSE_STRICT_MODE", raising=False)

    def unavailable(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(client.httpx, "post", unavailable)

    assert client.checkout_seat("lic-1", "user-1") is False


def test_activate_instance_fails_closed_on_portal_exception_by_default(monkeypatch):
    monkeypatch.delenv("CUTCTX_LICENSE_STRICT_MODE", raising=False)

    def unavailable(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(client.httpx, "post", unavailable)

    assert client.activate_instance("lic-1", "instance-1") is False


def test_activate_instance_can_fail_open_only_in_explicit_dev_mode(monkeypatch):
    monkeypatch.setenv("CUTCTX_LICENSE_STRICT_MODE", "0")

    def unavailable(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(client.httpx, "post", unavailable)

    assert client.activate_instance("lic-1", "instance-1") is True


def test_checkout_seat_can_fail_open_only_in_explicit_dev_mode(monkeypatch):
    monkeypatch.setenv("CUTCTX_LICENSE_STRICT_MODE", "0")

    def unavailable(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(client.httpx, "post", unavailable)

    assert client.checkout_seat("lic-1", "user-1") is True


def test_strict_mode_is_enabled_for_unrecognized_values(monkeypatch):
    monkeypatch.setenv("CUTCTX_LICENSE_STRICT_MODE", "unexpected")

    assert client._strict_mode() is True


@pytest.mark.parametrize(
    ("operation", "expected_url"),
    [
        ("activate", "/v1/license/activate"),
        ("checkout", "/v1/license/checkout-seat"),
        ("start_trial", "/v1/license/start-trial"),
        ("check_trial", "/v1/license/check-trial"),
    ],
)
def test_license_service_key_is_sent_to_portal_calls(monkeypatch, operation, expected_url):
    monkeypatch.setenv("CUTCTX_LICENSE_SERVICE_API_KEY", "service-key")
    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", "must-not-be-sent")
    calls = []

    def capture(url, **kwargs):
        calls.append((url, kwargs))
        payload = {"status": "activated"} if operation == "activate" else {"status": "ok"}
        if operation == "check_trial":
            payload = {"active": True}
        return _FakeResponse(200, payload=payload)

    monkeypatch.setattr(client.httpx, "post", capture)
    if operation == "activate":
        assert client.activate_instance("lic-1", "inst-1") is True
    elif operation == "checkout":
        assert client.checkout_seat("lic-1", "user-1") is True
    elif operation == "start_trial":
        assert client.start_trial("trial-1", "user@example.com") is True
    else:
        assert client.is_trial_active("trial-1") is True

    assert calls[0][0] == f"{client.get_portal_url()}{expected_url}"
    assert calls[0][1]["headers"] == {"X-Cutctx-Admin-Key": "service-key"}
    assert calls[0][1]["timeout"] == 5.0
    assert isinstance(calls[0][1]["json"], dict)


def test_crl_service_key_is_sent_without_using_admin_key(monkeypatch):
    monkeypatch.setenv("CUTCTX_LICENSE_SERVICE_API_KEY", "service-key")
    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", "must-not-be-sent")
    client._CRL_CACHE["revoked"] = set()
    client._CRL_CACHE["expires_at"] = 0.0
    calls = []

    def capture(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(200, payload={"revoked": []})

    monkeypatch.setattr(client.httpx, "get", capture)

    assert client.is_revoked("lic-1") is False
    assert calls[0][1]["headers"] == {"X-Cutctx-Admin-Key": "service-key"}


def test_crl_call_omits_service_header_when_not_configured(monkeypatch):
    monkeypatch.delenv("CUTCTX_LICENSE_SERVICE_API_KEY", raising=False)
    client._CRL_CACHE["revoked"] = set()
    client._CRL_CACHE["expires_at"] = 0.0
    calls = []

    def capture(url, **kwargs):
        calls.append(kwargs)
        return _FakeResponse(200, payload={"revoked": []})

    monkeypatch.setattr(client.httpx, "get", capture)

    assert client.is_revoked("lic-1") is False
    assert "headers" not in calls[0]


@pytest.mark.parametrize("operation", ["activate", "checkout", "start_trial", "check_trial"])
def test_portal_calls_omit_service_header_when_not_configured(monkeypatch, operation):
    monkeypatch.delenv("CUTCTX_LICENSE_SERVICE_API_KEY", raising=False)
    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", "must-not-be-sent")
    calls = []

    def capture(url, **kwargs):
        calls.append(kwargs)
        payload = {"status": "activated"} if operation == "activate" else {"status": "ok"}
        if operation == "check_trial":
            payload = {"active": True}
        return _FakeResponse(200, payload=payload)

    monkeypatch.setattr(client.httpx, "post", capture)
    if operation == "activate":
        client.activate_instance("lic-1", "inst-1")
    elif operation == "checkout":
        client.checkout_seat("lic-1", "user-1")
    elif operation == "start_trial":
        client.start_trial("trial-1", "user@example.com")
    else:
        client.is_trial_active("trial-1")

    assert "headers" not in calls[0]


def test_strict_mode_denies_license_when_initial_crl_fetch_fails(monkeypatch):
    client._CRL_CACHE["revoked"] = set()
    client._CRL_CACHE["expires_at"] = 0.0
    monkeypatch.setenv("CUTCTX_LICENSE_STRICT_MODE", "1")

    def unavailable(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(client.httpx, "get", unavailable)

    assert client.is_revoked("license-without-crl") is True


def test_start_trial_rejects_html_portal(monkeypatch):
    monkeypatch.setattr(
        client.httpx,
        "post",
        lambda *args, **kwargs: _FakeResponse(200, content_type="text/html"),
    )
    assert client.start_trial("trial-1", "user@example.com") is False


def test_activate_instance_requires_expected_json(monkeypatch):
    monkeypatch.setattr(
        client.httpx,
        "post",
        lambda *args, **kwargs: _FakeResponse(200, payload={"status": "activated"}),
    )
    assert client.activate_instance("lic-1", "inst-1") is True


def test_trial_status_fails_open_on_non_json(monkeypatch):
    monkeypatch.setattr(
        client.httpx,
        "post",
        lambda *args, **kwargs: _FakeResponse(200, content_type="text/html"),
    )
    assert client.is_trial_active("trial-1") is True

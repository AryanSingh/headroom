"""Tests for the billing portal client contract."""

from __future__ import annotations

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

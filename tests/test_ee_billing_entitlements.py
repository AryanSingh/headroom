# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Regression tests: hosted trial entitlements must fail CLOSED.

Prior to this fix, ``cutctx_ee.billing.client.is_trial_active`` and
``start_trial`` both defaulted to ``True`` whenever the portal was
unreachable, timed out, answered with a non-200 status, or replied with a
non-JSON body (e.g. the marketing SPA answering every unmatched POST with
HTML). That let anyone with a forged or expired trial token bypass
enforcement simply by pointing the client at an unreachable host, or by
relying on the *default* unreachable-portal behavior in the field.

The contract enforced here:
  * Any network-level failure (timeout, connection error, exception) denies.
  * Any non-200 response (including 405 from an SPA fallback route) denies.
  * Any non-JSON response denies.
  * A malformed/missing ``active`` field denies (no defaulting to True).
  * A present ``expires_at`` must parse as RFC3339 and be in the future, or
    the trial is denied even if ``active`` was true.
  * Only an authenticated-enough 200 JSON response with ``active: true`` (and
    a future/absent ``expires_at``) grants access.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from cutctx_ee.billing import client
from cutctx_ee.trial import TrialManager


class _FakeResponse:
    def __init__(self, status_code: int, *, content_type: str = "application/json", payload=None):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def _future_iso(days: float = 1.0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _past_iso(days: float = 1.0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


class _Timeout(Exception):
    """Stand-in for httpx.TimeoutException so this test has no hard httpx dep."""


def _raise_timeout(*_args, **_kwargs):
    raise _Timeout("portal did not respond in time")


@pytest.mark.parametrize(
    ("label", "post_impl", "expected"),
    [
        ("timeout", _raise_timeout, False),
        ("405_from_spa", lambda *a, **k: _FakeResponse(405, content_type="text/html"), False),
        ("active_false", lambda *a, **k: _FakeResponse(200, payload={"active": False}), False),
        (
            "expired_expires_at",
            lambda *a, **k: _FakeResponse(
                200, payload={"active": True, "expires_at": _past_iso()}
            ),
            False,
        ),
        (
            "active_and_unexpired",
            lambda *a, **k: _FakeResponse(
                200, payload={"active": True, "expires_at": _future_iso()}
            ),
            True,
        ),
    ],
)
def test_is_trial_active_fails_closed(monkeypatch, label, post_impl, expected):
    monkeypatch.setattr(client.httpx, "post", post_impl)
    assert client.is_trial_active("trial-token") is expected, label


def test_is_trial_active_denies_when_active_field_missing(monkeypatch):
    """A 200 JSON body with no `active` key must NOT default to granting access."""
    monkeypatch.setattr(
        client.httpx, "post", lambda *a, **k: _FakeResponse(200, payload={"status": "ok"})
    )
    assert client.is_trial_active("trial-token") is False


def test_is_trial_active_denies_on_non_json_response(monkeypatch):
    monkeypatch.setattr(
        client.httpx, "post", lambda *a, **k: _FakeResponse(200, content_type="text/html")
    )
    assert client.is_trial_active("trial-token") is False


def test_is_trial_active_denies_when_expires_at_is_malformed(monkeypatch):
    monkeypatch.setattr(
        client.httpx,
        "post",
        lambda *a, **k: _FakeResponse(200, payload={"active": True, "expires_at": "not-a-date"}),
    )
    assert client.is_trial_active("trial-token") is False


def test_is_trial_active_grants_when_expires_at_absent(monkeypatch):
    monkeypatch.setattr(
        client.httpx, "post", lambda *a, **k: _FakeResponse(200, payload={"active": True})
    )
    assert client.is_trial_active("trial-token") is True


def test_start_trial_fails_closed_on_network_exception(monkeypatch):
    monkeypatch.setattr(client.httpx, "post", _raise_timeout)
    assert client.start_trial("trial-token", "user@example.com") is False


def test_start_trial_fails_closed_on_non_200(monkeypatch):
    monkeypatch.setattr(
        client.httpx, "post", lambda *a, **k: _FakeResponse(405, content_type="text/html")
    )
    assert client.start_trial("trial-token", "user@example.com") is False


def test_start_trial_grants_on_definite_ok(monkeypatch):
    monkeypatch.setattr(
        client.httpx, "post", lambda *a, **k: _FakeResponse(200, payload={"status": "ok"})
    )
    assert client.start_trial("trial-token", "user@example.com") is True


def test_trial_manager_start_trial_without_token_never_calls_network(monkeypatch):
    """Regression: starting a *local* trial (no server token/email) must never
    reach the network, and must never consult `is_trial_active` either — the
    two concerns (starting a fresh local trial clock vs. verifying a
    previously-issued server trial token) must stay independent.
    """

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("network must not be contacted when no trial token is provided")

    monkeypatch.setattr(client, "start_trial", _forbidden)
    monkeypatch.setattr(client, "is_trial_active", _forbidden)
    monkeypatch.setattr(client.httpx, "post", _forbidden)

    manager = TrialManager(MagicMock())
    state = manager.start_trial()

    assert state.trial_token is None
    assert state.org_id is None


def test_trial_manager_start_trial_denies_when_hosted_start_fails(tmp_path, monkeypatch):
    """When the portal denies hosted trial start, TrialManager must not persist
    server trial credentials or claim a successful server-side start."""
    state_path = tmp_path / "trial_state.json"
    manager = TrialManager(state_path)

    monkeypatch.setattr(client, "start_trial", lambda *a, **k: False)

    with patch("cutctx.billing.client.start_trial", return_value=False):
        with pytest.raises(RuntimeError, match="Hosted trial start denied"):
            manager.start_trial(
                org_id="org_1",
                trial_token="trial-token",
                customer_email="user@example.com",
            )

    assert not state_path.exists()
    assert manager._state is None

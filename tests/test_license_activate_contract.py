"""Contract tests for `cutctx license activate`.

Why this file exists: every pre-existing licence test mocked the portal, and
the mocks encoded a `/v1/license/validate` contract the server never
implemented. The suite stayed green while activation returned HTTP 405 for
every real customer. These tests pin the *actual* wire contract of the
Supabase `verify-license` edge function.

The live test at the bottom is opt-in so CI does not depend on the network,
but it is the only test here that could have caught the original break.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest
from click.testing import CliRunner

from cutctx.cli.license import DEFAULT_LICENSE_API_URL, activate

VALID_RESPONSE = {
    "valid": True,
    "tier": "enterprise",
    "seatsLimit": 500,
    "expiresAt": "2027-07-23T19:03:04.128321+00:00",
}


@pytest.fixture(autouse=True)
def isolate_license_cache(tmp_path, monkeypatch):
    """Keep the developer's real ~/.cutctx/license_cache.json untouched."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CUTCTX_HOME", str(tmp_path / ".cutctx"))
    (tmp_path / ".cutctx").mkdir(parents=True, exist_ok=True)
    yield


def _run(monkeypatch, handler, key="cutctx_testkey", extra_args=()):
    """Invoke `license activate` against a stubbed transport."""
    captured: dict[str, object] = {}

    def fake_post(url, json=None, timeout=None):  # noqa: A002
        captured["url"] = url
        captured["json"] = json
        return handler(url, json)

    monkeypatch.setattr(httpx, "post", fake_post)
    result = CliRunner().invoke(activate, [key, "--no-browser", *extra_args])
    return result, captured


def _response(payload, status=200):
    return httpx.Response(
        status_code=status,
        content=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "date": "Sat, 25 Jul 2026 00:00:00 GMT"},
    )


def test_default_url_is_the_supabase_functions_base():
    """A regression guard on the URL itself.

    The original defect was pointing at a static site that answered 405.
    """
    assert DEFAULT_LICENSE_API_URL.endswith("/functions/v1")
    assert "supabase.co" in DEFAULT_LICENSE_API_URL
    assert "pitchtoship" not in DEFAULT_LICENSE_API_URL


def test_posts_to_verify_license_with_key_field(monkeypatch):
    """The wire contract: POST <base>/verify-license with {"key": ...}.

    The server rejects `license_key` and `licenseKey` with HTTP 400 — the
    field name really is `key`.
    """
    result, captured = _run(monkeypatch, lambda u, j: _response(VALID_RESPONSE))

    assert result.exit_code == 0, result.output
    assert captured["url"] == f"{DEFAULT_LICENSE_API_URL}/verify-license"
    assert captured["json"] == {"key": "cutctx_testkey"}


def test_parses_tier_seats_and_expiry(monkeypatch):
    result, _ = _run(monkeypatch, lambda u, j: _response(VALID_RESPONSE))

    assert result.exit_code == 0, result.output
    assert "ENTERPRISE" in result.output
    assert "500" in result.output
    assert "2027-07-23" in result.output


def test_valid_false_is_rejected_not_activated(monkeypatch):
    """A 200 carrying valid=false must fail, not cache a bogus licence."""
    result, _ = _run(
        monkeypatch,
        lambda u, j: _response({"valid": False, "message": "License revoked."}),
    )

    assert result.exit_code == 1
    assert "not valid" in result.output
    assert "License revoked." in result.output


def test_http_400_surfaces_server_message(monkeypatch):
    """verify-license uses 400 + {"message": ...} for a bad key."""
    result, _ = _run(
        monkeypatch,
        lambda u, j: _response({"message": "A license key is required."}, status=400),
    )

    assert result.exit_code == 1
    assert "A license key is required." in result.output


def test_cloud_url_override_is_honoured(monkeypatch):
    """Self-hosted deployments must be able to repoint the licence API."""
    result, captured = _run(
        monkeypatch,
        lambda u, j: _response(VALID_RESPONSE),
        extra_args=("--cloud-url", "https://licence.example.test/fn"),
    )

    assert result.exit_code == 0, result.output
    assert captured["url"] == "https://licence.example.test/fn/verify-license"


def test_unexpected_status_is_an_error(monkeypatch):
    """The original symptom — a 405 from a static site — must fail loudly."""
    result, _ = _run(monkeypatch, lambda u, j: _response({}, status=405))

    assert result.exit_code == 1
    assert "405" in result.output


@pytest.mark.skipif(
    not os.environ.get("CUTCTX_LIVE_LICENSE_KEY"),
    reason="set CUTCTX_LIVE_LICENSE_KEY to run the live licence contract check",
)
def test_live_verify_license_contract():
    """Opt-in check against the real endpoint.

    This is the test class that was missing. Mocked-only coverage of a paid,
    network-dependent flow is why the 405 break shipped unnoticed. Run it in
    a release gate with a real key:

        CUTCTX_LIVE_LICENSE_KEY=<key> pytest tests/test_license_activate_contract.py
    """
    key = os.environ["CUTCTX_LIVE_LICENSE_KEY"]
    resp = httpx.post(
        f"{DEFAULT_LICENSE_API_URL}/verify-license",
        json={"key": key},
        timeout=15.0,
    )

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text[:200]}"
    assert "json" in resp.headers.get("content-type", ""), (
        "licence API returned a non-JSON body — it is probably not deployed "
        f"at this URL: content-type={resp.headers.get('content-type')!r}"
    )
    body = resp.json()
    assert body.get("valid") is True, f"key reported invalid: {body}"
    assert body.get("tier"), f"no tier in response: {body}"

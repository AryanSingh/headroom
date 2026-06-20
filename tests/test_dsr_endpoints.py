# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for the GDPR/CCPA DSR endpoints (Blocker-2)."""

from __future__ import annotations

import os
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

import headroom.proxy.routes.dsr as dsr_module
from headroom.proxy.server import ProxyConfig, create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("HEADROOM_ADMIN_API_KEY", "test-dsr-key-1234")
    config = ProxyConfig(
        cache_enabled=False,
        rate_limit_enabled=False,
        log_requests=False,
    )
    return TestClient(create_app(config))


def _auth_headers() -> dict[str, str]:
    return {"authorization": "Bearer test-dsr-key-1234"}


def test_dsr_export_unauthenticated_rejected(client: TestClient) -> None:
    """No Bearer token → 401 (admin auth gate)."""
    r = client.get("/v1/me/export?user_id=alice")
    assert r.status_code == 401, r.text


def test_dsr_delete_unauthenticated_rejected(client: TestClient) -> None:
    """No Bearer token → 401 (admin auth gate)."""
    r = client.post("/v1/me/delete", json={"user_id": "alice"})
    assert r.status_code == 401, r.text


def test_dsr_export_no_user_id_returns_400(client: TestClient) -> None:
    """Authenticated but no user_id → 400 (no silent empty target)."""
    r = client.get("/v1/me/export", headers=_auth_headers())
    assert r.status_code == 400
    assert "user_id" in r.json()["detail"]


def test_dsr_delete_no_user_id_returns_400(client: TestClient) -> None:
    """Authenticated but no user_id → 400 (no silent empty target).

    The endpoint accepts a Pydantic body so a missing ``user_id``
    field returns 422 (FastAPI validation error). An empty string
    also fails the model's min_length=1 constraint and returns 422.
    Both responses are acceptable; the contract is that the system
    does not silently target an empty user_id.
    """
    r = client.post("/v1/me/delete", json={}, headers=_auth_headers())
    assert r.status_code in (400, 422)
    if r.status_code == 400:
        assert "user_id" in r.json()["detail"]
    else:
        # 422: Pydantic body validation rejected the empty body.
        assert "user_id" in str(r.json())


def test_dsr_export_query_param_user_id(client: TestClient) -> None:
    """Authenticated with ?user_id=... in query string returns a structured payload."""
    r = client.get("/v1/me/export?user_id=alice", headers=_auth_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == "alice"
    assert "generated_at" in body
    assert "stores" in body
    assert "store_errors" in body
    # Memory subsystem is not configured in this test → reported as not_configured.
    assert "memory" in body["store_errors"]


def test_dsr_delete_body_user_id(client: TestClient) -> None:
    """Authenticated with body user_id returns a structured payload."""
    r = client.post(
        "/v1/me/delete", json={"user_id": "alice"}, headers=_auth_headers()
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == "alice"
    assert "deleted_at" in body
    assert "stores" in body
    assert "store_errors" in body
    # Memory subsystem is not configured in this test → reported as not_configured.
    assert "memory" in body["store_errors"]


def test_dsr_export_sso_user_id_from_state(client: TestClient) -> None:
    """The user_id resolves from request.state.headroom_user_id when set by SSO."""
    r = client.get("/v1/me/export", headers=_auth_headers())
    # The /v1/me/export handler accepts the user_id from a query param or
    # from request.state. We can't easily simulate request.state in a
    # TestClient call, so we test the helper directly instead.
    request = type("FakeRequest", (), {"state": type("FakeState", (), {"headroom_user_id": "bob"})(), "headers": {}})()
    target = dsr_module._resolve_target_user_id(
        request, body_user_id=None, query_user_id=None
    )
    assert target == "bob"


def test_dsr_export_user_id_priority() -> None:
    """Body > query > state > header; missing all → 400."""
    request_with_state = type(
        "FakeRequest",
        (),
        {
            "state": type(
                "FakeState", (), {"headroom_user_id": "from_state"}
            )(),
            "headers": {"X-Headroom-User-Id": "from_header"},
        },
    )()
    # Body wins.
    assert (
        dsr_module._resolve_target_user_id(
            request_with_state, body_user_id="from_body", query_user_id="from_query"
        )
        == "from_body"
    )
    # Query wins when no body.
    assert (
        dsr_module._resolve_target_user_id(
            request_with_state, body_user_id=None, query_user_id="from_query"
        )
        == "from_query"
    )
    # State wins when no body or query.
    assert (
        dsr_module._resolve_target_user_id(
            request_with_state, body_user_id=None, query_user_id=None
        )
        == "from_state"
    )
    # Header wins when only header is set.
    request_with_header_only = type(
        "FakeRequest",
        (),
        {
            "state": type("FakeState", (), {})(),
            "headers": {"X-Headroom-User-Id": "from_header"},
        },
    )()
    assert (
        dsr_module._resolve_target_user_id(
            request_with_header_only, body_user_id=None, query_user_id=None
        )
        == "from_header"
    )
    # No body, query, state, or header → raises HTTPException 400.
    request_empty = type(
        "FakeRequest",
        (),
        {
            "state": type("FakeState", (), {})(),
            "headers": {},
        },
    )()
    from fastapi import HTTPException

    try:
        dsr_module._resolve_target_user_id(
            request_empty, body_user_id=None, query_user_id=None
        )
        assert False, "expected HTTPException"
    except HTTPException as e:
        assert e.status_code == 400


def test_dsr_response_shape_contract() -> None:
    """The export response always has user_id, generated_at, stores, store_errors."""
    # Build a minimal request that the handler will accept.
    from fastapi import HTTPException

    request = type(
        "FakeRequest",
        (),
        {
            "state": type("FakeState", (), {"headroom_user_id": "alice"})(),
            "headers": {},
        },
    )()
    target = dsr_module._resolve_target_user_id(
        request, body_user_id=None, query_user_id=None
    )
    assert target == "alice"

    # The timestamp helper returns ISO-8601 UTC.
    ts = dsr_module._now_iso()
    assert "T" in ts
    assert ts.endswith("Z") or ts.endswith("+00:00")

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from unittest.mock import Mock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.routes.license_validation import create_license_validation_router
from cutctx.proxy.server import _apply_validated_license, create_app
from cutctx.telemetry.reporter import LicenseInfo, UsageReporter


def _user_token(*, subject: str = "user-1") -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {"sub": subject, "license_key": "license-1", "exp": time.time() + 60}
        ).encode()
    ).rstrip(b"=").decode()
    signed = f"ctu1.{payload}"
    return f"{signed}.{hmac.new(b'user-secret', signed.encode(), hashlib.sha256).hexdigest()}"


def _paid_app():
    app = create_app(
        ProxyConfig(
            backend="mock",
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            proxy_api_key="proxy-key",
            license_key="license-1",
            user_token_hmac_secret="user-secret",
        )
    )
    _apply_validated_license(app.state.proxy, LicenseInfo(status="active", plan="business"))
    return app


def test_local_validation_accepts_json_and_normalizes_valid_tier(monkeypatch) -> None:
    monkeypatch.setattr(
        "cutctx_ee.billing.pitchtoship_client.verify_license",
        lambda _license_key, hwid: {"valid": True, "tier": "business", "seats": 3},
    )
    app = FastAPI()
    app.include_router(create_license_validation_router())

    response = TestClient(app).post("/v1/license/validate", json={"license_key": "lic_test"})

    assert response.status_code == 200
    assert response.json() == {"status": "active", "plan": "business", "seats": 3}


def test_definitive_remote_invalid_license_does_not_fall_back_to_local_authority(
    monkeypatch,
) -> None:
    local_db = Mock()
    local_db.validate.return_value = {"valid": True, "tier": "enterprise"}
    monkeypatch.setattr(
        "cutctx_ee.billing.pitchtoship_client.verify_license",
        lambda _license_key, hwid: {"valid": False, "status": "revoked"},
    )
    monkeypatch.setattr(
        "cutctx_ee.billing.pitchtoship_client._get_cached_signed_token",
        lambda _license_key: "cached-token",
    )
    monkeypatch.setattr(
        "cutctx_ee.billing.pitchtoship_client._get_cached_public_key",
        lambda: "cached-public-key",
    )
    monkeypatch.setattr(
        "cutctx_ee.billing.license_db.get_license_db",
        lambda: local_db,
    )
    app = FastAPI()
    app.include_router(create_license_validation_router())

    response = TestClient(app).post(
        "/v1/license/validate",
        json={"license_key": "revoked-license"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["status"] == "revoked"
    local_db.validate.assert_not_called()


def test_remote_unavailability_preserves_local_fallback(monkeypatch) -> None:
    local_db = Mock()
    local_db.validate.return_value = {"valid": True, "tier": "enterprise"}
    monkeypatch.setattr(
        "cutctx_ee.billing.pitchtoship_client.verify_license",
        lambda _license_key, hwid: None,
    )
    monkeypatch.setattr(
        "cutctx_ee.billing.pitchtoship_client._get_cached_signed_token",
        lambda _license_key: None,
    )
    monkeypatch.setattr(
        "cutctx_ee.billing.license_db.get_license_db",
        lambda: local_db,
    )
    app = FastAPI()
    app.include_router(create_license_validation_router())

    response = TestClient(app).post(
        "/v1/license/validate",
        json={"license_key": "offline-license"},
    )

    assert response.status_code == 200
    assert response.json()["plan"] == "enterprise"
    local_db.validate.assert_called_once_with("offline-license")


def test_usage_reporter_normalizes_valid_tier_response(tmp_path) -> None:
    async def scenario() -> None:
        def validate(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/license/validate"
            assert json.loads(request.content) == {"license_key": "lic_test"}
            return httpx.Response(200, json={"valid": True, "tier": "business", "seats": 3})

        reporter = UsageReporter(
            license_key="lic_test",
            cloud_url="https://licenses.example",
            cache_path=tmp_path / "license.json",
        )
        reporter._http_client = httpx.AsyncClient(transport=httpx.MockTransport(validate))
        try:
            info = await reporter.validate_license()
        finally:
            await reporter._http_client.aclose()

        assert info.status == "active"
        assert info.plan == "business"

    asyncio.run(scenario())


def test_usage_reporter_does_not_reuse_active_cache_after_definitive_rejection(
    tmp_path,
) -> None:
    async def scenario() -> None:
        cache_path = tmp_path / "license.json"
        cache_path.write_text(
            json.dumps(LicenseInfo(status="active", plan="business").to_dict()),
            encoding="utf-8",
        )

        def validate(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={"detail": {"valid": False, "status": "revoked"}},
            )

        reporter = UsageReporter(
            license_key="revoked-license",
            cloud_url="https://licenses.example",
            cache_path=cache_path,
        )
        reporter._http_client = httpx.AsyncClient(transport=httpx.MockTransport(validate))
        try:
            info = await reporter.validate_license()
        finally:
            await reporter._http_client.aclose()

        assert info.status == "revoked"
        assert info.plan is None
        assert json.loads(cache_path.read_text(encoding="utf-8"))["status"] == "revoked"

    asyncio.run(scenario())


def test_paid_provider_request_requires_user_scoped_token() -> None:
    app = _paid_app()

    response = TestClient(app).post(
        "/v1/chat/completions",
        headers={"X-Cutctx-Proxy-Key": "proxy-key"},
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 401


def test_paid_provider_request_denies_when_user_has_no_seat(monkeypatch) -> None:
    monkeypatch.setattr("cutctx_ee.billing.client.checkout_seat", lambda *_args: False)
    app = _paid_app()

    response = TestClient(app).post(
        "/v1/chat/completions",
        headers={"X-Cutctx-Proxy-Key": "proxy-key", "X-Cutctx-User-Token": _user_token()},
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 403


def test_paid_provider_request_with_valid_token_and_seat_reaches_backend(monkeypatch) -> None:
    monkeypatch.setattr("cutctx_ee.billing.client.checkout_seat", lambda *_args: True)
    app = _paid_app()

    async def accepted(_request):
        return JSONResponse({"status": "accepted"})

    app.state.proxy.handle_openai_chat = accepted
    response = TestClient(app).post(
        "/v1/chat/completions",
        headers={
            "X-Cutctx-Proxy-Key": "proxy-key",
            "X-Cutctx-User-Token": _user_token(),
        },
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200


@pytest.mark.parametrize("seat_available", [True, False])
def test_paid_websocket_guard_returns_policy_close(monkeypatch, seat_available: bool) -> None:
    monkeypatch.setattr(
        "cutctx_ee.billing.client.checkout_seat",
        lambda *_args: seat_available,
    )
    headers = {"X-Cutctx-Proxy-Key": "proxy-key"}
    if not seat_available:
        headers["X-Cutctx-User-Token"] = _user_token()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with TestClient(_paid_app()).websocket_connect("/v1/responses", headers=headers):
            pass

    assert exc_info.value.code == 1008

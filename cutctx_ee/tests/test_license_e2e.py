# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from unittest.mock import patch

from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app

app = create_app(
    ProxyConfig(
        backend="mock",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        admin_api_key="test-admin",
    )
)
client = TestClient(app)
ADMIN_HEADERS = {"X-Cutctx-Admin-Key": "test-admin"}


def test_activate_license():
    with patch("cutctx_ee.billing.license_db.LicenseDB.validate", return_value={"valid": True}):
        with patch("cutctx_ee.billing.license_db.LicenseDB.activate_instance", return_value=True):
            resp = client.post(
                "/v1/license/activate",
                json={"license_key": "test_key", "instance_id": "inst_1"},
                headers=ADMIN_HEADERS,
            )
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}


def test_activate_license_returns_failure_when_instance_activation_is_rejected():
    with patch("cutctx_ee.billing.license_db.LicenseDB.validate", return_value={"valid": True}):
        with patch("cutctx_ee.billing.license_db.LicenseDB.activate_instance", return_value=False):
            resp = client.post(
                "/v1/license/activate",
                json={"license_key": "test_key", "instance_id": "inst_1"},
                headers=ADMIN_HEADERS,
            )

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"error": "activation_rejected"}


def test_portal_client_reports_activation_http_failure(monkeypatch):
    class Response:
        status_code = 409
        headers = {"content-type": "application/json"}

        def json(self):
            return {"detail": {"error": "activation_rejected"}}

    monkeypatch.setattr("cutctx_ee.billing.client.httpx.post", lambda *args, **kwargs: Response())

    from cutctx_ee.billing.client import activate_instance

    assert activate_instance("test_key", "inst_1") is False


def test_get_crl():
    with patch("cutctx_ee.billing.license_db.LicenseDB.get_crl", return_value=["revoked_1"]):
        resp = client.get("/v1/license/crl", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == {"revoked": ["revoked_1"]}


def test_checkout_seat():
    with patch("cutctx_ee.billing.license_db.LicenseDB.validate", return_value={"valid": True}):
        with patch("cutctx_ee.billing.license_db.LicenseDB.checkout_seat", return_value=True):
            resp = client.post(
                "/v1/license/checkout-seat",
                json={"license_key": "test_key", "user_id": "u1", "lease_duration": 3600.0},
                headers=ADMIN_HEADERS,
            )
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}


def test_start_trial():
    with patch("cutctx_ee.billing.license_db.LicenseDB.start_trial", return_value=True):
        resp = client.post(
            "/v1/license/start-trial",
            json={"trial_token": "tok_1", "customer_email": "test@example.com"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_check_trial():
    with patch("cutctx_ee.billing.license_db.LicenseDB.is_trial_active", return_value=True):
        resp = client.post(
            "/v1/license/check-trial",
            json={"trial_token": "tok_1"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json() == {"active": True}

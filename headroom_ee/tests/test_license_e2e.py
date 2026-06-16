from unittest.mock import patch

from fastapi.testclient import TestClient

from headroom.proxy.server import create_app

app = create_app()
client = TestClient(app)


def test_activate_license():
    with patch("headroom_ee.billing.license_db.LicenseDB.validate", return_value={"valid": True}):
        with patch("headroom_ee.billing.license_db.LicenseDB.activate_instance", return_value=True):
            resp = client.post(
                "/v1/license/activate", json={"license_key": "test_key", "instance_id": "inst_1"}
            )
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}


def test_get_crl():
    with patch("headroom_ee.billing.license_db.LicenseDB.get_crl", return_value=["revoked_1"]):
        resp = client.get("/v1/license/crl")
        assert resp.status_code == 200
        assert resp.json() == {"revoked": ["revoked_1"]}


def test_checkout_seat():
    with patch("headroom_ee.billing.license_db.LicenseDB.validate", return_value={"valid": True}):
        with patch("headroom_ee.billing.license_db.LicenseDB.checkout_seat", return_value=True):
            resp = client.post(
                "/v1/license/checkout-seat",
                json={"license_key": "test_key", "user_id": "u1", "lease_duration": 3600.0},
            )
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}


def test_start_trial():
    with patch("headroom_ee.billing.license_db.LicenseDB.start_trial", return_value=True):
        resp = client.post(
            "/v1/license/start-trial",
            json={"trial_token": "tok_1", "customer_email": "test@example.com"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_check_trial():
    with patch("headroom_ee.billing.license_db.LicenseDB.is_trial_active", return_value=True):
        resp = client.post("/v1/license/check-trial", json={"trial_token": "tok_1"})
        assert resp.status_code == 200
        assert resp.json() == {"active": True}

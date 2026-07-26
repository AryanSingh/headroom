from __future__ import annotations

from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cutctx.proxy.routes.license_validation import create_license_validation_router
from cutctx_ee.entitlements import FEATURE_TIERS, EntitlementChecker


def test_hosted_enterprise_key_activates_and_unlocks_every_enterprise_feature(monkeypatch):
    local_db = Mock()
    monkeypatch.setattr(
        "cutctx_ee.billing.pitchtoship_client.verify_license",
        lambda _license_key, hwid: {"valid": True, "tier": "enterprise", "seats": 500},
    )
    monkeypatch.setattr(
        "cutctx_ee.billing.pitchtoship_client.heartbeat_seat",
        lambda _license_key, hwid: {"accepted": True},
    )
    monkeypatch.setattr("cutctx_ee.billing.license_db.get_license_db", lambda: local_db)
    app = FastAPI()
    app.include_router(create_license_validation_router())

    validation = TestClient(app).post(
        "/v1/license/validate", json={"license_key": "cutctx_test_enterprise"}
    )
    activation = TestClient(app).post(
        "/v1/license/activate",
        json={"license_key": "cutctx_test_enterprise", "instance_id": "instance-1"},
    )

    assert validation.status_code == 200
    assert validation.json()["plan"] == "enterprise"
    assert activation.status_code == 200
    assert all(EntitlementChecker("enterprise").is_entitled(feature) for feature in FEATURE_TIERS)
    local_db.validate.assert_not_called()


def test_hosted_enterprise_capacity_rejection_is_not_bypassed_by_local_state(monkeypatch):
    local_db = Mock()
    monkeypatch.setattr(
        "cutctx_ee.billing.pitchtoship_client.verify_license",
        lambda _license_key, hwid: {"valid": True, "tier": "enterprise", "seats": 500},
    )
    monkeypatch.setattr(
        "cutctx_ee.billing.pitchtoship_client.heartbeat_seat",
        lambda _license_key, hwid: {"accepted": False},
    )
    monkeypatch.setattr("cutctx_ee.billing.license_db.get_license_db", lambda: local_db)
    app = FastAPI()
    app.include_router(create_license_validation_router())

    response = TestClient(app).post(
        "/v1/license/activate",
        json={"license_key": "cutctx_test_enterprise", "instance_id": "instance-over-limit"},
    )

    assert response.status_code == 409
    local_db.validate.assert_not_called()

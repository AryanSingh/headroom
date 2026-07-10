from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.savings_canary import reset_savings_canary_coordinator_for_tests
from cutctx.proxy.server import create_app


@pytest.fixture
def canary_client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", "canary-admin-test-key")
    monkeypatch.setenv("CUTCTX_SAVINGS_CANARY_ENABLED", "1")
    monkeypatch.setenv("CUTCTX_SAVINGS_CANARY_SALT", "stable-test-salt")
    monkeypatch.setenv("CUTCTX_SAVINGS_CANARY_PATH", str(tmp_path / "canary.json"))
    reset_savings_canary_coordinator_for_tests()
    app = create_app(ProxyConfig(cache_enabled=False, rate_limit_enabled=False))
    with TestClient(app) as client:
        yield client
    reset_savings_canary_coordinator_for_tests()


def _auth() -> dict[str, str]:
    return {"authorization": "Bearer canary-admin-test-key"}


def test_feedback_requires_canonical_fields(canary_client: TestClient):
    for payload in (
        {"arm": "control", "quality_success": True},
        {"event_id": "eval/task", "quality_success": True},
        {"event_id": "eval/task", "arm": "control"},
    ):
        response = canary_client.post(
            "/savings-canary/feedback", headers=_auth(), json=payload
        )
        assert response.status_code == 422, response.text


def test_feedback_duplicate_returns_200_without_double_counting(canary_client: TestClient):
    payload = {
        "event_id": "evaluation-run/task-id",
        "request_id": None,
        "arm": "model_routing",
        "quality_success": True,
        "retries": 0,
        "user_corrections": 0,
        "evaluator": "coding-eval-v1",
        "evaluated_at": "2026-07-10T12:00:00Z",
    }
    first = canary_client.post(
        "/savings-canary/feedback", headers=_auth(), json=payload
    )
    second = canary_client.post(
        "/savings-canary/feedback", headers=_auth(), json=payload
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    metrics = second.json()["metrics"]["model_routing"]
    assert metrics["quality_samples"] == 1
    assert metrics["quality_successes"] == 1

"""H8 regression: genuine tamper-evidence for the SQLite audit log.

Before this fix ``AuditLogger`` had no ``verify_chain`` at all, so
``GET /audit/verify`` (cutctx/proxy/routes/admin.py:570) raised AttributeError
and returned HTTP 500 on every call. These tests pin the real behaviour: an
untouched log verifies, and *any* mutation of a stored row is detected and
reported with the offending entry id.
"""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cutctx.audit import AuditEvent, AuditLogger
from cutctx.proxy.routes.admin import create_admin_router


@pytest.fixture
def audit_db(tmp_path):
    return str(tmp_path / "audit-chain.db")


def _seed(logger: AuditLogger, count: int = 5, org_id: str | None = "acme") -> None:
    for index in range(count):
        logger.log(
            AuditEvent(
                action="config.changed",
                actor=f"admin{index}@example.com",
                detail={"seq": index},
                org_id=org_id,
                event_id=f"evt-{index}",
            )
        )


def test_verify_chain_exists_and_passes_on_clean_log(audit_db):
    """The endpoint's call site must not raise — H8's proximate 500."""
    logger = AuditLogger(db_path=audit_db)
    _seed(logger)

    result = logger.verify_chain(tenant_id=None)

    assert result["ok"] is True
    assert result["checked"] == 5
    assert result["unverifiable"] == 0
    assert result["broken_at"] is None
    logger.close()


def test_verify_chain_detects_tampered_row(audit_db):
    """Editing a single stored field must FAIL verification."""
    logger = AuditLogger(db_path=audit_db)
    _seed(logger)
    logger.close()

    # Tamper: rewrite the actor of one row, leaving hashes untouched —
    # exactly what an attacker with DB write access would do.
    conn = sqlite3.connect(audit_db)
    conn.execute("UPDATE audit_events SET actor = ? WHERE event_id = ?", ("mallory", "evt-2"))
    conn.commit()
    conn.close()

    logger = AuditLogger(db_path=audit_db)
    result = logger.verify_chain(tenant_id=None)

    assert result["ok"] is False
    assert result["broken_at"] is not None
    assert result["broken_at"]["event_id"] == "evt-2"
    assert result["broken_at"]["reason"] == "entry_hash_mismatch"
    logger.close()


def test_verify_chain_detects_tampered_detail_payload(audit_db):
    """The JSON detail column is covered by the chain too."""
    logger = AuditLogger(db_path=audit_db)
    _seed(logger)
    logger.close()

    conn = sqlite3.connect(audit_db)
    conn.execute("UPDATE audit_events SET detail = ? WHERE event_id = ?", ('{"seq": 999}', "evt-3"))
    conn.commit()
    conn.close()

    result = AuditLogger(db_path=audit_db).verify_chain(tenant_id=None)
    assert result["ok"] is False
    assert result["broken_at"]["event_id"] == "evt-3"


def test_verify_chain_detects_deleted_row(audit_db):
    """Deleting a row breaks the prev_hash link of its successor."""
    logger = AuditLogger(db_path=audit_db)
    _seed(logger)
    logger.close()

    conn = sqlite3.connect(audit_db)
    conn.execute("DELETE FROM audit_events WHERE event_id = ?", ("evt-2",))
    conn.commit()
    conn.close()

    result = AuditLogger(db_path=audit_db).verify_chain(tenant_id=None)
    assert result["ok"] is False
    assert result["broken_at"]["event_id"] == "evt-3"
    assert result["broken_at"]["reason"] == "prev_hash_mismatch"


def test_verify_chain_reports_hmac_mode_when_key_configured(audit_db, monkeypatch):
    monkeypatch.setenv("CUTCTX_AUDIT_SECRET_KEY", "s3cret-high-entropy-value")
    logger = AuditLogger(db_path=audit_db)
    _seed(logger, count=2)

    result = logger.verify_chain()
    assert result["ok"] is True
    assert result["mode"] == "hmac-sha256"
    assert result["key_configured"] is True
    assert result["forgeable"] is False
    logger.close()


def test_verify_chain_is_honest_about_unkeyed_chain(audit_db, monkeypatch):
    """Without a secret the chain is forgeable — the report must say so."""
    monkeypatch.delenv("CUTCTX_AUDIT_SECRET_KEY", raising=False)
    logger = AuditLogger(db_path=audit_db)
    _seed(logger, count=2)

    result = logger.verify_chain()
    assert result["ok"] is True
    assert result["mode"] == "sha256"
    assert result["key_configured"] is False
    assert result["forgeable"] is True
    logger.close()


def test_verify_chain_counts_legacy_rows_as_unverifiable(audit_db):
    """Pre-feature rows have NULL hashes: report them, do not cry tamper."""
    logger = AuditLogger(db_path=audit_db)
    _seed(logger, count=2)
    logger.close()

    conn = sqlite3.connect(audit_db)
    conn.execute(
        """
        INSERT INTO audit_events
        (event_id, timestamp, action, actor, success, detail, created_at)
        VALUES ('legacy-1', '2020-01-01T00:00:00+00:00', 'a', 'b', 1, '{}', 0)
        """
    )
    conn.commit()
    conn.close()

    result = AuditLogger(db_path=audit_db).verify_chain()
    assert result["ok"] is True
    assert result["unverifiable"] == 1
    assert result["checked"] == 2


def test_verify_chain_scopes_to_tenant(audit_db):
    logger = AuditLogger(db_path=audit_db)
    for index in range(3):
        logger.log(AuditEvent(action="a", actor="x", org_id="alpha", event_id=f"a-{index}"))
    for index in range(3):
        logger.log(AuditEvent(action="a", actor="x", org_id="beta", event_id=f"b-{index}"))
    logger.close()

    conn = sqlite3.connect(audit_db)
    conn.execute("UPDATE audit_events SET actor = 'evil' WHERE event_id = 'b-1'")
    conn.commit()
    conn.close()

    logger = AuditLogger(db_path=audit_db)
    # The untouched tenant still verifies...
    assert logger.verify_chain(tenant_id="alpha")["ok"] is True
    # ...while the tampered one does not.
    beta = logger.verify_chain(tenant_id="beta")
    assert beta["ok"] is False
    assert beta["broken_at"]["event_id"] == "b-1"
    logger.close()


def _audit_verify_client(audit_logger, audit_chain_store=None) -> TestClient:
    proxy = SimpleNamespace(
        audit_logger=audit_logger,
        audit_chain_store=audit_chain_store,
    )
    no_auth = lambda: None
    dependency_factory = lambda _name: no_auth
    router = create_admin_router(
        proxy,
        SimpleNamespace(),
        require_admin_auth=no_auth,
        require_rbac_permission=dependency_factory,
        require_entitlement=dependency_factory,
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_audit_verify_endpoint_returns_structured_valid_verdict(audit_db):
    logger = AuditLogger(db_path=audit_db)
    _seed(logger, count=1)
    with _audit_verify_client(logger) as client:
        response = client.get("/audit/verify")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "valid"
    assert body["valid"] is True
    assert body["event_id"] is None
    logger.close()


def test_audit_verify_endpoint_returns_200_for_tamper_verdict():
    logger = SimpleNamespace(
        verify_chain=lambda tenant_id=None: {
            "ok": False,
            "broken_at": {"event_id": "evt-2", "reason": "entry_hash_mismatch"},
        }
    )
    with _audit_verify_client(logger) as client:
        response = client.get("/audit/verify", params={"tenant_id": "acme"})

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "status": "tampered",
        "valid": False,
        "tenant_id": "acme",
        "event_id": "evt-2",
        "reason": "entry_hash_mismatch",
        "broken_at": {"event_id": "evt-2", "reason": "entry_hash_mismatch"},
        "lightweight": {
            "ok": False,
            "broken_at": {"event_id": "evt-2", "reason": "entry_hash_mismatch"},
        },
        "hash_chain": None,
    }


def test_audit_verify_endpoint_hides_lightweight_verifier_exception():
    logger = SimpleNamespace(
        verify_chain=lambda tenant_id=None: (_ for _ in ()).throw(
            RuntimeError("secret verifier internals")
        )
    )
    with _audit_verify_client(logger) as client:
        response = client.get("/audit/verify")

    assert response.status_code == 500
    assert "secret verifier internals" not in response.text
    assert response.json() == {"detail": "Audit verification failed"}


def test_audit_verify_endpoint_hides_hash_chain_store_exception():
    logger = SimpleNamespace(verify_chain=lambda tenant_id=None: {"ok": True})
    store = SimpleNamespace(
        verify_chain=lambda tenant_id: (_ for _ in ()).throw(
            RuntimeError("secret hash-store internals")
        )
    )
    with _audit_verify_client(logger, store) as client:
        response = client.get("/audit/verify")

    assert response.status_code == 500
    assert "secret hash-store internals" not in response.text
    assert response.json() == {"detail": "Audit verification failed"}


def test_audit_verify_endpoint_rejects_non_boolean_hash_chain_result():
    logger = SimpleNamespace(verify_chain=lambda tenant_id=None: {"ok": True})
    store = SimpleNamespace(verify_chain=lambda tenant_id: "yes")
    with _audit_verify_client(logger, store) as client:
        response = client.get("/audit/verify")

    assert response.status_code == 500
    assert "yes" not in response.text
    assert response.json() == {"detail": "Audit verification failed"}


@pytest.mark.parametrize("malformed", [None, [], "not-a-verdict", {"ok": "yes"}])
def test_audit_verify_endpoint_rejects_malformed_hash_verifier_results(malformed):
    logger = SimpleNamespace(verify_chain=lambda tenant_id=None: malformed)
    with _audit_verify_client(logger) as client:
        response = client.get("/audit/verify")

    assert response.status_code == 500
    assert "not-a-verdict" not in response.text
    assert response.json() == {"detail": "Audit verification failed"}


def test_audit_verify_endpoint_returns_503_without_audit_logger():
    with _audit_verify_client(None) as client:
        response = client.get("/audit/verify")

    assert response.status_code == 503
    assert response.json() == {"detail": "Audit logging not available"}


def test_audit_verify_openapi_documents_verdict_and_error_contracts():
    with _audit_verify_client(
        SimpleNamespace(verify_chain=lambda tenant_id=None: {"ok": True})
    ) as client:
        schema = client.app.openapi()

    operation = schema["paths"]["/audit/verify"]["get"]
    responses = operation["responses"]
    assert {"200", "422", "500", "503"} <= set(responses)
    assert responses["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AuditVerificationVerdict"
    }
    assert responses["500"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AuditVerificationFailure"
    }
    assert responses["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AuditLoggingUnavailable"
    }
    assert responses["500"]["description"] == "Audit verification failed"
    assert responses["503"]["description"] == "Audit logging not available"
    assert "ok" in schema["components"]["schemas"]["AuditVerificationVerdict"]["properties"]
    failure_detail = schema["components"]["schemas"]["AuditVerificationFailure"]["properties"][
        "detail"
    ]
    unavailable_detail = schema["components"]["schemas"]["AuditLoggingUnavailable"]["properties"][
        "detail"
    ]
    assert failure_detail["const"] == "Audit verification failed"
    assert unavailable_detail["const"] == "Audit logging not available"


AUTHORITATIVE_NON_ORCHESTRATION_PATHS = frozenset(
    [
        "/admin/config/flags",
        "/admin/dashboard-sessions",
        "/analytics/dashboard",
        "/analytics/projects",
        "/audit/events",
        "/audit/export",
        "/audit/stats",
        "/audit/verify",
        "/backend-api/codex/responses",
        "/backend-api/codex/responses/{sub_path}",
        "/backend-api/responses",
        "/backend-api/responses/{sub_path}",
        "/budget/status",
        "/cache/clear",
        "/config/flags",
        "/dashboard",
        "/dashboard/{path}",
        "/ensemble/status",
        "/entitlements",
        "/firewall/scan",
        "/firewall/status",
        "/fleet/deployments",
        "/fleet/deployments/heartbeat",
        "/fleet/deployments/{deployment_id}",
        "/fleet/summary",
        "/health",
        "/health/config",
        "/intelligence/autopilot/status",
        "/intelligence/context-budget/status",
        "/intelligence/cost-forecast/status",
        "/intelligence/dedup/status",
        "/intelligence/profiles/status",
        "/intelligence/shared-context/status",
        "/intelligence/task-aware/status",
        "/license-status",
        "/livez",
        "/metrics",
        "/orgs",
        "/orgs/{org_id}",
        "/orgs/{org_id}/workspaces",
        "/policy/status",
        "/quota",
        "/rbac/roles",
        "/rbac/roles/{user_id}",
        "/readyz",
        "/reports/savings",
        "/reports/usage",
        "/retention/cleanup",
        "/retention/stats",
        "/savings-canary/feedback",
        "/savings-canary/promote",
        "/savings-canary/report",
        "/scim/v2/Groups",
        "/scim/v2/Groups/{group_id}",
        "/scim/v2/ResourceTypes",
        "/scim/v2/ServiceProviderConfig",
        "/scim/v2/Users",
        "/scim/v2/Users/{user_id}",
        "/stats",
        "/stats-history",
        "/stats/reset",
        "/structured-output/status",
        "/structured-output/validate",
        "/subscription-window",
        "/transformations/feed",
        "/transformations/traces",
        "/transformations/traces/{request_id}",
        "/v1/admin/mfa",
        "/v1/admin/mfa/code",
        "/v1/admin/mfa/enroll",
        "/v1/admin/mfa/verify",
        "/v1/airgap/check",
        "/v1/airgap/policy",
        "/v1/airgap/status",
        "/v1/audio/speech",
        "/v1/audio/transcriptions",
        "/v1/audit/events",
        "/v1/audit/events/{tenant_id}",
        "/v1/audit/verify/{tenant_id}",
        "/v1/auth/client/status",
        "/v1/batches",
        "/v1/batches/{batch_id}",
        "/v1/batches/{batch_id}/cancel",
        "/v1/chat/completions",
        "/v1/codex/responses",
        "/v1/codex/responses/{sub_path}",
        "/v1/compress",
        "/v1/dsr/delete",
        "/v1/dsr/export",
        "/v1/embeddings",
        "/v1/feedback",
        "/v1/feedback/{tool_name}",
        "/v1/images/generations",
        "/v1/license/activate",
        "/v1/license/check-trial",
        "/v1/license/checkout-seat",
        "/v1/license/crl",
        "/v1/license/start-trial",
        "/v1/license/validate",
        "/v1/memory/query",
        "/v1/memory/review",
        "/v1/memory/search",
        "/v1/memory/sync",
        "/v1/messages",
        "/v1/messages/batches",
        "/v1/messages/batches/{batch_id}",
        "/v1/messages/batches/{batch_id}/cancel",
        "/v1/messages/batches/{batch_id}/results",
        "/v1/messages/count_tokens",
        "/v1/models",
        "/v1/models/{model_id}",
        "/v1/moderations",
        "/v1/policies",
        "/v1/policies/{org_id}/signed",
        "/v1/providers",
        "/v1/providers/{name}/disable",
        "/v1/providers/{name}/enable",
        "/v1/rate_limit/stats",
        "/v1/rbac/assignments",
        "/v1/rbac/assignments/{user_id}",
        "/v1/residency/proof",
        "/v1/responses",
        "/v1/responses/{sub_path}",
        "/v1/retrieve",
        "/v1/retrieve/stats",
        "/v1/retrieve/tool_call",
        "/v1/retrieve/{hash_key}",
        "/v1/secrets/",
        "/v1/secrets/{name}",
        "/v1/sessions",
        "/v1/sessions/recover",
        "/v1/sessions/{session_id}/replay",
        "/v1/sessions/{session_id}/state",
        "/v1/spend/dashboard",
        "/v1/spend/events",
        "/v1/spend/export/csv",
        "/v1/spend/query",
        "/v1/sso/config",
        "/v1/sso/validate",
        "/v1/stats",
        "/v1/telemetry",
        "/v1/telemetry/export",
        "/v1/telemetry/import",
        "/v1/telemetry/tools",
        "/v1/telemetry/tools/{signature_hash}",
        "/v1/toin/pattern/{hash_prefix}",
        "/v1/toin/patterns",
        "/v1/toin/stats",
        "/v1/v1internal:countTokens",
        "/v1/v1internal:generateContent",
        "/v1/v1internal:loadCodeAssist",
        "/v1/v1internal:onboardUser",
        "/v1/v1internal:streamGenerateContent",
        "/v1/version",
        "/v1beta/batches/{batch_name}",
        "/v1beta/batches/{batch_name}:cancel",
        "/v1beta/cachedContents",
        "/v1beta/cachedContents/{cache_id}",
        "/v1beta/models",
        "/v1beta/models/{model_name}",
        "/v1beta/models/{model}:batchEmbedContents",
        "/v1beta/models/{model}:batchGenerateContent",
        "/v1beta/models/{model}:countTokens",
        "/v1beta/models/{model}:embedContent",
        "/v1beta/models/{model}:generateContent",
        "/v1beta/models/{model}:streamGenerateContent",
        "/v1internal:countTokens",
        "/v1internal:generateContent",
        "/v1internal:loadCodeAssist",
        "/v1internal:onboardUser",
        "/v1internal:streamGenerateContent",
        "/webhooks/stripe",
        "/webhooks/subscriptions",
        "/webhooks/test",
        "/workspaces/{workspace_id}/projects",
        "/{api_version}/projects/{project}/locations/{location}/publishers/{publisher}/models/{model}:countTokens",
        "/{api_version}/projects/{project}/locations/{location}/publishers/{publisher}/models/{model}:generateContent",
        "/{api_version}/projects/{project}/locations/{location}/publishers/{publisher}/models/{model}:rawPredict",
        "/{api_version}/projects/{project}/locations/{location}/publishers/{publisher}/models/{model}:streamGenerateContent",
        "/{api_version}/projects/{project}/locations/{location}/publishers/{publisher}/models/{model}:streamRawPredict",
        "/{path}",
    ]
)


def test_openapi_preserves_authoritative_non_orchestration_routes():
    artifact = json.load(open("artifacts/openapi.json"))["paths"]

    assert len(AUTHORITATIVE_NON_ORCHESTRATION_PATHS) == 181
    assert AUTHORITATIVE_NON_ORCHESTRATION_PATHS <= set(artifact)
    assert not [path for path in artifact if path.startswith("/v1/orchestration")]

"""H8 regression: genuine tamper-evidence for the SQLite audit log.

Before this fix ``AuditLogger`` had no ``verify_chain`` at all, so
``GET /audit/verify`` (cutctx/proxy/routes/admin.py:570) raised AttributeError
and returned HTTP 500 on every call. These tests pin the real behaviour: an
untouched log verifies, and *any* mutation of a stored row is detected and
reported with the offending entry id.
"""

from __future__ import annotations

import sqlite3

import pytest

from cutctx.audit import AuditEvent, AuditLogger


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
    conn.execute(
        "UPDATE audit_events SET detail = ? WHERE event_id = ?", ('{"seq": 999}', "evt-3")
    )
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
